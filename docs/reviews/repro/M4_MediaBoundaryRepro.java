import com.dippie.moviercm.MovieRcmApplication;
import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.service.LocalMediaStorageAdapter;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.context.ServletWebServerApplicationContext;
import java.net.URI;
import java.net.http.*;
import java.nio.file.*;
import java.time.Duration;
import java.util.Arrays;

/** Reviewer-only: isolated in-memory DB, temporary bytes, random loopback port. */
public class M4_MediaBoundaryRepro {
  public static void main(String[] args) throws Exception {
    Path root=Files.createTempDirectory("codex-m4-http-");
    byte[] expected="review-fixture-0123456789".getBytes();
    Files.write(root.resolve("clip.bin"),expected);
    try(var ctx=new SpringApplicationBuilder(MovieRcmApplication.class).run(
        "--spring.profiles.active=test", "--server.address=127.0.0.1", "--server.port=0",
        "--spring.datasource.url=jdbc:h2:mem:codex_m4_http_"+System.nanoTime()+";DB_CLOSE_DELAY=-1;MODE=PostgreSQL",
        "--spring.jpa.hibernate.ddl-auto=create-drop", "--spring.sql.init.mode=never",
        "--app.seed.enabled=false", "--app.media.root="+root)) {
      var movies=ctx.getBean(MovieRepository.class);
      var assets=ctx.getBean(MediaAssetRepository.class);
      movies.save(Movie.builder().id("codex-m4-movie").title("Reviewer fixture")
          .year(2026).rating(8.0).genres("Animation").build());
      for(boolean pub:new boolean[]{true,false}) assets.save(new MediaAsset(
          pub?"codex-public":"codex-private","codex-m4-movie",pub?"trailer":"feature",
          "local","clip.bin","v1","application/octet-stream",(long)expected.length,null,pub,true));
      int port=((ServletWebServerApplicationContext)ctx).getWebServer().getPort();
      var client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
      String base="http://127.0.0.1:"+port;
      for(String asset:new String[]{"codex-public","codex-private"}){
        for(String method:new String[]{"GET","HEAD"}){
          var request=HttpRequest.newBuilder(URI.create(base+"/api/media/stream/"+asset))
              .timeout(Duration.ofSeconds(5)).method(method,HttpRequest.BodyPublishers.noBody()).build();
          var response=client.send(request,HttpResponse.BodyHandlers.ofByteArray());
          System.out.println("REPRO asset="+asset+" guestMethod="+method+" status="+response.statusCode()
              +" bytes="+response.body().length+" cache="+response.headers().firstValue("Cache-Control").orElse(""));
          if(asset.equals("codex-public")&&method.equals("GET")&&!Arrays.equals(expected,response.body()))
            throw new AssertionError("Public fixture integrity mismatch");
        }
      }
      var descriptor=client.send(HttpRequest.newBuilder(URI.create(base+"/api/movies/codex-m4-movie/media-descriptor"))
          .timeout(Duration.ofSeconds(5)).build(),HttpResponse.BodyHandlers.ofString());
      System.out.println("REPRO guestDescriptor="+descriptor.statusCode()+" body="+descriptor.body());
      var range=client.send(HttpRequest.newBuilder(URI.create(base+"/api/media/stream/codex-public"))
          .header("Range","bytes=7-12").timeout(Duration.ofSeconds(5)).build(),HttpResponse.BodyHandlers.ofByteArray());
      System.out.println("REPRO publicRange="+range.statusCode()+" integrity="+Arrays.equals(Arrays.copyOfRange(expected,7,13),range.body()));
      Path missing=root.resolve("explicit-root-does-not-exist");
      var adapter=new LocalMediaStorageAdapter(missing.toString());
      System.out.println("REPRO configuredRoot="+missing+" actualRoot="+adapter.getNormalizedRoot());
    } finally {
      Files.deleteIfExists(root.resolve("clip.bin"));
      Files.deleteIfExists(root);
    }
  }
}
