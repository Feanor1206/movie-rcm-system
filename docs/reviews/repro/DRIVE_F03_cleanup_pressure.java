import com.dippie.moviercm.service.storage.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Reviewer: actual production cleanup API, small temporary file, owned handles/latches only.
public class DRIVE_F03_cleanup_pressure {
  public static void main(String[] args)throws Exception {
    var io=new DriveIoExecutor(50,50,1,new DriveCircuitBreaker(1000,100));
    var holdMain=new CountDownLatch(1);var entered=new CountDownLatch(1);var holdClose=new CountDownLatch(1);
    var caller=Executors.newSingleThreadExecutor();var closed=new AtomicInteger();var handles=new ArrayList<FileChannel>();
    Path file=Files.createTempFile("codex-drive-cleanup-",".bin");
    try {
      var active=caller.submit(()->{try{io.executeRead(()->{entered.countDown();while(true){try{holdMain.await();break;}catch(InterruptedException ignored){}}return 0;});}catch(Exception expected){}});
      if(!entered.await(2,TimeUnit.SECONDS))throw new AssertionError("No main worker");
      for(int i=0;i<300;i++){
        var ch=FileChannel.open(file,StandardOpenOption.READ);handles.add(ch);
        io.executeCleanupAsync(()->{while(true){try{holdClose.await();break;}catch(InterruptedException ignored){}}ch.close();closed.incrementAndGet();});
      }
      System.out.println("REPRO submittedCleanup=300 trackedMainWorkers="+io.getActualOutstandingWorkers());
      holdClose.countDown();
      long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(2);
      while(closed.get()<300&&System.nanoTime()<until)Thread.sleep(10);
      long stillOpen=handles.stream().filter(FileChannel::isOpen).count();
      System.out.println("REPRO closedAfterRelease="+closed.get()+" leakedOpenHandles="+stillOpen);
      if(stillOpen==0)throw new AssertionError("Repro no longer applies");
      holdMain.countDown();active.get(2,TimeUnit.SECONDS);
    }finally{holdMain.countDown();holdClose.countDown();for(var ch:handles)ch.close();io.shutdown();caller.shutdownNow();caller.awaitTermination(2,TimeUnit.SECONDS);Files.deleteIfExists(file);}
  }
}
