import com.dippie.moviercm.controller.MediaStreamController;
import com.dippie.moviercm.entity.*;
import com.dippie.moviercm.repository.*;
import com.dippie.moviercm.service.*;
import org.springframework.core.io.*;
import org.springframework.mock.web.MockHttpServletResponse;
import java.lang.reflect.Proxy;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

// Reviewer-only deterministic filesystem stall; no Drive/DB/user processes.
public class DRIVE_01_IoRepro {
  public static void main(String[] args) throws Exception {
    Path root=Files.createTempDirectory("codex-drive-io-");
    Files.write(root.resolve("clip.bin"),new byte[]{1,2,3});
    var entered=new CountDownLatch(1); var release=new CountDownLatch(1);
    var drive=new DriveMediaStorageAdapter(root.toString()) {
      @Override public Resource getResource(String p) {
        entered.countDown();
        try {release.await();} catch(InterruptedException e){Thread.currentThread().interrupt();}
        return super.getResource(p);
      }
    };
    var d=new MediaAsset("review-drive","review-movie","feature","drive","clip.bin","v1","video/mp4",3L,null,true,true);
    var l=new MediaAsset("review-local","review-local-movie","feature","local","clip.bin","v1","video/mp4",3L,null,true,true);
    var movie=Movie.builder().id("review-movie").title("Review").year(2026).rating(8.0).genres("Animation").build();
    var repo=(MediaAssetRepository)Proxy.newProxyInstance(MediaAssetRepository.class.getClassLoader(),new Class[]{MediaAssetRepository.class},(p,m,a)->{
      if(m.getName().equals("findByIdAndIsAvailableTrue"))return Optional.of(a[0].equals(d.getId())?d:l);
      if(m.getName().equals("findByMovieIdAndIsAvailableTrue"))return List.of(d);
      throw new UnsupportedOperationException(m.getName());
    });
    var movies=(MovieRepository)Proxy.newProxyInstance(MovieRepository.class.getClassLoader(),new Class[]{MovieRepository.class},(p,m,a)->{
      if(m.getName().equals("findById"))return Optional.of(movie);
      throw new UnsupportedOperationException(m.getName());
    });
    var svc=new MediaStreamService(movies,repo,new LocalMediaStorageAdapter(root.toString()),drive,1);
    var ctl=new MediaStreamController(svc); var worker=Executors.newSingleThreadExecutor();
    try {
      var pending=worker.submit(()->{try{ctl.streamMedia(d.getId(),null,new MockHttpServletResponse());}catch(Exception e){throw new RuntimeException(e);}});
      if(!entered.await(2,TimeUnit.SECONDS))throw new AssertionError("Did not enter production IO");
      try {pending.get(500,TimeUnit.MILLISECONDS);throw new AssertionError("Stall did not reproduce");}
      catch(TimeoutException expected){System.out.println("REPRO blockedDriveRequestStillPending=true active="+svc.getActiveStreamCount());}
      var localResponse=new MockHttpServletResponse(); ctl.streamMedia(l.getId(),null,localResponse);
      System.out.println("REPRO healthyLocalWhileDriveBlocked="+localResponse.getStatus());
      if(localResponse.getStatus()!=429)throw new AssertionError("Expected shared-admission starvation");
      release.countDown(); pending.get(2,TimeUnit.SECONDS);
      Files.delete(root.resolve("clip.bin"));
      System.out.println("REPRO missingFeatureDescriptorAdvertised="+svc.getMediaDescriptor(movie.getId()).isHasFeature());
      try {drive.getResource("clip.bin");}catch(Exception e){System.out.println("REPRO streamAfterDescriptor="+e.getClass().getSimpleName());}
    } finally {release.countDown();worker.shutdownNow();worker.awaitTermination(3,TimeUnit.SECONDS);}
  }
}
