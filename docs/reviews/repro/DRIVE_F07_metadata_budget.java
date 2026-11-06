import com.dippie.moviercm.service.storage.*;
import com.dippie.moviercm.exception.MediaUnavailableException;
import java.nio.channels.FileChannel;
import java.nio.file.*;
import java.io.IOException;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

/** Production-source capacity repro; own temp files only, no DB/server/Drive/GPU. */
class DRIVE_F07_metadata_budget {
  public static void main(String[] args) throws Exception {
    var ex = new DriveIoExecutor(100,100,1,1,new DriveCircuitBreaker(1000,10));
    var permit = ex.acquireReservation();
    var paths = new ArrayList<Path>();
    var handles = new ArrayList<FileChannel>();
    try {
      for (int i=0; i<3; i++) {
        Path file=Files.createTempFile("codex-f07-budget-", ".bin"); paths.add(file);
        var handle=FileChannel.open(file,StandardOpenOption.READ); handles.add(handle);
        var release=new CountDownLatch(1); var entered=new CountDownLatch(1);
        var error=new AtomicReference<Throwable>();
        AutoCloseable resource=()->{throw new IOException("Injected before native close: "+handle.isOpen());};
        var caller=new Thread(()->{
          try { ex.executeWithTimeout(()->{
            entered.countDown();
            while(release.getCount()!=0) try{release.await();}catch(InterruptedException ignored){}
            return resource;
          },100,"metadata-resource"); } catch(Throwable t){error.set(t);}
        });
        try {
          caller.start();
          if(!entered.await(2,TimeUnit.SECONDS)) throw new AssertionError("Worker not entered");
          caller.join(2000);
          if(caller.isAlive()||!(error.get() instanceof MediaUnavailableException)) throw new AssertionError("Caller timeout missing");
        } finally {release.countDown();caller.join(2000);}
        long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(2);
        while(ex.getActualOutstandingWorkers()!=0&&System.nanoTime()<until) Thread.sleep(5);
        if(ex.getActualOutstandingWorkers()!=0) throw new AssertionError("Worker not finished");
      }
      int retained=ex.getRetainedFailedResources().size();
      long open=handles.stream().filter(FileChannel::isOpen).count();
      System.out.printf("{\"capacity\":1,\"active\":%d,\"pending\":%d,\"retained\":%d,\"nativeOpen\":%d}%n",
        ex.getActiveResourceReservations(),ex.getPendingCleanupObligations(),retained,open);
      if(retained>1) throw new AssertionError("Confirmed: retained native cleanup obligations exceed lifecycle capacity");
    } finally {
      for(var handle:handles) handle.close();
      permit.release();ex.shutdown();
      for(var path:paths) Files.deleteIfExists(path);
    }
  }
}
