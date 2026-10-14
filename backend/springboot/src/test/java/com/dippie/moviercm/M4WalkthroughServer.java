package com.dippie.moviercm;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.context.ServletWebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Isolated Spring Boot test server for real HTTP Range media walkthrough and benchmark.
 * Runs on dynamic loopback port with in-memory H2 database and temporary media root.
 */
public class M4WalkthroughServer {

    public static void main(String[] args) throws Exception {
        String mediaRoot = System.getProperty("walkthrough.media.root");
        if (mediaRoot == null || mediaRoot.trim().isEmpty()) {
            mediaRoot = "target/test-media";
        }
        Path mediaPath = Paths.get(mediaRoot).toAbsolutePath().normalize();

        String dbName = "m4_walkthrough_" + System.nanoTime();

        ConfigurableApplicationContext ctx = new SpringApplicationBuilder(MovieRcmApplication.class)
                .run(
                        "--spring.profiles.active=test",
                        "--server.address=127.0.0.1",
                        "--server.port=0",
                        "--spring.datasource.url=jdbc:h2:mem:" + dbName + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;NON_KEYWORDS=YEAR,USER",
                        "--spring.jpa.hibernate.ddl-auto=create-drop",
                        "--spring.sql.init.mode=never",
                        "--app.seed.enabled=false",
                        "--app.media.root=" + mediaPath.toString(),
                        "--app.media.drive-mount="
                );

        MovieRepository movieRepo = ctx.getBean(MovieRepository.class);
        MediaAssetRepository assetRepo = ctx.getBean(MediaAssetRepository.class);

        // 1. Save Walkthrough Movie
        Movie movie = Movie.builder()
                .id("m4-walkthrough-movie")
                .title("Walkthrough Cinema Special")
                .year(2026)
                .rating(9.2)
                .runtime("0h 20m")
                .genres("Animation,Sci-Fi")
                .description("A stunning synthetic animated space voyage used to verify real HTTP Range video streaming.")
                .poster("https://images.unsplash.com/photo-1534447677768-be436bb09401?w=800")
                .backdrop("https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=1600")
                .videoUrl("/videos/fallback-walkthrough.mp4")
                .build();
        movieRepo.save(movie);

        // 2. Check synthetic video file length
        Path videoFile = mediaPath.resolve("synthetic/walkthrough_feature.mp4");
        long fileLength = Files.exists(videoFile) ? Files.size(videoFile) : 350000L;

        // 3. Save Public Feature Asset
        MediaAsset feature = new MediaAsset(
                "ast-walkthrough-feat",
                "m4-walkthrough-movie",
                "feature",
                "local",
                "synthetic/walkthrough_feature.mp4",
                "v1",
                "video/mp4",
                fileLength,
                20.0,
                true,
                true
        );
        assetRepo.save(feature);

        // 4. Save Private Asset (for isolation verification)
        MediaAsset privateAsset = new MediaAsset(
                "ast-walkthrough-private",
                "m4-walkthrough-movie",
                "trailer",
                "local",
                "synthetic/walkthrough_feature.mp4",
                "v1",
                "video/mp4",
                fileLength,
                20.0,
                false,
                true
        );
        assetRepo.save(privateAsset);

        int port = ((ServletWebServerApplicationContext) ctx).getWebServer().getPort();
        System.out.println("WALKTHROUGH_BACKEND_PORT=" + port);
        System.out.flush();

        // Keep running until stdin EOF or termination
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(System.in))) {
            while (reader.readLine() != null) {
                // wait for external stop signal
            }
        } catch (Exception ignored) {
        } finally {
            ctx.close();
            System.out.println("WALKTHROUGH_BACKEND_STOPPED");
        }
    }
}
