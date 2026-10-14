import com.dippie.moviercm.service.storage.*;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Production executor, deterministic late-completing file open, no Drive or DB.
public class DRIVE_F01_late_open {
  public static void main(String[] args)throws Exception {
    var io=new DriveIoExecutor(40,40,1,new DriveCircuitBreaker(5,100));
    var release=new CountDownLatch(1);var opened=new AtomicReference<FileChannel>();
    Path file=Files.createTempFile("codex-drive-late-",".bin");
    try {
      try {io.executeMetadata(()->{
        while(true){try{release.await();break;}catch(InterruptedException ignored){}}
        FileChannel ch=FileChannel.open(file,StandardOpenOption.READ);opened.set(ch);return ch;
      });}catch(Exception e){System.out.println("REPRO caller="+e.getClass().getSimpleName());}
      release.countDown();
      long until=System.nanoTime()+TimeUnit.SECONDS.toNanos(2);
      while((opened.get()==null||io.getActualOutstandingWorkers()!=0)&&System.nanoTime()<until)Thread.sleep(5);
      System.out.println("REPRO lateOpenChannelStillOpen="+(opened.get()!=null&&opened.get().isOpen())+" actualWorkers="+io.getActualOutstandingWorkers());
      if(opened.get()==null)throw new AssertionError("Late open was not exercised");
    }finally{release.countDown();if(opened.get()!=null)opened.get().close();io.shutdown();Files.deleteIfExists(file);}
  }
}
