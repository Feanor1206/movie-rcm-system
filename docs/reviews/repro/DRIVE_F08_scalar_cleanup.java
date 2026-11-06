import com.dippie.moviercm.service.storage.*;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.io.IOException;
import java.util.concurrent.atomic.*;

/** Boundary-error repro; own temp native handle, no DB/server/Drive/GPU. */
class DRIVE_F08_scalar_cleanup {
  public static void main(String[] args) throws Exception {
    var ex=new DriveIoExecutor(1000,1000,1,1,new DriveCircuitBreaker(100,10));
    var permit=ex.acquireReservation();
    Path file=Files.createTempFile("codex-f08-scalar-", ".bin");
    var handle=FileChannel.open(file,StandardOpenOption.READ);
    var attempts=new AtomicInteger();
    AutoCloseable forbidden=()->{
      if(attempts.incrementAndGet()==1) throw new IOException("Injected before native close");
      handle.close();
    };
    try {
      Throwable error=null;
      try { ex.executeMetadata(()->forbidden); } catch(Throwable t){error=t;}
      boolean lost=handle.isOpen()&&attempts.get()==1&&ex.getRetainedFailedResources().isEmpty();
      System.out.printf("{\"error\":\"%s\",\"nativeOpen\":%s,\"closeAttempts\":%d,\"retained\":%d,\"lostCleanup\":%s}%n",
        error==null?"none":error.getClass().getSimpleName(),handle.isOpen(),attempts.get(),
        ex.getRetainedFailedResources().size(),lost);
      if(lost) throw new AssertionError("Scalar contract rejection swallowed a failed native close");
    } finally {handle.close();permit.release();ex.shutdown();Files.deleteIfExists(file);}
  }
}
