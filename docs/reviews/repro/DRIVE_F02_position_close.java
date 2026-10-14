import com.dippie.moviercm.service.storage.*;
import java.io.*;
import java.nio.*;
import java.nio.channels.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

// Simulates uninterruptible native read and close waiting for that read, using production wrapper.
public class DRIVE_F02_position_close {
  static class BlockingFile extends FileChannel {
    final CountDownLatch release=new CountDownLatch(1);
    void waitForRelease(){while(true){try{release.await();return;}catch(InterruptedException ignored){}}}
    public int read(ByteBuffer b){return -1;}
    protected void implCloseChannel(){waitForRelease();}
    public long position(){return 0;}
    public FileChannel position(long n){waitForRelease();return this;}
    public long size(){return 1;}
    public FileChannel truncate(long n){throw new UnsupportedOperationException();}
    public void force(boolean m){}
    public long transferTo(long p,long c,WritableByteChannel t){throw new UnsupportedOperationException();}
    public long transferFrom(ReadableByteChannel s,long p,long c){throw new UnsupportedOperationException();}
    public int read(ByteBuffer b,long p){return read(b);}
    public int write(ByteBuffer b,long p){throw new UnsupportedOperationException();}
    public int write(ByteBuffer b){throw new UnsupportedOperationException();}
    public long read(ByteBuffer[] b,int o,int l){throw new UnsupportedOperationException();}
    public long write(ByteBuffer[] b,int o,int l){throw new UnsupportedOperationException();}
    public MappedByteBuffer map(MapMode m,long p,long s){throw new UnsupportedOperationException();}
    public FileLock lock(long p,long s,boolean sh){throw new UnsupportedOperationException();}
    public FileLock tryLock(long p,long s,boolean sh){throw new UnsupportedOperationException();}
  }
  public static void main(String[] args)throws Exception {
    var raw=new BlockingFile();var io=new DriveIoExecutor(40,40,1,new DriveCircuitBreaker());
    var caller=Executors.newSingleThreadExecutor();var readFailed=new AtomicBoolean();
    var future=caller.submit(()->{
      try(var channel=new DriveSeekableByteChannel(raw,io)) {
        try{channel.position(1);}catch(IOException expected){readFailed.set(true);}
      }catch(IOException e){throw new RuntimeException(e);}
    });
    try {
      try{future.get(250,TimeUnit.MILLISECONDS);}catch(TimeoutException expected){}
      System.out.println("REPRO positionDeadlineFired="+readFailed.get()+" callerStillBlockedInClose="+!future.isDone()+" ioWorkers="+io.getActualOutstandingWorkers());
      if(!readFailed.get()||future.isDone())throw new AssertionError("Expected production close stall");
    }finally{raw.release.countDown();future.get(2,TimeUnit.SECONDS);caller.shutdownNow();io.shutdown();}
  }
}

