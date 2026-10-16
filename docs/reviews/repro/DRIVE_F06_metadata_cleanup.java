import com.dippie.moviercm.service.storage.*;
import com.dippie.moviercm.exception.MediaUnavailableException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.io.IOException;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Reviewer repro: production source; own temp file, no DB/network/GPU/mount. */
class DRIVE_F06_metadata_cleanup {
  public static void main(String[] args) throws Exception {
    var executor = new DriveIoExecutor(100, 100, 1, 1, new DriveCircuitBreaker(100, 10));
    var permit = executor.acquireReservation();
    var entered = new CountDownLatch(1);
    var release = new CountDownLatch(1);
    var attempts = new AtomicInteger();
    var callerFailure = new AtomicReference<Throwable>();
    Path file = Files.createTempFile("codex-f06-metadata-", ".bin");
    var nativeHandle = FileChannel.open(file, StandardOpenOption.READ);
    AutoCloseable resource = () -> {
      if (attempts.incrementAndGet() == 1) throw new IOException("Injected before native close");
      nativeHandle.close();
    };
    var caller = new Thread(() -> {
      try {
        executor.executeWithTimeout(() -> {
          entered.countDown();
          while (release.getCount() != 0) {
            try { release.await(); } catch (InterruptedException ignored) { }
          }
          return resource;
        }, 150, "metadata-close-failure");
      } catch (Throwable t) { callerFailure.set(t); }
    });
    try {
      caller.start();
      if (!entered.await(2, TimeUnit.SECONDS)) throw new AssertionError("Worker not entered");
      caller.join(2000);
      if (caller.isAlive() || !(callerFailure.get() instanceof MediaUnavailableException))
        throw new AssertionError("Expected bounded caller timeout");
      release.countDown();
      long end = System.nanoTime() + TimeUnit.SECONDS.toNanos(2);
      while (executor.getActualOutstandingWorkers() != 0 && System.nanoTime() < end) Thread.sleep(5);
      boolean lost = attempts.get() == 1 && nativeHandle.isOpen()
        && executor.getRetainedFailedResources().isEmpty()
        && executor.getPendingCleanupObligations() == 0;
      System.out.printf("{\"closeAttempts\":%d,\"nativeOpen\":%s,\"active\":%d,\"pending\":%d,\"retained\":%d,\"lostCleanup\":%s}%n",
        attempts.get(), nativeHandle.isOpen(), executor.getActiveResourceReservations(),
        executor.getPendingCleanupObligations(), executor.getRetainedFailedResources().size(), lost);
      if (lost) throw new AssertionError("Confirmed: generic metadata close failure is dropped at full lifecycle budget");
    } finally {
      release.countDown(); caller.join(2000); nativeHandle.close();
      permit.release(); executor.shutdown(); Files.deleteIfExists(file);
    }
  }
}
