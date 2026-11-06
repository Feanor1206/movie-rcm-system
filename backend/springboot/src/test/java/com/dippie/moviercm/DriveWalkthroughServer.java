package com.dippie.moviercm;

import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.service.DriveMediaStorageAdapter;
import com.dippie.moviercm.service.MediaStreamService;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.servlet.context.ServletWebServerApplicationContext;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.http.ResponseEntity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.util.matcher.AntPathRequestMatcher;
import org.springframework.web.bind.annotation.*;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Isolated Spring Boot test server for Google Drive mounted media walkthrough and benchmark.
 * Runs on dynamic loopback port with in-memory H2 database and temporary Drive mount directory.
 * Provides live mount/unmount simulation diagnostics at /api/test/drive/*.
 */
public class DriveWalkthroughServer {

    private static Path driveMountPath;
    private static Path offlineMountPath;
    private static final AtomicBoolean mountActive = new AtomicBoolean(true);

    public static void main(String[] args) throws Exception {
        String mountRoot = System.getProperty("walkthrough.drive.mount");
        if (mountRoot == null || mountRoot.trim().isEmpty()) {
            mountRoot = "target/test-drive-mount";
        }
        driveMountPath = Paths.get(mountRoot).toAbsolutePath().normalize();
        offlineMountPath = driveMountPath.getParent().resolve(driveMountPath.getFileName().toString() + "-offline");

        // Prepare initial Drive mount directory
        Files.createDirectories(driveMountPath.resolve("movies/m4-drive-movie/v1"));
        mountActive.set(true);

        // Copy synthetic test video into Drive mount only if not already present
        Path syntheticSource = Paths.get("target/test-media/synthetic/walkthrough_feature.mp4").toAbsolutePath().normalize();
        Path mediaFallback = Paths.get("../../media/synthetic/walkthrough_feature.mp4").toAbsolutePath().normalize();
        Path driveVideoTarget = driveMountPath.resolve("movies/m4-drive-movie/v1/feature.mp4");

        if (!Files.exists(driveVideoTarget)) {
            if (Files.exists(syntheticSource)) {
                Files.copy(syntheticSource, driveVideoTarget, StandardCopyOption.REPLACE_EXISTING);
            } else if (Files.exists(mediaFallback)) {
                Files.copy(mediaFallback, driveVideoTarget, StandardCopyOption.REPLACE_EXISTING);
            } else {
                byte[] dummyData = new byte[350000];
                for (int i = 0; i < dummyData.length; i++) {
                    dummyData[i] = (byte) ((i * 31 + 7) % 128);
                }
                Files.write(driveVideoTarget, dummyData);
            }
        }

        long fileLength = Files.size(driveVideoTarget);

        String dbName = "drive_walkthrough_" + System.nanoTime();

        ConfigurableApplicationContext ctx = new SpringApplicationBuilder(
                MovieRcmApplication.class,
                DriveWalkthroughSecurityConfig.class,
                DriveDiagnosticsController.class
        )
                .run(
                        "--spring.profiles.active=test,drive-walkthrough",
                        "--server.address=127.0.0.1",
                        "--server.port=0",
                        "--spring.datasource.url=jdbc:h2:mem:" + dbName + ";DB_CLOSE_DELAY=-1;MODE=PostgreSQL;NON_KEYWORDS=YEAR,USER",
                        "--spring.jpa.hibernate.ddl-auto=create-drop",
                        "--spring.sql.init.mode=never",
                        "--app.seed.enabled=false",
                        "--app.media.root=target/test-media",
                        "--app.media.drive-mount=" + driveMountPath.toString()
                );

        MovieRepository movieRepo = ctx.getBean(MovieRepository.class);
        MediaAssetRepository assetRepo = ctx.getBean(MediaAssetRepository.class);

        // 1. Save Walkthrough Movie (m4-drive-movie)
        Movie driveMovie = Movie.builder()
                .id("m4-drive-movie")
                .title("Drive Walkthrough Cinema Special")
                .year(2026)
                .rating(9.3)
                .runtime("0h 20m")
                .genres("Animation,Sci-Fi")
                .description("A stunning synthetic animated space voyage streamed directly from Google Drive Windows mount.")
                .poster("")
                .backdrop("")
                .videoUrl("/videos/fallback-walkthrough.mp4")
                .build();
        movieRepo.save(driveMovie);

        // 2. Also save m4-walkthrough-movie for backward-compatibility with existing frontend routes
        Movie m4Movie = Movie.builder()
                .id("m4-walkthrough-movie")
                .title("Walkthrough Cinema Special (Drive)")
                .year(2026)
                .rating(9.3)
                .runtime("0h 20m")
                .genres("Animation,Sci-Fi")
                .description("A stunning synthetic animated space voyage streamed directly from Google Drive Windows mount.")
                .poster("")
                .backdrop("")
                .videoUrl("/videos/fallback-walkthrough.mp4")
                .build();
        movieRepo.save(m4Movie);

        // 3. Save Public Feature Assets with storageProvider = "drive"
        MediaAsset featDrive = new MediaAsset(
                "ast-drive-walkthrough-feat",
                "m4-drive-movie",
                "feature",
                "drive",
                "movies/m4-drive-movie/v1/feature.mp4",
                "v1",
                "video/mp4",
                fileLength,
                20.0,
                true,
                true
        );
        assetRepo.save(featDrive);

        MediaAsset featM4 = new MediaAsset(
                "ast-drive-m4-feat",
                "m4-walkthrough-movie",
                "feature",
                "drive",
                "movies/m4-drive-movie/v1/feature.mp4",
                "v1",
                "video/mp4",
                fileLength,
                20.0,
                true,
                true
        );
        assetRepo.save(featM4);

        // 4. Save Public Trailer Asset with storageProvider = "drive"
        MediaAsset trailerDrive = new MediaAsset(
                "ast-drive-walkthrough-trl",
                "m4-drive-movie",
                "trailer",
                "drive",
                "movies/m4-drive-movie/v1/feature.mp4",
                "v1",
                "video/mp4",
                fileLength,
                20.0,
                true,
                true
        );
        assetRepo.save(trailerDrive);

        MediaAsset trailerM4 = new MediaAsset(
                "ast-drive-m4-trl",
                "m4-walkthrough-movie",
                "trailer",
                "drive",
                "movies/m4-drive-movie/v1/feature.mp4",
                "v1",
                "video/mp4",
                fileLength,
                20.0,
                true,
                true
        );
        assetRepo.save(trailerM4);

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
            // Restore mount folder if still in offline state
            if (Files.exists(offlineMountPath)) {
                try {
                    Files.move(offlineMountPath, driveMountPath, StandardCopyOption.REPLACE_EXISTING);
                } catch (Exception ignored) {
                }
            }
            System.out.println("WALKTHROUGH_BACKEND_STOPPED");
        }
    }

    @Configuration
    @Profile("drive-walkthrough")
    public static class DriveWalkthroughSecurityConfig {
        @Bean("driveWalkthroughSecurityFilterChain")
        @Order(Ordered.HIGHEST_PRECEDENCE)
        public SecurityFilterChain driveWalkthroughFilterChain(HttpSecurity http) throws Exception {
            http.securityMatcher(AntPathRequestMatcher.antMatcher("/api/test/**"))
                    .csrf(csrf -> csrf.disable())
                    .authorizeHttpRequests(auth -> auth.anyRequest().permitAll());
            return http.build();
        }
    }

    @RestController
    @RequestMapping("/api/test/drive")
    @Profile("drive-walkthrough")
    public static class DriveDiagnosticsController {
        private final DriveMediaStorageAdapter driveStorageAdapter;
        private final MediaStreamService mediaStreamService;

        public DriveDiagnosticsController(DriveMediaStorageAdapter driveStorageAdapter, MediaStreamService mediaStreamService) {
            this.driveStorageAdapter = driveStorageAdapter;
            this.mediaStreamService = mediaStreamService;
        }

        @PostMapping("/unmount")
        @GetMapping("/unmount")
        public synchronized ResponseEntity<Map<String, Object>> unmountDrive() {
            try {
                if (Files.exists(driveMountPath)) {
                    Files.move(driveMountPath, offlineMountPath, StandardCopyOption.REPLACE_EXISTING);
                }
                mountActive.set(false);
                return ResponseEntity.ok(Map.of(
                        "status", "UNMOUNTED",
                        "mounted", false,
                        "adapterAvailable", driveStorageAdapter.isAvailable(),
                        "message", "Simulated Drive mount disconnect (directory unmounted)"
                ));
            } catch (IOException e) {
                return ResponseEntity.internalServerError().body(Map.of(
                        "status", "ERROR",
                        "error", e.getMessage()
                ));
            }
        }

        @PostMapping("/mount")
        @GetMapping("/mount")
        public synchronized ResponseEntity<Map<String, Object>> mountDrive() {
            try {
                if (Files.exists(offlineMountPath)) {
                    Files.move(offlineMountPath, driveMountPath, StandardCopyOption.REPLACE_EXISTING);
                } else if (!Files.exists(driveMountPath)) {
                    Files.createDirectories(driveMountPath.resolve("movies/m4-drive-movie/v1"));
                }
                mountActive.set(true);
                return ResponseEntity.ok(Map.of(
                        "status", "MOUNTED",
                        "mounted", true,
                        "adapterAvailable", driveStorageAdapter.isAvailable(),
                        "message", "Simulated Drive mount restored"
                ));
            } catch (IOException e) {
                return ResponseEntity.internalServerError().body(Map.of(
                        "status", "ERROR",
                        "error", e.getMessage()
                ));
            }
        }

        @GetMapping("/status")
        public ResponseEntity<Map<String, Object>> getDriveStatus() {
            return ResponseEntity.ok(Map.of(
                    "mounted", mountActive.get(),
                    "mountPathExists", Files.exists(driveMountPath),
                    "adapterAvailable", driveStorageAdapter.isAvailable()
            ));
        }

        @GetMapping("/metrics")
        public ResponseEntity<Map<String, Object>> getMetrics() {
            int active = mediaStreamService.getActiveDriveStreamCount() + mediaStreamService.getActiveStreamCount();
            return ResponseEntity.ok(Map.of(
                    "activeStreams", active,
                    "activeDriveStreams", mediaStreamService.getActiveDriveStreamCount(),
                    "maxConcurrentStreams", mediaStreamService.getMaxConcurrentDriveStreams(),
                    "totalRejectedCount", mediaStreamService.getTotalDriveRejectedCount()
            ));
        }

        @PostMapping("/max-concurrent-streams")
        public ResponseEntity<Map<String, Object>> setMaxConcurrent(@RequestParam("limit") int limit) {
            mediaStreamService.setMaxConcurrentDriveStreams(limit);
            mediaStreamService.setMaxConcurrentStreams(limit);
            return ResponseEntity.ok(Map.of(
                    "maxConcurrentStreams", mediaStreamService.getMaxConcurrentDriveStreams()
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
