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
import com.dippie.moviercm.service.storage.DriveCircuitBreaker;
import com.dippie.moviercm.service.storage.DriveIoExecutor;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.core.io.Resource;
import org.springframework.http.ResponseEntity;
import org.springframework.mock.web.MockHttpServletResponse;

import java.io.IOException;
import java.lang.reflect.Proxy;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DriveIoDeadlineTest - Drive IO Deadlines, Worker Capacity & Bulkhead Verification")
public class DriveIoDeadlineTest {

    private Map<String, Movie> movieStorage;
    private Map<String, MediaAsset> assetStorage;
    private Map<String, List<MediaAsset>> assetsByMovieId;

    private MovieRepository movieRepository;
    private MediaAssetRepository mediaAssetRepository;

    private LocalMediaStorageAdapter localStorageAdapter;
    private DriveMediaStorageAdapter driveStorageAdapter;

    private MediaStreamService mediaStreamService;
    private MediaStreamController mediaStreamController;

    private Movie driveMovie;
    private MediaAsset driveAsset;

    private ExecutorService executorService;
    private DriveIoExecutor ioExecutor;
    private DriveCircuitBreaker circuitBreaker;

    private final int MAX_WORKERS = 2;
    private final long METADATA_TIMEOUT_MS = 200;
    private final long READ_TIMEOUT_MS = 300;

    @BeforeEach
    void setUp(@TempDir Path tempLocalDir, @TempDir Path tempDriveDir) throws IOException {
        executorService = Executors.newCachedThreadPool();

        movieStorage = new ConcurrentHashMap<>();
        assetStorage = new ConcurrentHashMap<>();
        assetsByMovieId = new ConcurrentHashMap<>();

        movieRepository = createMovieRepoStub(movieStorage);
        mediaAssetRepository = createMediaAssetRepoStub(assetStorage, assetsByMovieId);

        // Seed Drive media file
        Path driveFile = tempDriveDir.resolve("drive_deadline_clip.mp4");
        byte[] driveData = "DRIVE_DEADLINE_TEST_BYTES_0123456789".getBytes(StandardCharsets.UTF_8);
        Files.write(driveFile, driveData);

        circuitBreaker = new DriveCircuitBreaker(5, 5000);
        ioExecutor = new DriveIoExecutor(
                METADATA_TIMEOUT_MS,
                READ_TIMEOUT_MS,
                MAX_WORKERS,
                circuitBreaker
        );

        localStorageAdapter = new LocalMediaStorageAdapter(tempLocalDir.toString());
        driveStorageAdapter = new DriveMediaStorageAdapter(tempDriveDir.toString(), ioExecutor);

        mediaStreamService = new MediaStreamService(
                movieRepository,
                mediaAssetRepository,
                localStorageAdapter,
                driveStorageAdapter,
                10,
                MAX_WORKERS
        );
        mediaStreamController = new MediaStreamController(mediaStreamService);

        driveMovie = Movie.builder()
                .id("movie-drive-deadline-01")
                .title("Deadline Movie")
                .year(2026)
                .rating(9.0)
                .genres("Sci-Fi")
                .videoUrl("")
                .build();
        movieStorage.put(driveMovie.getId(), driveMovie);

        driveAsset = new MediaAsset(
                "ast-drive-deadline-01",
                "movie-drive-deadline-01",
                "feature",
                "drive",
                "drive_deadline_clip.mp4",
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
        if (ioExecutor != null) {
            ioExecutor.shutdown();
        }
        if (executorService != null) {
            executorService.shutdownNow();
            executorService.awaitTermination(3, TimeUnit.SECONDS);
        }
    }

    @Nested
    @DisplayName("1. Deadline Enforcement & Timeout Tests")
    class DeadlineEnforcementTests {

        @Test
        @DisplayName("Stalled IO read operation times out after deadline and throws MediaUnavailableException")
        void testStalledReadOperationTimesOut() {
            CountDownLatch entered = new CountDownLatch(1);
            CountDownLatch release = new CountDownLatch(1);

            long startTime = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () ->
                    ioExecutor.executeRead(() -> {
                        entered.countDown();
                        release.await();
                        return 42;
                    })
            );
            long elapsed = System.currentTimeMillis() - startTime;

            assertTrue(elapsed >= READ_TIMEOUT_MS, "Operation should have waited at least readTimeoutMs (" + READ_TIMEOUT_MS + "ms)");
            assertTrue(elapsed < READ_TIMEOUT_MS + 1000, "Operation should have timed out promptly without indefinite blocking");
            assertTrue(ex.getMessage().contains("vượt quá thời gian chờ") || ex.getMessage().contains("read"),
                    "Exception must clearly describe timeout: " + ex.getMessage());

            release.countDown();
        }

        @Test
        @DisplayName("Stalled metadata operation times out after deadline and throws MediaUnavailableException")
        void testStalledMetadataOperationTimesOut() {
            CountDownLatch entered = new CountDownLatch(1);
            CountDownLatch release = new CountDownLatch(1);

            long startTime = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () ->
                    ioExecutor.executeMetadata(() -> {
                        entered.countDown();
                        release.await();
                        return "metadata-result";
                    })
            );
            long elapsed = System.currentTimeMillis() - startTime;

            assertTrue(elapsed >= METADATA_TIMEOUT_MS);
            assertTrue(elapsed < METADATA_TIMEOUT_MS + 1000);
            assertTrue(ex.getMessage().contains("vượt quá thời gian chờ") || ex.getMessage().contains("metadata"),
                    "Exception must describe metadata timeout: " + ex.getMessage());

            release.countDown();
        }
    }

    @Nested
    @DisplayName("2. Interruption-Ignoring Task & Worker Accounting Tests")
    class InterruptionIgnoringWorkerTests {

        @Test
        @DisplayName("Worker capacity (actualOutstandingWorkers) is retained when caller times out while task ignores interruption")
        void testWorkerCapacityRetainedAfterCallerTimeout() throws Exception {
            CountDownLatch taskStarted = new CountDownLatch(1);
            CountDownLatch taskRelease = new CountDownLatch(1);

            // Submit an interruption-ignoring task directly through ioExecutor
            Future<?> callerFuture = executorService.submit(() -> {
                return ioExecutor.executeRead(() -> {
                    taskStarted.countDown();
                    // Simulates uninterruptible kernel / WinFsp IO: catches and ignores interrupt
                    while (true) {
                        try {
                            if (taskRelease.await(10, TimeUnit.MILLISECONDS)) {
                                break;
                            }
                        } catch (InterruptedException e) {
                            // Intentionally ignores interruption
                        }
                    }
                    return "completed";
                });
            });

            // Wait until task actually enters execution
            assertTrue(taskStarted.await(2, TimeUnit.SECONDS), "Task should have started execution");

            // Verify worker is registered in executor
            assertEquals(1, ioExecutor.getActualOutstandingWorkers());

            // Await caller future: MUST encounter MediaUnavailableException due to timeout
            ExecutionException ee = assertThrows(ExecutionException.class, () -> callerFuture.get());
            assertInstanceOf(MediaUnavailableException.class, ee.getCause());

            // CRITICAL INVARIANT: Even though caller timed out, the background worker is STILL active and ignoring interrupt!
            // Therefore, actualOutstandingWorkers MUST STILL BE 1 (not decremented prematurely)!
            assertEquals(1, ioExecutor.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must remain 1 until the kernel IO task physically finishes");

            // Now release the latch to allow the task to physically exit
            taskRelease.countDown();

            // Wait for worker count to return to 0
            boolean returnedToZero = waitForWorkerCount(0, 3000);
            assertTrue(returnedToZero, "Worker count must return to 0 once background thread physically terminates");
        }

        @Test
        @DisplayName("Fast-rejection occurs immediately without spawning new threads when outstanding workers reach maxWorkers")
        void testFastRejectionWhenCapacityExceeded() throws Exception {
            CountDownLatch task1Started = new CountDownLatch(1);
            CountDownLatch task2Started = new CountDownLatch(1);
            CountDownLatch releaseAll = new CountDownLatch(1);

            // Fill all worker slots (MAX_WORKERS = 2) with interruption-ignoring tasks
            executorService.submit(() -> ioExecutor.executeRead(() -> {
                task1Started.countDown();
                while (!releaseAll.await(10, TimeUnit.MILLISECONDS)) {}
                return 1;
            }));
            assertTrue(task1Started.await(2, TimeUnit.SECONDS));

            executorService.submit(() -> ioExecutor.executeRead(() -> {
                task2Started.countDown();
                while (!releaseAll.await(10, TimeUnit.MILLISECONDS)) {}
                return 2;
            }));
            assertTrue(task2Started.await(2, TimeUnit.SECONDS));

            // Wait for both workers to be registered
            assertEquals(2, ioExecutor.getActualOutstandingWorkers(), "Both worker slots must be occupied");

            // A 3rd request arrives: MUST be fast-rejected immediately without waiting for timeout!
            long startMs = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () ->
                    ioExecutor.executeRead(() -> "task3")
            );
            long durationMs = System.currentTimeMillis() - startMs;

            assertTrue(durationMs < 100, "Fast rejection must occur immediately (< 100ms), not after timeout");
            assertTrue(ex.getMessage().contains("đạt giới hạn tối đa") || ex.getMessage().contains("2"),
                    "Exception message must mention worker limit reached: " + ex.getMessage());

            // Invariant: Peak outstanding workers must never exceed MAX_WORKERS (2)
            assertEquals(2, ioExecutor.getActualOutstandingWorkers(), "Worker count must remain bounded at 2");

            // Release workers and verify full recovery
            releaseAll.countDown();
            boolean recovered = waitForWorkerCount(0, 3000);
            assertTrue(recovered, "All workers must return to 0 after release");

            // Now subsequent request succeeds normally
            int result = ioExecutor.executeRead(() -> 999);
            assertEquals(999, result);
        }
    }

    @Nested
    @DisplayName("3. Circuit Breaker Protection Tests")
    class CircuitBreakerTests {

        @Test
        @DisplayName("Circuit breaker trips to OPEN after consecutive failures and fails fast")
        void testCircuitBreakerTripsAndFailsFast() {
            DriveCircuitBreaker breaker = ioExecutor.getCircuitBreaker();
            assertEquals(DriveCircuitBreaker.State.CLOSED, breaker.getState());

            // Cause 5 consecutive timeout failures
            for (int i = 0; i < 5; i++) {
                assertThrows(MediaUnavailableException.class, () ->
                        ioExecutor.executeMetadata(() -> {
                            Thread.sleep(METADATA_TIMEOUT_MS + 50);
                            return null;
                        })
                );
            }

            // Circuit breaker MUST now be OPEN
            assertEquals(DriveCircuitBreaker.State.OPEN, breaker.getState());
            assertTrue(breaker.isOpen());

            // Next request MUST fail immediately with Circuit Breaker OPEN exception without submitting to pool
            long start = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () ->
                    ioExecutor.executeMetadata(() -> "fast-fail")
            );
            long elapsed = System.currentTimeMillis() - start;

            assertTrue(elapsed < 20, "Circuit breaker open must fail fast (< 20ms)");
            assertTrue(ex.getMessage().contains("Circuit Breaker OPEN"),
                    "Exception message should mention Circuit Breaker OPEN: " + ex.getMessage());

            // Reset circuit breaker and verify recovery
            breaker.reset();
            assertEquals(DriveCircuitBreaker.State.CLOSED, breaker.getState());
            String recovered = ioExecutor.executeMetadata(() -> "recovered-value");
            assertEquals("recovered-value", recovered);
        }
    }

    @Nested
    @DisplayName("4. Controller & Descriptor Metadata Deadline Protection Tests")
    class ControllerMetadataDeadlineTests {

        @Test
        @DisplayName("HEAD request and getMediaDescriptor do not hang servlet threads when Drive metadata stalls")
        void testHeadAndDescriptorDoNotHangOnStall() throws Exception {
            CountDownLatch stallLatch = new CountDownLatch(1);

            DriveIoExecutor stallingExecutor = new DriveIoExecutor(150, 150, 2, new DriveCircuitBreaker());
            DriveMediaStorageAdapter stallingAdapter = new DriveMediaStorageAdapter("target/fake-drive-mount", stallingExecutor) {
                @Override
                public boolean isAvailable() {
                    return stallingExecutor.executeMetadata(() -> {
                        stallLatch.await();
                        return true;
                    });
                }

                @Override
                public long getResourceLength(String relativePath) {
                    return stallingExecutor.executeMetadata(() -> {
                        stallLatch.await();
                        return 1000L;
                    });
                }
            };

            MediaStreamService stallingService = new MediaStreamService(
                    movieRepository,
                    mediaAssetRepository,
                    localStorageAdapter,
                    stallingAdapter,
                    5,
                    2
            );
            MediaStreamController stallingController = new MediaStreamController(stallingService);

            // 1. getMediaDescriptor for Drive movie must timeout promptly and throw MediaUnavailableException (503)
            long startDesc = System.currentTimeMillis();
            assertThrows(MediaUnavailableException.class, () ->
                    stallingService.getMediaDescriptor(driveMovie.getId()));
            long elapsedDesc = System.currentTimeMillis() - startDesc;
            assertTrue(elapsedDesc < 1000, "Descriptor must timeout promptly without hanging servlet thread");

            // 2. HEAD request must timeout promptly and throw MediaUnavailableException (503)
            long startHead = System.currentTimeMillis();
            assertThrows(MediaUnavailableException.class, () ->
                    stallingController.getStreamHeaders(driveAsset.getId()));
            long elapsedHead = System.currentTimeMillis() - startHead;
            assertTrue(elapsedHead < 1000, "HEAD request must timeout promptly without hanging servlet thread");

            stallLatch.countDown();
            stallingExecutor.shutdown();
        }
    }

    private boolean waitForWorkerCount(int expected, long maxWaitMs) throws InterruptedException {
        long deadline = System.currentTimeMillis() + maxWaitMs;
        while (System.currentTimeMillis() < deadline) {
            if (ioExecutor.getActualOutstandingWorkers() == expected) {
                return true;
            }
            Thread.sleep(20);
        }
        return ioExecutor.getActualOutstandingWorkers() == expected;
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
