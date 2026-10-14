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
import jakarta.servlet.ServletOutputStream;
import jakarta.servlet.WriteListener;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.servlet.http.HttpServletResponseWrapper;
import org.apache.catalina.connector.ClientAbortException;
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
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DriveFaultIsolationTest - Storage Fault Isolation and Concurrency Accounting")
public class DriveFaultIsolationTest {

    private Map<String, Movie> movieStorage;
    private Map<String, MediaAsset> assetStorage;
    private Map<String, List<MediaAsset>> assetsByMovieId;

    private MovieRepository movieRepository;
    private MediaAssetRepository mediaAssetRepository;

    private StubLocalMediaStorageAdapter localStorageAdapter;
    private StubDriveMediaStorageAdapter driveStorageAdapter;

    private MediaStreamService mediaStreamService;
    private MediaStreamController mediaStreamController;

    private Movie localMovie;
    private MediaAsset localFeatureAsset;
    private MediaAsset localTrailerAsset;

    private Movie driveMovie;
    private MediaAsset driveFeatureAsset;
    private MediaAsset driveTrailerAsset;

    @BeforeEach
    void setUp() {
        movieStorage = new ConcurrentHashMap<>();
        assetStorage = new ConcurrentHashMap<>();
        assetsByMovieId = new ConcurrentHashMap<>();

        movieRepository = createMovieRepoStub(movieStorage);
        mediaAssetRepository = createMediaAssetRepoStub(assetStorage, assetsByMovieId);

        localStorageAdapter = new StubLocalMediaStorageAdapter();
        driveStorageAdapter = new StubDriveMediaStorageAdapter();

        mediaStreamService = new MediaStreamService(
                movieRepository,
                mediaAssetRepository,
                localStorageAdapter,
                driveStorageAdapter,
                5
        );
        mediaStreamController = new MediaStreamController(mediaStreamService);

        // Seed Local entities
        localMovie = Movie.builder()
                .id("movie-local-01")
                .title("Local Cinema Classic")
                .year(2025)
                .rating(8.7)
                .genres("Action,Thriller")
                .videoUrl("/videos/fallback-local.mp4")
                .build();
        movieStorage.put(localMovie.getId(), localMovie);

        localFeatureAsset = new MediaAsset(
                "ast-local-feat-01",
                "movie-local-01",
                "feature",
                "local",
                "movies/local-01/feature.mp4",
                "v1",
                "video/mp4",
                1048576L,
                120.0,
                true,
                true
        );
        assetStorage.put(localFeatureAsset.getId(), localFeatureAsset);

        localTrailerAsset = new MediaAsset(
                "ast-local-trl-01",
                "movie-local-01",
                "trailer",
                "local",
                "movies/local-01/trailer.mp4",
                "v1",
                "video/mp4",
                262144L,
                15.0,
                true,
                true
        );
        assetStorage.put(localTrailerAsset.getId(), localTrailerAsset);
        assetsByMovieId.put("movie-local-01", new CopyOnWriteArrayList<>(List.of(localFeatureAsset, localTrailerAsset)));

        // Seed Drive entities
        driveMovie = Movie.builder()
                .id("movie-drive-01")
                .title("Cloud Drive Feature")
                .year(2026)
                .rating(9.1)
                .genres("Sci-Fi,Documentary")
                .videoUrl("/videos/fallback-drive.mp4")
                .build();
        movieStorage.put(driveMovie.getId(), driveMovie);

        driveFeatureAsset = new MediaAsset(
                "ast-drive-feat-01",
                "movie-drive-01",
                "feature",
                "drive",
                "movies/drive-01/feature.mp4",
                "v1",
                "video/mp4",
                5242880L,
                180.0,
                true,
                true
        );
        assetStorage.put(driveFeatureAsset.getId(), driveFeatureAsset);

        driveTrailerAsset = new MediaAsset(
                "ast-drive-trl-01",
                "movie-drive-01",
                "trailer",
                "drive",
                "movies/drive-01/trailer.mp4",
                "v1",
                "video/mp4",
                524288L,
                30.0,
                true,
                true
        );
        assetStorage.put(driveTrailerAsset.getId(), driveTrailerAsset);
        assetsByMovieId.put("movie-drive-01", new CopyOnWriteArrayList<>(List.of(driveFeatureAsset, driveTrailerAsset)));
    }

    @Nested
    @DisplayName("1. Local vs Drive Storage Fault Isolation Tests")
    class FaultIsolationTests {

        @Test
        @DisplayName("When Drive is offline (isAvailable==false), local assets continue to operate 100% normally")
        void testLocalAssetsUnaffectedByDriveOutage() throws IOException {
            // Drive is disconnected / offline
            driveStorageAdapter.setAvailable(false);
            assertFalse(driveStorageAdapter.isAvailable());

            // Local storage is healthy
            localStorageAdapter.setAvailable(true);
            assertTrue(localStorageAdapter.isAvailable());

            // 1. Local descriptor resolution succeeds completely
            MediaDescriptorResponse descriptor = mediaStreamService.getMediaDescriptor("movie-local-01");
            assertNotNull(descriptor);
            assertEquals("movie-local-01", descriptor.getMovieId());
            assertTrue(descriptor.isHasFeature(), "Local movie feature must remain available");
            assertTrue(descriptor.isHasTrailer(), "Local movie trailer must remain available");
            assertNotNull(descriptor.getFeature());
            assertEquals("ast-local-feat-01", descriptor.getFeature().getAssetId());
            assertEquals("/api/media/stream/ast-local-feat-01", descriptor.getFeature().getStreamUrl());

            // 2. Local asset retrieval succeeds
            MediaAsset fetchedAsset = mediaStreamService.getMediaAsset("ast-local-feat-01");
            assertEquals(localFeatureAsset, fetchedAsset);

            // 3. Local resource, length, and seekable channel open normally
            Resource resource = mediaStreamService.getMediaResource(localFeatureAsset);
            assertNotNull(resource);
            assertTrue(resource.contentLength() > 0);

            long length = mediaStreamService.getResourceLength(localFeatureAsset);
            assertEquals(1048576L, length);

            SeekableByteChannel channel = mediaStreamService.openMediaChannel(localFeatureAsset);
            assertNotNull(channel);
            assertTrue(channel.isOpen());
        }

        @Test
        @DisplayName("When Drive feature is requested but Drive is offline, throws MediaUnavailableException (503) instead of hasFeature=false")
        void testDriveFeatureThrows503WhenDriveOffline() {
            // Drive is offline
            driveStorageAdapter.setAvailable(false);
            assertFalse(driveStorageAdapter.isAvailable());

            // Calling getMediaDescriptor MUST throw MediaUnavailableException (503)
            // It MUST NOT return hasFeature = false (which would falsely mark the movie as lacking media)
            MediaUnavailableException ex = assertThrows(
                    MediaUnavailableException.class,
                    () -> mediaStreamService.getMediaDescriptor("movie-drive-01"),
                    "Must throw MediaUnavailableException (503) when Drive mount is offline"
            );

            assertTrue(ex.getMessage().contains("Google Drive") || ex.getMessage().contains("offline"),
                    "Exception message should mention Google Drive offline status: " + ex.getMessage());
        }

        @Test
        @DisplayName("When Drive trailer is requested but Drive is offline, throws MediaUnavailableException (503)")
        void testDriveTrailerThrows503WhenDriveOffline() {
            // Setup hybrid movie: local feature, drive trailer
            Movie hybridMovie = Movie.builder()
                    .id("movie-hybrid-01")
                    .title("Hybrid Movie")
                    .videoUrl("")
                    .build();
            movieStorage.put(hybridMovie.getId(), hybridMovie);
            assetsByMovieId.put("movie-hybrid-01", List.of(localFeatureAsset, driveTrailerAsset));

            driveStorageAdapter.setAvailable(false);

            MediaUnavailableException ex = assertThrows(
                    MediaUnavailableException.class,
                    () -> mediaStreamService.getMediaDescriptor("movie-hybrid-01"),
                    "Must throw MediaUnavailableException when trailer is hosted on offline Drive mount"
            );

            assertTrue(ex.getMessage().contains("Google Drive") || ex.getMessage().contains("offline"));
        }

        @Test
        @DisplayName("When Drive is restored online, Drive movie descriptor succeeds with hasFeature=true")
        void testDriveDescriptorSucceedsWhenDriveOnline() {
            driveStorageAdapter.setAvailable(true);
            assertTrue(driveStorageAdapter.isAvailable());

            MediaDescriptorResponse descriptor = mediaStreamService.getMediaDescriptor("movie-drive-01");
            assertNotNull(descriptor);
            assertTrue(descriptor.isHasFeature());
            assertTrue(descriptor.isHasTrailer());
            assertEquals("ast-drive-feat-01", descriptor.getFeature().getAssetId());
            assertEquals("/api/media/stream/ast-drive-feat-01", descriptor.getFeature().getStreamUrl());
        }
    }

    @Nested
    @DisplayName("2. Stream Permit Accounting and Concurrency Invariant Tests")
    class ConcurrencyPermitTests {

        @Test
        @DisplayName("Permit acquisition and release accurately track activeStreamCount and enforce maxConcurrentStreams")
        void testPermitAccountingAndBoundEnforcement() {
            mediaStreamService.setMaxConcurrentStreams(3);
            assertEquals(0, mediaStreamService.getActiveStreamCount());
            assertEquals(0, mediaStreamService.getTotalRejectedCount());

            // Acquire permit 1
            assertTrue(mediaStreamService.acquireStreamPermit());
            assertEquals(1, mediaStreamService.getActiveStreamCount());

            // Acquire permit 2
            assertTrue(mediaStreamService.acquireStreamPermit());
            assertEquals(2, mediaStreamService.getActiveStreamCount());

            // Acquire permit 3 (reaches max limit)
            assertTrue(mediaStreamService.acquireStreamPermit());
            assertEquals(3, mediaStreamService.getActiveStreamCount());

            // Permit 4 exceeds max limit: MUST be rejected
            assertFalse(mediaStreamService.acquireStreamPermit(), "Permit exceeding max concurrent streams must be denied");
            assertEquals(3, mediaStreamService.getActiveStreamCount(), "Active stream count must remain at max limit on rejection");
            assertEquals(1, mediaStreamService.getTotalRejectedCount());

            // Permit 5 exceeds max limit: MUST be rejected
            assertFalse(mediaStreamService.acquireStreamPermit());
            assertEquals(3, mediaStreamService.getActiveStreamCount());
            assertEquals(2, mediaStreamService.getTotalRejectedCount());

            // Release 1 permit
            mediaStreamService.releaseStreamPermit();
            assertEquals(2, mediaStreamService.getActiveStreamCount());

            // Now a new permit can be acquired
            assertTrue(mediaStreamService.acquireStreamPermit());
            assertEquals(3, mediaStreamService.getActiveStreamCount());

            // Release all permits down to 0
            mediaStreamService.releaseStreamPermit();
            mediaStreamService.releaseStreamPermit();
            mediaStreamService.releaseStreamPermit();
            assertEquals(0, mediaStreamService.getActiveStreamCount());

            // Extra release does not cause underflow below 0
            mediaStreamService.releaseStreamPermit();
            assertEquals(0, mediaStreamService.getActiveStreamCount(), "Counter must not underflow below zero");
        }
    }

    @Nested
    @DisplayName("3. Mid-Stream Cancellation & Exception Permit Recovery Tests")
    class CancellationRecoveryTests {

        @Test
        @DisplayName("ClientAbortException during streaming releases permit and restores activeStreamCount to baseline")
        void testClientAbortExceptionReleasesPermit() {
            assertEquals(0, mediaStreamService.getActiveStreamCount());

            boolean acquired = mediaStreamService.acquireStreamPermit();
            assertTrue(acquired);
            assertEquals(1, mediaStreamService.getActiveStreamCount());

            try {
                // Simulate Tomcat ClientAbortException when client drops video connection
                throw new ClientAbortException("java.io.IOException: An established connection was aborted by the software in your host machine");
            } catch (ClientAbortException e) {
                assertNotNull(e.getMessage());
            } finally {
                mediaStreamService.releaseStreamPermit();
            }

            assertEquals(0, mediaStreamService.getActiveStreamCount(), "Permit must be released on client abort");
        }

        @Test
        @DisplayName("IOException during streaming releases permit and restores activeStreamCount to baseline")
        void testGenericIOExceptionReleasesPermit() {
            assertEquals(0, mediaStreamService.getActiveStreamCount());

            boolean acquired = mediaStreamService.acquireStreamPermit();
            assertTrue(acquired);
            assertEquals(1, mediaStreamService.getActiveStreamCount());

            try {
                throw new IOException("Broken pipe / Connection reset by peer");
            } catch (IOException e) {
                assertNotNull(e.getMessage());
            } finally {
                mediaStreamService.releaseStreamPermit();
            }

            assertEquals(0, mediaStreamService.getActiveStreamCount(), "Permit must be released on generic IOException");
        }

        @Test
        @DisplayName("Controller streamMedia invocation releasing permit on ClientAbortException from response output stream")
        void testControllerStreamMediaReleasesPermitOnClientAbort(@TempDir Path tempMountDir) throws IOException {
            assertEquals(0, mediaStreamService.getActiveStreamCount());

            Path sampleVideo = tempMountDir.resolve("sample.mp4");
            byte[] videoContent = "STREAM_TEST_CHUNK_DATA_FOR_ABORT_VERIFICATION_0123456789".getBytes(StandardCharsets.UTF_8);
            Files.write(sampleVideo, videoContent);

            driveStorageAdapter.setMockResource(new ByteArrayResource(videoContent));
            driveStorageAdapter.setMockLength(videoContent.length);
            driveStorageAdapter.setMockChannel(FileChannel.open(sampleVideo, StandardOpenOption.READ));

            // Mock response whose OutputStream throws ClientAbortException on write
            MockHttpServletResponse rawResponse = new MockHttpServletResponse();
            HttpServletResponse abortResponse = new HttpServletResponseWrapper(rawResponse) {
                private final ServletOutputStream sos = new ServletOutputStream() {
                    @Override
                    public boolean isReady() {
                        return true;
                    }

                    @Override
                    public void setWriteListener(WriteListener writeListener) {
                    }

                    @Override
                    public void write(int b) throws IOException {
                        throw new ClientAbortException("Simulated socket write disconnection");
                    }

                    @Override
                    public void write(byte[] b, int off, int len) throws IOException {
                        throw new ClientAbortException("Simulated socket write disconnection");
                    }
                };

                @Override
                public ServletOutputStream getOutputStream() {
                    return sos;
                }
            };

            // Invoke streamMedia: must throw ClientAbortException
            assertThrows(ClientAbortException.class, () ->
                    mediaStreamController.streamMedia("ast-drive-feat-01", null, abortResponse));

            // Permit MUST be released in finally block: count is back to 0
            assertEquals(0, mediaStreamService.getActiveStreamCount(),
                    "Controller must unconditionally release permit in finally block even on ClientAbortException");

            // Subsequent requests must be able to acquire permits normally
            assertTrue(mediaStreamService.acquireStreamPermit());
            assertEquals(1, mediaStreamService.getActiveStreamCount());
            mediaStreamService.releaseStreamPermit();
            assertEquals(0, mediaStreamService.getActiveStreamCount());
        }

        @Test
        @DisplayName("Controller streamMedia invocation releasing permit on generic IOException from response output stream")
        void testControllerStreamMediaReleasesPermitOnGenericIOException(@TempDir Path tempMountDir) throws IOException {
            assertEquals(0, mediaStreamService.getActiveStreamCount());

            Path sampleVideo = tempMountDir.resolve("sample_ioe.mp4");
            byte[] videoContent = "STREAM_TEST_DATA_IOE".getBytes(StandardCharsets.UTF_8);
            Files.write(sampleVideo, videoContent);

            driveStorageAdapter.setMockResource(new ByteArrayResource(videoContent));
            driveStorageAdapter.setMockLength(videoContent.length);
            driveStorageAdapter.setMockChannel(FileChannel.open(sampleVideo, StandardOpenOption.READ));

            MockHttpServletResponse rawResponse = new MockHttpServletResponse();
            HttpServletResponse ioeResponse = new HttpServletResponseWrapper(rawResponse) {
                private final ServletOutputStream sos = new ServletOutputStream() {
                    @Override
                    public boolean isReady() {
                        return true;
                    }

                    @Override
                    public void setWriteListener(WriteListener writeListener) {
                    }

                    @Override
                    public void write(int b) throws IOException {
                        throw new IOException("Connection reset by peer");
                    }

                    @Override
                    public void write(byte[] b, int off, int len) throws IOException {
                        throw new IOException("Connection reset by peer");
                    }
                };

                @Override
                public ServletOutputStream getOutputStream() {
                    return sos;
                }
            };

            assertThrows(IOException.class, () ->
                    mediaStreamController.streamMedia("ast-drive-feat-01", null, ioeResponse));

            assertEquals(0, mediaStreamService.getActiveStreamCount(),
                    "Controller must release permit on generic IOException");
        }

        @Test
        @DisplayName("Concurrent multi-threaded streams with mixed aborts and completions preserve counter integrity")
        void testConcurrentPermitIntegrityUnderStress() throws InterruptedException, ExecutionException {
            int maxPermits = 4;
            int totalTasks = 40;
            mediaStreamService.setMaxConcurrentStreams(maxPermits);

            ExecutorService executor = Executors.newFixedThreadPool(16);
            AtomicInteger peakActive = new AtomicInteger(0);
            AtomicInteger completedNormally = new AtomicInteger(0);
            AtomicInteger abortedMidStream = new AtomicInteger(0);
            AtomicInteger rejectedCount = new AtomicInteger(0);

            List<Future<?>> futures = new ArrayList<>();

            for (int i = 0; i < totalTasks; i++) {
                final int taskId = i;
                futures.add(executor.submit(() -> {
                    if (!mediaStreamService.acquireStreamPermit()) {
                        rejectedCount.incrementAndGet();
                        return;
                    }

                    try {
                        int active = mediaStreamService.getActiveStreamCount();
                        peakActive.updateAndGet(current -> Math.max(current, active));

                        // Simulate streaming latency
                        Thread.sleep(15);

                        // Every 3rd task simulates a client disconnection
                        if (taskId % 3 == 0) {
                            abortedMidStream.incrementAndGet();
                            throw new ClientAbortException("Client dropped connection in task " + taskId);
                        }

                        completedNormally.incrementAndGet();
                    } catch (ClientAbortException ignored) {
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                    } finally {
                        mediaStreamService.releaseStreamPermit();
                    }
                }));
            }

            for (Future<?> f : futures) {
                f.get();
            }

            executor.shutdown();
            assertTrue(executor.awaitTermination(10, TimeUnit.SECONDS));

            // Invariants
            assertTrue(peakActive.get() <= maxPermits,
                    "Peak active streams (" + peakActive.get() + ") must never exceed max allowed permits (" + maxPermits + ")");
            assertTrue(completedNormally.get() > 0, "Some streams should have completed normally");
            assertTrue(abortedMidStream.get() > 0, "Some streams should have aborted");
            assertEquals(0, mediaStreamService.getActiveStreamCount(),
                    "Active stream counter must return strictly to 0 after all threads finish");
        }
    }

    // --- Helper Stubs ---

    static class StubLocalMediaStorageAdapter extends LocalMediaStorageAdapter {
        private boolean available = true;
        private Resource mockResource;
        private long mockLength = 1048576L;
        private SeekableByteChannel mockChannel;

        public StubLocalMediaStorageAdapter() {
            super("./media");
        }

        public void setAvailable(boolean available) {
            this.available = available;
        }

        public void setMockResource(Resource mockResource) {
            this.mockResource = mockResource;
        }

        public void setMockLength(long mockLength) {
            this.mockLength = mockLength;
        }

        public void setMockChannel(SeekableByteChannel mockChannel) {
            this.mockChannel = mockChannel;
        }

        @Override
        public boolean isAvailable() {
            return available;
        }

        @Override
        public Resource getResource(String relativePath) {
            return mockResource != null ? mockResource : new ByteArrayResource("LOCAL_VIDEO".getBytes(StandardCharsets.UTF_8));
        }

        @Override
        public long getResourceLength(String relativePath) {
            return mockLength;
        }

        @Override
        public SeekableByteChannel openChannel(String relativePath) {
            return mockChannel != null ? mockChannel : new MemorySeekableByteChannel("LOCAL_VIDEO_BYTES".getBytes(StandardCharsets.UTF_8));
        }
    }

    static class StubDriveMediaStorageAdapter extends DriveMediaStorageAdapter {
        private boolean available = true;
        private Resource mockResource;
        private long mockLength = 5242880L;
        private SeekableByteChannel mockChannel;

        public StubDriveMediaStorageAdapter() {
            super("M:\\DippieMedia");
        }

        public void setAvailable(boolean available) {
            this.available = available;
        }

        public void setMockResource(Resource mockResource) {
            this.mockResource = mockResource;
        }

        public void setMockLength(long mockLength) {
            this.mockLength = mockLength;
        }

        public void setMockChannel(SeekableByteChannel mockChannel) {
            this.mockChannel = mockChannel;
        }

        @Override
        public boolean isAvailable() {
            return available;
        }

        @Override
        public Resource getResource(String relativePath) {
            if (!available) {
                throw new MediaUnavailableException("Drive is offline");
            }
            return mockResource != null ? mockResource : new ByteArrayResource("DRIVE_VIDEO".getBytes(StandardCharsets.UTF_8));
        }

        @Override
        public long getResourceLength(String relativePath) {
            if (!available) {
                throw new MediaUnavailableException("Drive is offline");
            }
            return mockLength;
        }

        @Override
        public SeekableByteChannel openChannel(String relativePath) {
            if (!available) {
                throw new MediaUnavailableException("Drive is offline");
            }
            return mockChannel != null ? mockChannel : new MemorySeekableByteChannel("DRIVE_VIDEO_BYTES".getBytes(StandardCharsets.UTF_8));
        }
    }

    static class MemorySeekableByteChannel implements SeekableByteChannel {
        private final byte[] data;
        private long position = 0;
        private boolean open = true;

        public MemorySeekableByteChannel(byte[] data) {
            this.data = data;
        }

        @Override
        public int read(ByteBuffer dst) {
            if (!open || position >= data.length) return -1;
            int remaining = dst.remaining();
            int toRead = (int) Math.min(remaining, data.length - position);
            dst.put(data, (int) position, toRead);
            position += toRead;
            return toRead;
        }

        @Override
        public int write(ByteBuffer src) {
            throw new UnsupportedOperationException("Read-only channel");
        }

        @Override
        public long position() {
            return position;
        }

        @Override
        public SeekableByteChannel position(long newPosition) {
            this.position = newPosition;
            return this;
        }

        @Override
        public long size() {
            return data.length;
        }

        @Override
        public SeekableByteChannel truncate(long size) {
            throw new UnsupportedOperationException("Read-only channel");
        }

        @Override
        public boolean isOpen() {
            return open;
        }

        @Override
        public void close() {
            open = false;
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
