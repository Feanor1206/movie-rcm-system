package com.dippie.moviercm;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.service.MediaStreamService;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.context.ServletWebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.ResponseEntity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

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

        ConfigurableApplicationContext ctx = new SpringApplicationBuilder(
                MovieRcmApplication.class,
                WalkthroughSecurityConfig.class,
                WalkthroughDiagnosticsController.class
        )
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
                .poster("")
                .backdrop("")
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

    public static class WalkthroughSecurityConfig {
        @Bean
        @Order(Ordered.HIGHEST_PRECEDENCE)
        public SecurityFilterChain walkthroughTestFilterChain(HttpSecurity http) throws Exception {
            http.securityMatcher(org.springframework.security.web.util.matcher.AntPathRequestMatcher.antMatcher("/api/test/**"))
                    .csrf(csrf -> csrf.disable())
                    .authorizeHttpRequests(auth -> auth.anyRequest().permitAll());
            return http.build();
        }
    }

    @RestController
    @RequestMapping("/api/test/media")
    public static class WalkthroughDiagnosticsController {
        private final MediaStreamService mediaStreamService;

        public WalkthroughDiagnosticsController(MediaStreamService mediaStreamService) {
            this.mediaStreamService = mediaStreamService;
        }

        @GetMapping("/metrics")
        public ResponseEntity<Map<String, Object>> getMetrics() {
            return ResponseEntity.ok(Map.of(
                    "activeStreams", mediaStreamService.getActiveStreamCount(),
                    "maxConcurrentStreams", mediaStreamService.getMaxConcurrentStreams(),
                    "totalRejectedCount", mediaStreamService.getTotalRejectedCount()
            ));
        }

        @PostMapping("/max-concurrent-streams")
        public ResponseEntity<Map<String, Object>> setMaxConcurrent(@RequestParam("limit") int limit) {
            mediaStreamService.setMaxConcurrentStreams(limit);
            return ResponseEntity.ok(Map.of(
                    "maxConcurrentStreams", mediaStreamService.getMaxConcurrentStreams()
            ));
        }

        @PostMapping("/gate/arm")
        public ResponseEntity<Map<String, Object>> armGate() {
            MediaStreamService.setTestStreamGate(new java.util.concurrent.CountDownLatch(1));
            return ResponseEntity.ok(Map.of("gateArmed", true));
        }

        @PostMapping("/gate/release")
        public ResponseEntity<Map<String, Object>> releaseGate() {
            java.util.concurrent.CountDownLatch gate = MediaStreamService.getTestStreamGate();
            MediaStreamService.setTestStreamGate(null);
            if (gate != null) gate.countDown();
            return ResponseEntity.ok(Map.of("gateReleased", true));
        }
    }
}
