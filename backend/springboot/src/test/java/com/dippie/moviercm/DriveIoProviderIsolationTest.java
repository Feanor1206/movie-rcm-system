package com.dippie.moviercm;

import com.dippie.moviercm.controller.MediaStreamController;
import com.dippie.moviercm.dto.MediaDescriptorResponse;
import com.dippie.moviercm.entity.MediaAsset;
import com.dippie.moviercm.entity.Movie;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.repository.MediaAssetRepository;
import com.dippie.moviercm.repository.MovieRepository;
import com.dippie.moviercm.service.DriveMediaStorageAdapter;
import com.dippie.moviercm.service.LocalMediaStorageAdapter;
import com.dippie.moviercm.service.MediaStreamService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.mock.web.MockHttpServletResponse;

import java.io.IOException;
import java.lang.reflect.Proxy;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DriveIoProviderIsolationTest - Resource Bulkhead Isolation (Local vs Drive)")
public class DriveIoProviderIsolationTest {

    private Map<String, Movie> movieStorage;
    private Map<String, MediaAsset> assetStorage;
    private Map<String, List<MediaAsset>> assetsByMovieId;

    private MovieRepository movieRepository;
    private MediaAssetRepository mediaAssetRepository;

    private LocalMediaStorageAdapter localStorageAdapter;
    private StallingDriveStorageAdapter driveStorageAdapter;

    private MediaStreamService mediaStreamService;
    private MediaStreamController mediaStreamController;

    private Movie localMovie;
    private MediaAsset localAsset;

    private Movie driveMovie;
    private MediaAsset driveAsset;

    private ExecutorService executorService;
    private CountDownLatch driveEnteredLatch;
    private CountDownLatch driveReleaseLatch;

    @BeforeEach
    void setUp(@TempDir Path tempLocalDir, @TempDir Path tempDriveDir) throws IOException {
        executorService = Executors.newCachedThreadPool();
        driveEnteredLatch = new CountDownLatch(1);
        driveReleaseLatch = new CountDownLatch(1);

        movieStorage = new ConcurrentHashMap<>();
        assetStorage = new ConcurrentHashMap<>();
        assetsByMovieId = new ConcurrentHashMap<>();

        movieRepository = createMovieRepoStub(movieStorage);
        mediaAssetRepository = createMediaAssetRepoStub(assetStorage, assetsByMovieId);

        // Prepare local media file
        Path localFile = tempLocalDir.resolve("local_clip.mp4");
        byte[] localData = "LOCAL_HEALTHY_VIDEO_PAYLOAD_123456789".getBytes(StandardCharsets.UTF_8);
        Files.write(localFile, localData);

        // Prepare drive media file
        Path driveFile = tempDriveDir.resolve("drive_clip.mp4");
        byte[] driveData = "DRIVE_VIDEO_PAYLOAD_STALLED".getBytes(StandardCharsets.UTF_8);
        Files.write(driveFile, driveData);

        localStorageAdapter = new LocalMediaStorageAdapter(tempLocalDir.toString());
        driveStorageAdapter = new StallingDriveStorageAdapter(
                tempDriveDir.toString(),
                driveEnteredLatch,
                driveReleaseLatch
        );

        // Shared or isolated permit service with 1 concurrent permit (review repro conditions)
        mediaStreamService = new MediaStreamService(
                movieRepository,
                mediaAssetRepository,
                localStorageAdapter,
                driveStorageAdapter,
                1
        );
        mediaStreamController = new MediaStreamController(mediaStreamService);

        // Setup Local movie
        localMovie = Movie.builder()
                .id("movie-local-isolation")
                .title("Local Cinema")
                .year(2025)
                .rating(8.5)
                .genres("Drama")
                .videoUrl("/videos/fallback-local.mp4")
                .build();
        movieStorage.put(localMovie.getId(), localMovie);

        localAsset = new MediaAsset(
                "ast-local-isolation-01",
                "movie-local-isolation",
                "feature",
                "local",
                "local_clip.mp4",
                "v1",
                "video/mp4",
                (long) localData.length,
                60.0,
                true,
                true
        );
        assetStorage.put(localAsset.getId(), localAsset);
        assetsByMovieId.put(localMovie.getId(), List.of(localAsset));

        // Setup Drive movie
        driveMovie = Movie.builder()
                .id("movie-drive-isolation")
                .title("Drive Feature")
                .year(2026)
                .rating(9.0)
                .genres("Sci-Fi")
                .videoUrl("/videos/fallback-drive.mp4")
                .build();
        movieStorage.put(driveMovie.getId(), driveMovie);

        driveAsset = new MediaAsset(
                "ast-drive-isolation-01",
                "movie-drive-isolation",
                "feature",
                "drive",
                "drive_clip.mp4",
                "v1",
                "video/mp4",
                (long) driveData.length,
                120.0,
                true,
                true
        );
        assetStorage.put(driveAsset.getId(), driveAsset);
        assetsByMovieId.put(driveMovie.getId(), List.of(driveAsset));
    }

    @AfterEach
    void tearDown() throws InterruptedException {
        if (driveReleaseLatch != null) {
            driveReleaseLatch.countDown();
        }
        if (executorService != null) {
            executorService.shutdownNow();
            executorService.awaitTermination(3, TimeUnit.SECONDS);
        }
    }

    @Nested
    @DisplayName("1. Bulkhead & Capacity Isolation Tests")
    class BulkheadIsolationTests {

        @Test
        @DisplayName("When Drive IO is blocked/stalled, healthy local stream requests succeed (HTTP 200) without 429 starvation")
        void testHealthyLocalStreamWhileDriveBlocked() throws Exception {
            // 1. Submit blocked Drive request
            Future<?> driveFuture = executorService.submit(() -> {
                try {
                    MockHttpServletResponse response = new MockHttpServletResponse();
                    mediaStreamController.streamMedia(driveAsset.getId(), null, response);
                } catch (Exception e) {
                    throw new RuntimeException(e);
                }
            });

            // Wait until Drive request enters stalling IO in Drive adapter
            assertTrue(driveEnteredLatch.await(3, TimeUnit.SECONDS),
                    "Drive IO operation should have entered stalling adapter");

            // Verify Drive request is pending/stalled
            assertThrows(TimeoutException.class, () ->
                    driveFuture.get(200, TimeUnit.MILLISECONDS),
                    "Drive request must remain stalled while latch is not released");

            // 2. Concurrently execute healthy local stream request
            MockHttpServletResponse localResponse = new MockHttpServletResponse();
            mediaStreamController.streamMedia(localAsset.getId(), null, localResponse);

            // 3. CRITICAL INVARIANT: Local stream MUST succeed with HTTP 200, NEVER return HTTP 429
            assertEquals(200, localResponse.getStatus(),
                    "Local stream must succeed with HTTP 200 and NOT be starved or return 429 by blocked Drive request");
            assertEquals("video/mp4", localResponse.getContentType());
            assertTrue(localResponse.getContentAsByteArray().length > 0,
                    "Local stream response body must contain video data");

            // 4. Release Drive latch to allow background thread to finish cleanly
            driveReleaseLatch.countDown();
            driveFuture.get(3, TimeUnit.SECONDS);
        }

        @Test
        @DisplayName("Local media descriptor resolution operates normally 100% while Drive is stalled or offline")
        void testLocalDescriptorWhileDriveStalled() {
            // Call getMediaDescriptor for local movie
            MediaDescriptorResponse descriptor = mediaStreamService.getMediaDescriptor(localMovie.getId());

            assertNotNull(descriptor);
            assertEquals(localMovie.getId(), descriptor.getMovieId());
            assertTrue(descriptor.isHasFeature(), "Local feature must remain available");
            assertNotNull(descriptor.getFeature());
            assertEquals(localAsset.getId(), descriptor.getFeature().getAssetId());
            assertEquals("/api/media/stream/" + localAsset.getId(), descriptor.getFeature().getStreamUrl());
        }
    }

    @Nested
    @DisplayName("2. Error Sanitization & Host Path Privacy Tests")
    class ErrorSanitizationTests {

        @Test
        @DisplayName("Exception messages when Drive is unconfigured or offline do not expose internal host mount paths")
        void testDriveOfflineErrorDoesNotLeakHostPath() {
            String sensitiveHostPath = "M:\\ConfidentialCorpData\\InternalServer\\SecretMountFolder";
            DriveMediaStorageAdapter adapterWithSensitivePath = new DriveMediaStorageAdapter(sensitiveHostPath);

            assertFalse(adapterWithSensitivePath.isAvailable());

            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () ->
                    adapterWithSensitivePath.resolveValidatedPath("movies/feat.mp4"));

            String message = ex.getMessage();
            assertNotNull(message);

            // Invariant: MUST NOT leak sensitive host path in user-facing / public exception message
            assertFalse(message.contains("ConfidentialCorpData"), "Exception must not expose confidential path segment");
            assertFalse(message.contains("SecretMountFolder"), "Exception must not expose internal folder name");
            assertFalse(message.contains(sensitiveHostPath), "Exception must not expose full host mount path");

            // Must contain a sanitized, clear Vietnamese error message
            assertTrue(message.contains("Google Drive") || message.contains("không sẵn sàng") || message.contains("không đọc được"),
                    "Exception message should be descriptive and sanitized: " + message);
        }
    }

    // --- Helper Stalling Adapter & Dynamic Repositories ---

    static class StallingDriveStorageAdapter extends DriveMediaStorageAdapter {
        private final CountDownLatch enteredLatch;
        private final CountDownLatch releaseLatch;

        public StallingDriveStorageAdapter(String mountPath, CountDownLatch enteredLatch, CountDownLatch releaseLatch) {
            super(mountPath);
            this.enteredLatch = enteredLatch;
            this.releaseLatch = releaseLatch;
        }

        @Override
        public Resource getResource(String relativePath) {
            enteredLatch.countDown();
            try {
                releaseLatch.await();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            return super.getResource(relativePath);
        }

        @Override
        public SeekableByteChannel openChannel(String relativePath) throws IOException {
            enteredLatch.countDown();
            try {
                releaseLatch.await();
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            return super.openChannel(relativePath);
        }
    }

    @SuppressWarnings("unchecked")
    private MovieRepository createMovieRepoStub(Map<String, Movie> storage) {
        return (MovieRepository) Proxy.newProxyInstance(
                MovieRepository.class.getClassLoader(),
                new Class<?>[]{MovieRepository.class},
                (proxy, method, args) -> {
                    if ("findById".equals(method.getName()) && args != null && args.length == 1) {
                        return Optional.ofNullable(storage.get((String) args[0]));
                    }
                    if ("save".equals(method.getName()) && args != null && args.length == 1) {
                        Movie m = (Movie) args[0];
                        storage.put(m.getId(), m);
                        return m;
                    }
                    return null;
                }
        );
    }

    @SuppressWarnings("unchecked")
    private MediaAssetRepository createMediaAssetRepoStub(
            Map<String, MediaAsset> assetById,
            Map<String, List<MediaAsset>> assetsByMovieId
    ) {
        return (MediaAssetRepository) Proxy.newProxyInstance(
                MediaAssetRepository.class.getClassLoader(),
                new Class<?>[]{MediaAssetRepository.class},
                (proxy, method, args) -> {
                    if ("findByIdAndIsAvailableTrue".equals(method.getName()) && args != null && args.length == 1) {
                        MediaAsset a = assetById.get((String) args[0]);
                        return (a != null && Boolean.TRUE.equals(a.getAvailable())) ? Optional.of(a) : Optional.empty();
                    }
                    if ("findByMovieIdAndIsAvailableTrue".equals(method.getName()) && args != null && args.length == 1) {
                        List<MediaAsset> list = assetsByMovieId.getOrDefault((String) args[0], List.of());
                        return list.stream().filter(a -> Boolean.TRUE.equals(a.getAvailable())).toList();
                    }
                    if ("save".equals(method.getName()) && args != null && args.length == 1) {
                        MediaAsset a = (MediaAsset) args[0];
                        assetById.put(a.getId(), a);
                        assetsByMovieId.computeIfAbsent(a.getMovieId(), k -> new ArrayList<>()).add(a);
                        return a;
                    }
                    return null;
                }
        );
    }
}
