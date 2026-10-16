package com.dippie.moviercm;

import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.service.DriveMediaStorageAdapter;
import com.dippie.moviercm.service.storage.DriveCircuitBreaker;
import com.dippie.moviercm.service.storage.DriveIoExecutor;
import com.dippie.moviercm.service.storage.DriveResourceReservation;
import com.dippie.moviercm.service.storage.DriveSeekableByteChannel;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.SeekableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

/**
 * DRIVE-01-F04 / R1 Cleanup Queue Saturation & Backpressure Test Suite.
 *
 * Verifies:
 * 1. Cleanup queue saturation and fail-fast rejection (no silent discard like F03).
 * 2. Backpressure rejecting new open / reservation when cleanup lane is saturated.
 * 3. Exactly-once execution and strict conservation law: accepted = closed + currently owned.
 * 4. Negative dropped-cleanup detection: unaccepted cleanups are never reported as accepted.
 * 5. Main worker saturation with idle cleanup lane (L-06).
 * 6. Reviewer reproduction scale with 300 real FileChannel handles (L-07).
 * 7. Full recovery after latch release with all 4 metric lanes returning to baseline 0 (L-11).
 */
@DisplayName("DriveCleanupQueueSaturationTest - Cleanup Queue Saturation, Backpressure & Conservation Suite")
public class DriveCleanupQueueSaturationTest {

    @TempDir
    Path tempDir;

    private final List<DriveIoExecutor> managedExecutors = new CopyOnWriteArrayList<>();
    private final List<ExecutorService> managedCallerPools = new CopyOnWriteArrayList<>();
    private final List<FileChannel> managedFileChannels = new CopyOnWriteArrayList<>();
    private final List<CountDownLatch> managedLatches = new CopyOnWriteArrayList<>();

    @BeforeEach
    void setUp() {
        managedExecutors.clear();
        managedCallerPools.clear();
        managedFileChannels.clear();
        managedLatches.clear();
    }

    @AfterEach
    void tearDown() {
        // Release all latches first so blocked background threads can exit
        for (CountDownLatch latch : managedLatches) {
            try {
                while (latch.getCount() > 0) {
                    latch.countDown();
                }
            } catch (Throwable ignored) {}
        }

        // Shut down test-managed DriveIoExecutors
        for (DriveIoExecutor exec : managedExecutors) {
            try {
                if (exec != null && !exec.isShutdown()) {
                    exec.shutdown();
                }
            } catch (Throwable ignored) {}
        }

        // Shut down test-managed caller pools
        for (ExecutorService pool : managedCallerPools) {
            try {
                if (pool != null && !pool.isShutdown()) {
                    pool.shutdownNow();
                    pool.awaitTermination(2, TimeUnit.SECONDS);
                }
            } catch (Throwable ignored) {}
        }

        // Close any lingering raw channels
        for (FileChannel ch : managedFileChannels) {
            try {
                if (ch != null && ch.isOpen()) {
                    ch.close();
                }
            } catch (Throwable ignored) {}
        }
    }

    // =========================================================================================
    // Helper Classes
    // =========================================================================================

    /**
     * AutoCloseable that records exact close counts, signals completion latches,
     * and optionally executes arbitrary actions on close.
     */
    static class TrackedAutoCloseable implements AutoCloseable {
        private final String id;
        private final AtomicInteger closeCount = new AtomicInteger(0);
        private final CountDownLatch closedLatch = new CountDownLatch(1);
        private final Runnable closeAction;

        TrackedAutoCloseable(String id) {
            this(id, null);
        }

        TrackedAutoCloseable(String id, Runnable closeAction) {
            this.id = id;
            this.closeAction = closeAction;
        }

        @Override
        public void close() {
            try {
                if (closeAction != null) {
                    closeAction.run();
                }
            } finally {
                closeCount.incrementAndGet();
                closedLatch.countDown();
            }
        }

        public int getCloseCount() {
            return closeCount.get();
        }

        public boolean isClosed() {
            return closeCount.get() > 0;
        }

        public boolean awaitClosed(long timeout, TimeUnit unit) throws InterruptedException {
            return closedLatch.await(timeout, unit);
        }

        public String getId() {
            return id;
        }
    }

    private boolean waitForCondition(Callable<Boolean> condition, long maxWaitMs) throws Exception {
        long deadline = System.currentTimeMillis() + maxWaitMs;
        while (System.currentTimeMillis() < deadline) {
            if (Boolean.TRUE.equals(condition.call())) {
                return true;
            }
            Thread.sleep(15);
        }
        return Boolean.TRUE.equals(condition.call());
    }

    // =========================================================================================
    // Test 1: testCleanupQueueSaturationAndRejection
    // =========================================================================================

    @Test
    @DisplayName("1. testCleanupQueueSaturationAndRejection - Submitting cleanups up to capacity returns true, beyond returns false (no silent discard)")
    void testCleanupQueueSaturationAndRejection() throws Exception {
        final int CLEANUP_QUEUE_CAP = 10;
        final int MAX_WORKERS = 2;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(100, 10000);
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_QUEUE_CAP, breaker);
        managedExecutors.add(executor);

        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS + 2);
        managedCallerPools.add(callerPool);

        CountDownLatch mainHoldLatch = new CountDownLatch(1);
        managedLatches.add(mainHoldLatch);
        CountDownLatch mainStartedLatch = new CountDownLatch(MAX_WORKERS);

        // 1. Occupy the main worker pool slots so all cleanup tasks route to the dedicated cleanup tier
        for (int i = 0; i < MAX_WORKERS; i++) {
            callerPool.submit(() -> {
                try {
                    executor.executeRead(() -> {
                        mainStartedLatch.countDown();
                        while (true) {
                            try {
                                if (mainHoldLatch.await(20, TimeUnit.MILLISECONDS)) {
                                    break;
                                }
                            } catch (InterruptedException ignored) {}
                        }
                        return 0;
                    });
                } catch (Exception ignored) {}
            });
        }
        assertTrue(mainStartedLatch.await(3, TimeUnit.SECONDS), "Main workers must be occupied");
        assertEquals(MAX_WORKERS, executor.getActualOutstandingWorkers());

        // 2. Prepare latched cleanup tasks to block the physical cleanup workers
        CountDownLatch cleanupHoldLatch = new CountDownLatch(1);
        managedLatches.add(cleanupHoldLatch);
        CountDownLatch cleanupWorkersRunningLatch = new CountDownLatch(2);

        List<TrackedAutoCloseable> acceptedTasks = new ArrayList<>();

        // Submit cleanups up to cleanup queue capacity (10)
        for (int i = 0; i < CLEANUP_QUEUE_CAP; i++) {
            final int idx = i;
            TrackedAutoCloseable task = new TrackedAutoCloseable("cleanup-" + idx, () -> {
                cleanupWorkersRunningLatch.countDown();
                while (true) {
                    try {
                        if (cleanupHoldLatch.await(20, TimeUnit.MILLISECONDS)) {
                            break;
                        }
                    } catch (InterruptedException ignored) {}
                }
            });
            acceptedTasks.add(task);
            long submitStart = System.nanoTime();
            boolean accepted = executor.executeCleanupAsync(task, "cleanup-" + idx);
            long submitElapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - submitStart);

            assertTrue(accepted, "Cleanup task " + idx + " must be accepted within capacity");
            assertTrue(submitElapsedMs < 200, "Caller must not be blocked on submission (took " + submitElapsedMs + "ms)");
        }

        // Wait until physical cleanup workers pick up tasks and hold
        assertTrue(cleanupWorkersRunningLatch.await(3, TimeUnit.SECONDS),
                "Cleanup workers must start and hold");

        // Verify metrics: pendingCleanupObligations == 10
        assertEquals(CLEANUP_QUEUE_CAP, executor.getPendingCleanupObligations(),
                "pendingCleanupObligations must equal cleanup queue capacity (10)");

        // 3. Submit additional cleanup beyond capacity: verify executeCleanupAsync returns false
        TrackedAutoCloseable extraTask = new TrackedAutoCloseable("cleanup-overflow");
        long start = System.nanoTime();
        boolean rejected = executor.executeCleanupAsync(extraTask, "cleanup-overflow");
        long elapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);

        assertFalse(rejected, "executeCleanupAsync must return false for cleanup beyond capacity (explicit rejection)");
        assertTrue(elapsedMs < 100, "Caller must not be blocked when rejected (took " + elapsedMs + "ms)");
        assertEquals(0, extraTask.getCloseCount(), "Rejected task must NOT be executed by executor");
        assertEquals(CLEANUP_QUEUE_CAP, executor.getPendingCleanupObligations(),
                "pendingCleanupObligations must remain 10");

        // 4. Release latches: all accepted cleanups execute, pendingCleanupObligations returns to 0
        cleanupHoldLatch.countDown();
        mainHoldLatch.countDown();

        for (TrackedAutoCloseable task : acceptedTasks) {
            assertTrue(task.awaitClosed(5, TimeUnit.SECONDS),
                    "Accepted task " + task.getId() + " must complete closure");
            assertEquals(1, task.getCloseCount(),
                    "Accepted task " + task.getId() + " must be closed exactly once");
        }

        boolean drained = waitForCondition(() -> executor.getPendingCleanupObligations() == 0, 3000);
        assertTrue(drained, "pendingCleanupObligations must return to 0");
        assertEquals(0, executor.getPendingCleanupObligations());

        boolean workersIdle = waitForCondition(() -> executor.getActualOutstandingWorkers() == 0, 3000);
        assertTrue(workersIdle, "Main workers must return to 0");
    }

    // =========================================================================================
    // Test 2: testBackpressureRejectsNewOpenWhenCleanupIsSaturated
    // =========================================================================================

    @Test
    @DisplayName("2. testBackpressureRejectsNewOpenWhenCleanupIsSaturated - Backpressure rejects new open / reservation without opening file")
    void testBackpressureRejectsNewOpenWhenCleanupIsSaturated() throws Exception {
        final int CLEANUP_QUEUE_CAP = 10;
        final int MAX_WORKERS = 2;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(100, 10000);
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_QUEUE_CAP, breaker);
        managedExecutors.add(executor);

        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS + 2);
        managedCallerPools.add(callerPool);

        CountDownLatch mainHoldLatch = new CountDownLatch(1);
        managedLatches.add(mainHoldLatch);
        CountDownLatch mainStartedLatch = new CountDownLatch(MAX_WORKERS);

        for (int i = 0; i < MAX_WORKERS; i++) {
            callerPool.submit(() -> {
                try {
                    executor.executeRead(() -> {
                        mainStartedLatch.countDown();
                        while (true) {
                            try {
                                if (mainHoldLatch.await(20, TimeUnit.MILLISECONDS)) {
                                    break;
                                }
                            } catch (InterruptedException ignored) {}
                        }
                        return 0;
                    });
                } catch (Exception ignored) {}
            });
        }
        assertTrue(mainStartedLatch.await(3, TimeUnit.SECONDS), "Main workers occupied");

        // Occupy cleanup capacity with 10 blocked cleanups
        CountDownLatch cleanupHoldLatch = new CountDownLatch(1);
        managedLatches.add(cleanupHoldLatch);
        List<TrackedAutoCloseable> tasks = new ArrayList<>();

        for (int i = 0; i < CLEANUP_QUEUE_CAP; i++) {
            final int idx = i;
            TrackedAutoCloseable task = new TrackedAutoCloseable("blocked-" + idx, () -> {
                while (true) {
                    try {
                        if (cleanupHoldLatch.await(20, TimeUnit.MILLISECONDS)) {
                            break;
                        }
                    } catch (InterruptedException ignored) {}
                }
            });
            tasks.add(task);
            assertTrue(executor.executeCleanupAsync(task, "blocked-" + idx));
        }

        assertEquals(CLEANUP_QUEUE_CAP, executor.getPendingCleanupObligations(),
                "Cleanup obligations must be saturated at capacity (10)");

        // Call acquireReservation(): verify it immediately throws MediaUnavailableException without opening any file
        AtomicBoolean fileOpened = new AtomicBoolean(false);
        Path testFile = tempDir.resolve("backpressure_test_file.bin");
        Files.write(testFile, "BACKPRESSURE_TEST_BYTES".getBytes(StandardCharsets.UTF_8));

        long start = System.nanoTime();
        MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () -> {
            // Attempting to acquire reservation under saturated cleanup
            try (DriveResourceReservation res = executor.acquireReservation()) {
                // If it were granted, file would be opened:
                FileChannel raw = FileChannel.open(testFile, StandardOpenOption.READ);
                managedFileChannels.add(raw);
                fileOpened.set(true);
            }
        }, "acquireReservation must throw MediaUnavailableException when cleanup is saturated");
        long elapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);

        assertTrue(elapsedMs < 100, "acquireReservation must fail fast (<100ms, took " + elapsedMs + "ms)");
        assertFalse(fileOpened.get(), "File must NEVER be opened when reservation fails");
        assertNotNull(ex.getMessage(), "Exception must contain informative message");

        // Also test storage adapter openChannel fails fast without creating handle
        DriveMediaStorageAdapter adapter = new DriveMediaStorageAdapter(tempDir.toString(), executor);
        assertThrows(MediaUnavailableException.class, () -> {
            adapter.openChannel("backpressure_test_file.bin");
        }, "Storage adapter openChannel must throw MediaUnavailableException under saturation");

        // Release cleanup latch: capacity frees up
        cleanupHoldLatch.countDown();
        mainHoldLatch.countDown();

        boolean drained = waitForCondition(() -> executor.getPendingCleanupObligations() == 0, 3000);
        assertTrue(drained, "Cleanup queue must drain after latch release");

        // Subsequent acquireReservation() succeeds
        try (DriveResourceReservation reservation = executor.acquireReservation()) {
            assertNotNull(reservation, "Reservation must succeed after cleanup capacity frees up");
            assertTrue(reservation.isActive(), "Reservation must be active");
        }

        // Subsequent openChannel succeeds
        try (SeekableByteChannel ch = adapter.openChannel("backpressure_test_file.bin")) {
            assertNotNull(ch, "openChannel must succeed after recovery");
            assertTrue(ch.isOpen(), "Opened channel must be open");
        }
    }

    // =========================================================================================
    // Test 3: testExactlyOnceExecutionAndConservation
    // =========================================================================================

    @Test
    @DisplayName("3. testExactlyOnceExecutionAndConservation - Conservation law: accepted = closed + currently owned; exactly-once execution")
    void testExactlyOnceExecutionAndConservation() throws Exception {
        final int CLEANUP_QUEUE_CAP = 15;
        final int MAX_WORKERS = 2;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(100, 10000);
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_QUEUE_CAP, breaker);
        managedExecutors.add(executor);

        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS + 2);
        managedCallerPools.add(callerPool);

        CountDownLatch mainHoldLatch = new CountDownLatch(1);
        managedLatches.add(mainHoldLatch);
        CountDownLatch mainStartedLatch = new CountDownLatch(MAX_WORKERS);

        for (int i = 0; i < MAX_WORKERS; i++) {
            callerPool.submit(() -> {
                try {
                    executor.executeRead(() -> {
                        mainStartedLatch.countDown();
                        while (true) {
                            try {
                                if (mainHoldLatch.await(20, TimeUnit.MILLISECONDS)) {
                                    break;
                                }
                            } catch (InterruptedException ignored) {}
                        }
                        return 0;
                    });
                } catch (Exception ignored) {}
            });
        }
        assertTrue(mainStartedLatch.await(3, TimeUnit.SECONDS));

        CountDownLatch cleanupLatch = new CountDownLatch(1);
        managedLatches.add(cleanupLatch);

        final int N = 35; // Submit 35 tasks against capacity 15
        List<TrackedAutoCloseable> allTasks = new ArrayList<>();
        List<TrackedAutoCloseable> acceptedTasks = new ArrayList<>();
        List<TrackedAutoCloseable> rejectedTasks = new ArrayList<>();

        for (int i = 0; i < N; i++) {
            final int idx = i;
            TrackedAutoCloseable task = new TrackedAutoCloseable("task-" + idx, () -> {
                while (true) {
                    try {
                        if (cleanupLatch.await(20, TimeUnit.MILLISECONDS)) {
                            break;
                        }
                    } catch (InterruptedException ignored) {}
                }
            });
            allTasks.add(task);

            boolean accepted = executor.executeCleanupAsync(task, "task-" + idx);
            if (accepted) {
                acceptedTasks.add(task);
            } else {
                rejectedTasks.add(task);
            }
        }

        // Verify accepted count bounded by cleanup queue capacity
        assertEquals(CLEANUP_QUEUE_CAP, acceptedTasks.size(),
                "Exactly cleanupQueueCapacity tasks must be accepted");
        assertEquals(N - CLEANUP_QUEUE_CAP, rejectedTasks.size(),
                "Remaining tasks must be explicitly rejected");

        // Conservation Law check while blocked:
        // accepted = closed + currentlyOwned
        int closedWhileBlocked = 0;
        for (TrackedAutoCloseable t : acceptedTasks) {
            if (t.isClosed()) closedWhileBlocked++;
        }
        int currentlyOwned = executor.getPendingCleanupObligations();
        assertEquals(acceptedTasks.size(), closedWhileBlocked + currentlyOwned,
                "Conservation Law must hold: accepted == closed + currentlyOwned");

        // Release latch: all accepted tasks execute
        cleanupLatch.countDown();
        mainHoldLatch.countDown();

        for (TrackedAutoCloseable t : acceptedTasks) {
            assertTrue(t.awaitClosed(5, TimeUnit.SECONDS),
                    "Accepted task " + t.getId() + " must be closed");
            assertEquals(1, t.getCloseCount(),
                    "Accepted task " + t.getId() + " must be closed exactly once");
        }

        // Verify all rejected tasks were never executed by executor
        for (TrackedAutoCloseable t : rejectedTasks) {
            assertEquals(0, t.getCloseCount(),
                    "Rejected task " + t.getId() + " must NOT be executed by executor");
            // Caller can safely close rejected tasks
            t.close();
            assertEquals(1, t.getCloseCount(), "Caller safely disposes rejected task");
        }

        // Verify final metrics: obligations and workers return to 0
        boolean drained = waitForCondition(() -> executor.getPendingCleanupObligations() == 0, 3000);
        assertTrue(drained, "pendingCleanupObligations must return to 0");
    }

    // =========================================================================================
    // Test 4: testNegativeDroppedCleanupDetection
    // =========================================================================================

    @Test
    @DisplayName("4. testNegativeDroppedCleanupDetection - Any unaccepted cleanup is detected and not reported as accepted")
    void testNegativeDroppedCleanupDetection() throws Exception {
        final int CLEANUP_QUEUE_CAP = 5;
        final int MAX_WORKERS = 1;
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_QUEUE_CAP, new DriveCircuitBreaker());
        managedExecutors.add(executor);

        ExecutorService callerPool = Executors.newSingleThreadExecutor();
        managedCallerPools.add(callerPool);

        CountDownLatch mainLatch = new CountDownLatch(1);
        managedLatches.add(mainLatch);
        CountDownLatch mainStarted = new CountDownLatch(1);

        callerPool.submit(() -> {
            try {
                executor.executeRead(() -> {
                    mainStarted.countDown();
                    while (true) {
                        try {
                            if (mainLatch.await(20, TimeUnit.MILLISECONDS)) break;
                        } catch (InterruptedException ignored) {}
                    }
                    return 0;
                });
            } catch (Exception ignored) {}
        });
        assertTrue(mainStarted.await(2, TimeUnit.SECONDS));

        CountDownLatch cleanupLatch = new CountDownLatch(1);
        managedLatches.add(cleanupLatch);

        // Fill cleanup queue to capacity
        List<TrackedAutoCloseable> acceptedList = new ArrayList<>();
        for (int i = 0; i < CLEANUP_QUEUE_CAP; i++) {
            TrackedAutoCloseable t = new TrackedAutoCloseable("acc-" + i, () -> {
                while (true) {
                    try {
                        if (cleanupLatch.await(20, TimeUnit.MILLISECONDS)) break;
                    } catch (InterruptedException ignored) {}
                }
            });
            acceptedList.add(t);
            boolean accepted = executor.executeCleanupAsync(t, "acc-" + i);
            assertTrue(accepted, "Accepted task must return true");
        }

        // Submit unaccepted task
        TrackedAutoCloseable unacceptedTask = new TrackedAutoCloseable("unaccepted-task");
        boolean accepted = executor.executeCleanupAsync(unacceptedTask, "unaccepted-task");

        // Crucial negative assertion: must NOT report accepted when capacity is full
        assertFalse(accepted,
                "Negative detection: Unaccepted cleanup must return false, never reported as true");
        assertEquals(0, unacceptedTask.getCloseCount(),
                "Negative detection: Unaccepted task must never be run or closed by executor");

        // Verify none of the previously accepted tasks were discarded or evicted (unlike F03 DiscardOldestPolicy)
        assertEquals(CLEANUP_QUEUE_CAP, executor.getPendingCleanupObligations(),
                "Queue size must remain exactly at capacity without evicting accepted tasks");

        cleanupLatch.countDown();
        mainLatch.countDown();

        for (TrackedAutoCloseable t : acceptedList) {
            assertTrue(t.awaitClosed(5, TimeUnit.SECONDS));
            assertEquals(1, t.getCloseCount(), "All originally accepted tasks must execute");
        }

        // Caller handles the unaccepted task
        unacceptedTask.close();
        assertEquals(1, unacceptedTask.getCloseCount(), "Caller retains explicit ownership");
    }

    // =========================================================================================
    // Test 5: testCleanupUnderMainWorkerSaturation (Lifecycle Matrix L-06)
    // =========================================================================================

    @Test
    @DisplayName("5. testCleanupUnderMainWorkerSaturation (L-06) - Main pool full, cleanup succeeds through dedicated capacity")
    void testCleanupUnderMainWorkerSaturation() throws Exception {
        final int MAX_WORKERS = 4;
        final int CLEANUP_CAP = 30;
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_CAP, new DriveCircuitBreaker());
        managedExecutors.add(executor);

        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS + 2);
        managedCallerPools.add(callerPool);

        CountDownLatch mainBlockLatch = new CountDownLatch(1);
        managedLatches.add(mainBlockLatch);
        CountDownLatch mainReadyLatch = new CountDownLatch(MAX_WORKERS);

        for (int i = 0; i < MAX_WORKERS; i++) {
            callerPool.submit(() -> {
                try {
                    executor.executeRead(() -> {
                        mainReadyLatch.countDown();
                        while (true) {
                            try {
                                if (mainBlockLatch.await(20, TimeUnit.MILLISECONDS)) break;
                            } catch (InterruptedException ignored) {}
                        }
                        return 0;
                    });
                } catch (Exception ignored) {}
            });
        }
        assertTrue(mainReadyLatch.await(3, TimeUnit.SECONDS));
        assertEquals(MAX_WORKERS, executor.getActualOutstandingWorkers());

        // Submit 20 cleanups while main pool is completely saturated
        final int CLEANUP_COUNT = 20;
        List<TrackedAutoCloseable> cleanupTasks = new ArrayList<>();
        for (int i = 0; i < CLEANUP_COUNT; i++) {
            TrackedAutoCloseable task = new TrackedAutoCloseable("main-sat-cleanup-" + i);
            cleanupTasks.add(task);
            boolean accepted = executor.executeCleanupAsync(task, "main-sat-cleanup-" + i);
            assertTrue(accepted, "Cleanup must succeed through dedicated cleanup capacity");
        }

        // All 20 cleanups must execute and close without depending on main worker pool
        for (TrackedAutoCloseable task : cleanupTasks) {
            assertTrue(task.awaitClosed(5, TimeUnit.SECONDS),
                    "Cleanup task " + task.getId() + " must complete even while main workers are saturated");
            assertEquals(1, task.getCloseCount());
        }

        // Main workers are still saturated!
        assertEquals(MAX_WORKERS, executor.getActualOutstandingWorkers(),
                "Main workers must still be occupied by active reads");

        mainBlockLatch.countDown();
        boolean workersIdle = waitForCondition(() -> executor.getActualOutstandingWorkers() == 0, 3000);
        assertTrue(workersIdle, "Main workers must return to 0 after release");
    }

    // =========================================================================================
    // Test 6: test300HandlesCleanupSaturation_ZeroDiscard (Lifecycle Matrix L-07)
    // =========================================================================================

    @Test
    @DisplayName("6. test300HandlesCleanupSaturation_ZeroDiscard (L-07) - Reviewer 300 handles scale: zero discard, zero handle leak")
    void test300HandlesCleanupSaturation_ZeroDiscard() throws Exception {
        final int MAX_WORKERS = 1;
        final int CLEANUP_CAP = 256;
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_CAP, new DriveCircuitBreaker(1000, 100));
        managedExecutors.add(executor);

        ExecutorService callerPool = Executors.newSingleThreadExecutor();
        managedCallerPools.add(callerPool);

        CountDownLatch mainHoldLatch = new CountDownLatch(1);
        managedLatches.add(mainHoldLatch);
        CountDownLatch mainEnteredLatch = new CountDownLatch(1);

        callerPool.submit(() -> {
            try {
                executor.executeRead(() -> {
                    mainEnteredLatch.countDown();
                    while (true) {
                        try {
                            if (mainHoldLatch.await(20, TimeUnit.MILLISECONDS)) break;
                        } catch (InterruptedException ignored) {}
                    }
                    return 0;
                });
            } catch (Exception ignored) {}
        });
        assertTrue(mainEnteredLatch.await(3, TimeUnit.SECONDS));

        // Create 300 real FileChannel handles on tiny temp file (reviewer reproduction condition)
        Path tempFile = tempDir.resolve("codex_cleanup_pressure_300.bin");
        Files.write(tempFile, "CODEX_F04_ZERO_DISCARD_TEST_BYTES".getBytes(StandardCharsets.UTF_8));

        CountDownLatch cleanupHoldLatch = new CountDownLatch(1);
        managedLatches.add(cleanupHoldLatch);

        final int TOTAL_HANDLES = 300;
        List<FileChannel> allChannels = new ArrayList<>();
        List<FileChannel> acceptedChannels = new ArrayList<>();
        List<FileChannel> rejectedChannels = new ArrayList<>();
        AtomicInteger closedCount = new AtomicInteger(0);

        try {
            for (int i = 0; i < TOTAL_HANDLES; i++) {
                FileChannel ch = FileChannel.open(tempFile, StandardOpenOption.READ);
                allChannels.add(ch);
                managedFileChannels.add(ch);

                boolean accepted = executor.executeCleanupAsync(() -> {
                    while (true) {
                        try {
                            if (cleanupHoldLatch.await(20, TimeUnit.MILLISECONDS)) break;
                        } catch (InterruptedException ignored) {}
                    }
                    ch.close();
                    closedCount.incrementAndGet();
                }, "repro-cleanup-" + i);

                if (accepted) {
                    acceptedChannels.add(ch);
                } else {
                    rejectedChannels.add(ch);
                }
            }

            // In F03, 300 was submitted, 256 was queued, and 44 were silently discarded by DiscardOldestPolicy.
            // In F04, queue capacity is 256. Exactly 256 are accepted, and 44 are explicitly rejected!
            assertEquals(CLEANUP_CAP, acceptedChannels.size(),
                    "Exactly cleanupQueueCapacity (256) handles must be accepted");
            assertEquals(TOTAL_HANDLES - CLEANUP_CAP, rejectedChannels.size(),
                    "Remaining handles (44) must be explicitly rejected (NOT silently discarded)");

            // Release cleanup latch
            cleanupHoldLatch.countDown();

            // Wait for all accepted channels to close
            boolean allAcceptedClosed = waitForCondition(() -> closedCount.get() == acceptedChannels.size(), 5000);
            assertTrue(allAcceptedClosed, "All accepted channels must be closed after release");

            // Verify 100% of accepted channels are closed at OS level
            long openAcceptedCount = acceptedChannels.stream().filter(FileChannel::isOpen).count();
            assertEquals(0, openAcceptedCount, "Zero accepted handles may be leaked (was 42 in F03!)");

            // For rejected channels, caller still owns them and closes them safely
            for (FileChannel ch : rejectedChannels) {
                if (ch.isOpen()) {
                    ch.close();
                }
            }

            long totalStillOpen = allChannels.stream().filter(FileChannel::isOpen).count();
            assertEquals(0, totalStillOpen, "Total open handles after recovery must be exactly 0");

        } finally {
            cleanupHoldLatch.countDown();
            mainHoldLatch.countDown();
        }
    }

    // =========================================================================================
    // Test 7: testFullRecoveryAfterLatchRelease (Lifecycle Matrix L-11)
    // =========================================================================================

    @Test
    @DisplayName("7. testFullRecoveryAfterLatchRelease (L-11) - Full recovery after latch release: all 4 metric lanes return to baseline 0")
    void testFullRecoveryAfterLatchRelease() throws Exception {
        final int MAX_WORKERS = 2;
        final int CLEANUP_CAP = 10;
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_CAP, new DriveCircuitBreaker());
        managedExecutors.add(executor);

        CountDownLatch holdLatch = new CountDownLatch(1);
        managedLatches.add(holdLatch);

        List<TrackedAutoCloseable> tasks = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            TrackedAutoCloseable t = new TrackedAutoCloseable("rec-" + i, () -> {
                while (true) {
                    try {
                        if (holdLatch.await(20, TimeUnit.MILLISECONDS)) break;
                    } catch (InterruptedException ignored) {}
                }
            });
            tasks.add(t);
            executor.executeCleanupAsync(t, "rec-" + i);
        }

        // Metrics are non-zero while held
        assertTrue(executor.getPendingCleanupObligations() > 0 || executor.getActualOutstandingWorkers() > 0);

        // Release latch
        holdLatch.countDown();

        for (TrackedAutoCloseable t : tasks) {
            assertTrue(t.awaitClosed(5, TimeUnit.SECONDS));
        }

        // Verify all 4 metric lanes return strictly to 0 at baseline
        boolean baselineRecovered = waitForCondition(() ->
                executor.getActualOutstandingWorkers() == 0 &&
                executor.getActiveCleanupWorkers() == 0 &&
                executor.getPendingCleanupObligations() == 0 &&
                executor.getActiveResourceReservations() == 0,
                3000
        );

        assertTrue(baselineRecovered, "All 4 metric lanes must return to baseline 0");
        assertEquals(0, executor.getActualOutstandingWorkers(), "Lane 1: Actual outstanding workers must be 0");
        assertEquals(0, executor.getActiveCleanupWorkers(), "Lane 2: Active cleanup workers must be 0");
        assertEquals(0, executor.getPendingCleanupObligations(), "Lane 3: Pending cleanup obligations must be 0");
        assertEquals(0, executor.getActiveResourceReservations(), "Lane 4: Active resource reservations must be 0");
    }
}
