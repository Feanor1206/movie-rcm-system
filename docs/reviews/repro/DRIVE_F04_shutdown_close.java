import com.dippie.moviercm.service.storage.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Production reservation boundary; actual tiny-file handle; all stalls released in finally.
public class DRIVE_F04_shutdown_close {
  public static void main(String[] args) throws Exception {
    var io = new DriveIoExecutor(50, 50, 1, new DriveCircuitBreaker(1000, 100));
    var reservation = io.acquireReservation();
    var entered = new CountDownLatch(1);
    var release = new CountDownLatch(1);
    var caller = Executors.newSingleThreadExecutor();
    var closeThread = new AtomicReference<String>();
    Path file = Files.createTempFile("codex-f04-", ".bin");
    var handle = FileChannel.open(file, StandardOpenOption.READ);
    try {
      io.shutdown();
      var result = caller.submit(() -> reservation.closeAsync(() -> {
        closeThread.set(Thread.currentThread().getName());
        entered.countDown();
        release.await();
        handle.close();
      }, "reviewer-post-shutdown"));
      if (!entered.await(2, TimeUnit.SECONDS)) throw new AssertionError("No close entered");
      boolean blocked;
      try { result.get(200, TimeUnit.MILLISECONDS); blocked = false; }
      catch (TimeoutException expected) { blocked = true; }
      System.out.println("callerBlocked=" + blocked + " closeThread=" + closeThread.get()
        + " handleOpen=" + handle.isOpen() + " reservations=" + io.getActiveResourceReservations()
        + " pending=" + io.getPendingCleanupObligations() + " cleanupWorkers=" + io.getActiveCleanupWorkers());
      release.countDown();
      System.out.println("accepted=" + result.get(2, TimeUnit.SECONDS) + " closedAfterRelease=" + !handle.isOpen());
      if (blocked) throw new AssertionError("Caller performs native close synchronously after shutdown");
    } finally {
      release.countDown(); caller.shutdown(); caller.awaitTermination(3, TimeUnit.SECONDS);
      handle.close(); io.shutdown(); Files.deleteIfExists(file);
    }
  }
}
