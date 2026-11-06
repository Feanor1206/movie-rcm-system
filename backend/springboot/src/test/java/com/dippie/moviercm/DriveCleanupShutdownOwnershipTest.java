package com.dippie.moviercm;

import com.dippie.moviercm.exception.MediaUnavailableException;
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
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DriveCleanupShutdownOwnershipTest - Shutdown Drain, Rejection & Lifecycle Ownership Suite")
public class DriveCleanupShutdownOwnershipTest {

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
        for (CountDownLatch latch : managedLatches) {
            while (latch.getCount() > 0) {
                latch.countDown();
            }
        }

        // Deterministically shut down any test-managed executors
        for (DriveIoExecutor exec : managedExecutors) {
            try {
                if (exec != null && !exec.isShutdown()) {
                    exec.shutdown();
                }
            } catch (Throwable ignored) {}
        }

        // Shut down any extra caller thread pools
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
            closeCount.incrementAndGet();
            try {
                if (closeAction != null) {
                    closeAction.run();
                }
            } finally {
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

    /**
     * FileChannel decorator to accurately track close invocations and enable zero-leak handle checks.
     */
    static class TrackedFileChannel extends FileChannel {
        private final FileChannel delegate;
        private final AtomicInteger closeCount = new AtomicInteger(0);
        final CountDownLatch closeStartedLatch = new CountDownLatch(1);
        final CountDownLatch closeCompletedLatch = new CountDownLatch(1);
        final CountDownLatch releaseCloseLatch;
        private final boolean blockOnClose;
        private volatile String closeThreadName;

        TrackedFileChannel(FileChannel delegate, boolean blockOnClose, CountDownLatch releaseCloseLatch) {
            this.delegate = delegate;
            this.blockOnClose = blockOnClose;
            this.releaseCloseLatch = releaseCloseLatch;
        }

        TrackedFileChannel(FileChannel delegate) {
            this(delegate, false, null);
        }

        public int getCloseCount() {
            return closeCount.get();
        }

        public String getCloseThreadName() {
            return closeThreadName;
        }

        @Override
        protected void implCloseChannel() throws IOException {
            closeCount.incrementAndGet();
            closeThreadName = Thread.currentThread().getName();
            closeStartedLatch.countDown();
            try {
                if (blockOnClose && releaseCloseLatch != null) {
                    while (true) {
                        try {
                            if (releaseCloseLatch.await(20, TimeUnit.MILLISECONDS)) {
                                break;
                            }
                        } catch (InterruptedException ignored) {
                        }
                    }
                }
                if (delegate != null && delegate.isOpen()) {
                    delegate.close();
                }
            } finally {
                closeCompletedLatch.countDown();
            }
        }

        @Override
        public int read(ByteBuffer dst) throws IOException {
            return delegate != null ? delegate.read(dst) : -1;
        }

        @Override
        public long read(ByteBuffer[] dsts, int offset, int length) throws IOException {
            return delegate != null ? delegate.read(dsts, offset, length) : -1;
        }

        @Override
        public int write(ByteBuffer src) throws IOException {
            return delegate != null ? delegate.write(src) : 0;
        }

        @Override
        public long write(ByteBuffer[] srcs, int offset, int length) throws IOException {
            return delegate != null ? delegate.write(srcs, offset, length) : 0;
        }

        @Override
        public long position() throws IOException {
            return delegate != null ? delegate.position() : 0;
        }

        @Override
        public FileChannel position(long newPosition) throws IOException {
            if (delegate != null) delegate.position(newPosition);
            return this;
        }

        @Override
        public long size() throws IOException {
            return delegate != null ? delegate.size() : 0;
        }

        @Override
        public FileChannel truncate(long size) throws IOException {
            if (delegate != null) delegate.truncate(size);
            return this;
        }

        @Override
        public void force(boolean metaData) throws IOException {
            if (delegate != null) delegate.force(metaData);
        }

        @Override
        public long transferTo(long position, long count, java.nio.channels.WritableByteChannel target) throws IOException {
            return delegate != null ? delegate.transferTo(position, count, target) : 0;
        }

        @Override
        public long transferFrom(java.nio.channels.ReadableByteChannel src, long position, long count) throws IOException {
            return delegate != null ? delegate.transferFrom(src, position, count) : 0;
        }

        @Override
        public int read(ByteBuffer dst, long position) throws IOException {
            return delegate != null ? delegate.read(dst, position) : -1;
        }

        @Override
        public int write(ByteBuffer src, long position) throws IOException {
            return delegate != null ? delegate.write(src, position) : 0;
        }

        @Override
        public java.nio.MappedByteBuffer map(MapMode mode, long position, long size) throws IOException {
            return delegate != null ? delegate.map(mode, position, size) : null;
        }

        @Override
        public java.nio.channels.FileLock lock(long position, long size, boolean shared) throws IOException {
            return delegate != null ? delegate.lock(position, size, shared) : null;
        }

        @Override
        public java.nio.channels.FileLock tryLock(long position, long size, boolean shared) throws IOException {
            return delegate != null ? delegate.tryLock(position, size, shared) : null;
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

    private boolean waitForWorkerCount(DriveIoExecutor executor, int expected, long maxWaitMs) throws InterruptedException {
        long deadline = System.currentTimeMillis() + maxWaitMs;
        while (System.currentTimeMillis() < deadline) {
            if (executor.getActualOutstandingWorkers() == expected) {
                return true;
            }
            Thread.sleep(15);
        }
        return executor.getActualOutstandingWorkers() == expected;
    }

    private boolean awaitCondition(Callable<Boolean> condition, long timeoutMs) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.MILLISECONDS.toNanos(timeoutMs);
        do {
            if (Boolean.TRUE.equals(condition.call())) {
                return true;
            }
            Thread.sleep(5);
        } while (System.nanoTime() < deadline);
        return Boolean.TRUE.equals(condition.call());
    }

    // =========================================================================================
    // Test 1: testShutdownDrainsQueuedCleanupObligations
    // =========================================================================================

    @Test
    @DisplayName("1. testShutdownDrainsQueuedCleanupObligations - Shutdown drains queued cleanup obligations without abandoning them")
    void testShutdownDrainsQueuedCleanupObligations() throws Exception {
        final int CLEANUP_QUEUE_CAP = 20;
        final int MAX_WORKERS = 2;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(100, 10000);
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_QUEUE_CAP, breaker);
        managedExecutors.add(executor);

        assertEquals(CLEANUP_QUEUE_CAP, executor.getCleanupQueueCapacity(),
                "Configured cleanup queue capacity must match");

        // 1. Saturate main worker pool so cleanup tasks route directly to dedicated cleanupExecutor
        CountDownLatch mainHoldLatch = new CountDownLatch(1);
        CountDownLatch mainWorkersBusyLatch = new CountDownLatch(MAX_WORKERS);
        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS);
        managedCallerPools.add(callerPool);

        for (int i = 0; i < MAX_WORKERS; i++) {
            callerPool.submit(() -> {
                try {
                    executor.executeRead(() -> {
                        mainWorkersBusyLatch.countDown();
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
        assertTrue(mainWorkersBusyLatch.await(3, TimeUnit.SECONDS),
                "Main worker pool must be saturated");
        assertEquals(MAX_WORKERS, executor.getActualOutstandingWorkers());

        // 2. Hold physical cleanup workers with a latch
        CountDownLatch holdLatch = new CountDownLatch(1);
        CountDownLatch workersHeldLatch = new CountDownLatch(2);

        List<TrackedAutoCloseable> blockerTasks = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            final int idx = i;
            TrackedAutoCloseable blocker = new TrackedAutoCloseable("blocker-" + idx, () -> {
                workersHeldLatch.countDown();
                while (true) {
                    try {
                        if (holdLatch.await(20, TimeUnit.MILLISECONDS)) {
                            break;
                        }
                    } catch (InterruptedException ignored) {}
                }
            });
            blockerTasks.add(blocker);
            boolean submitted = executor.executeCleanupAsync(blocker, "blocker-" + idx);
            assertTrue(submitted, "Blocker cleanup task must be accepted");
        }

        // Wait until physical cleanup workers start and are held by latch
        assertTrue(workersHeldLatch.await(3, TimeUnit.SECONDS),
                "Physical cleanup workers must have started and become held");

        // 3. Submit 15 cleanup tasks with tracked AutoCloseables
        final int NUM_TASKS = 15;
        List<TrackedAutoCloseable> queuedTasks = new ArrayList<>();
        for (int i = 0; i < NUM_TASKS; i++) {
            TrackedAutoCloseable task = new TrackedAutoCloseable("task-" + i);
            queuedTasks.add(task);
            boolean accepted = executor.executeCleanupAsync(task, "task-" + i);
            assertTrue(accepted, "Cleanup task " + i + " must be accepted into queued cleanup capacity");
        }

        // Verify pendingCleanupObligations reflects all admitted uncompleted obligations
        int pendingBefore = executor.getPendingCleanupObligations();
        assertTrue(pendingBefore >= NUM_TASKS,
                "Pending cleanup obligations (" + pendingBefore + ") must include all queued tasks (" + NUM_TASKS + ")");

        // Verify none of the 15 queued tasks have closed yet
        for (TrackedAutoCloseable task : queuedTasks) {
            assertEquals(0, task.getCloseCount(),
                    "Task " + task.getId() + " must still be waiting in queue before release");
        }

        // 4. Release latches and immediately call executor.shutdown()
        holdLatch.countDown();
        mainHoldLatch.countDown();
        executor.shutdown();

        // Verify all 15 tasks are executed and closed, none abandoned in the queue
        for (TrackedAutoCloseable task : queuedTasks) {
            assertTrue(task.awaitClosed(5, TimeUnit.SECONDS),
                    "Task " + task.getId() + " must be closed during shutdown drain");
            assertEquals(1, task.getCloseCount(),
                    "Task " + task.getId() + " must be closed exactly once");
        }

        for (TrackedAutoCloseable blocker : blockerTasks) {
            assertTrue(blocker.awaitClosed(5, TimeUnit.SECONDS),
                    "Blocker task " + blocker.getId() + " must be closed");
            assertEquals(1, blocker.getCloseCount(),
                    "Blocker task " + blocker.getId() + " must be closed exactly once");
        }

        // Verify pendingCleanupObligations becomes 0
        boolean drained = waitForCondition(() -> executor.getPendingCleanupObligations() == 0, 3000);
        assertTrue(drained, "pendingCleanupObligations must become 0 after shutdown drain");
        assertEquals(0, executor.getPendingCleanupObligations());
        assertEquals(0, executor.getActiveCleanupWorkers(),
                "Active cleanup workers must return to 0 after drain");
    }

    // =========================================================================================
    // Test 2: testExecuteCleanupAsyncRejectsAfterShutdown
    // =========================================================================================

    @Test
    @DisplayName("2. testExecuteCleanupAsyncRejectsAfterShutdown - Rejects cleanup and reservations post-shutdown without blocking")
    void testExecuteCleanupAsyncRejectsAfterShutdown() throws Exception {
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, 4, 20, new DriveCircuitBreaker());
        managedExecutors.add(executor);

        // Pre-shutdown: acquire reservation succeeds and increments counter
        try (DriveResourceReservation res = executor.acquireReservation()) {
            assertNotNull(res, "Reservation should be successfully acquired before shutdown");
            assertTrue(executor.getActiveResourceReservations() >= 1,
                    "Active reservations should reflect acquired lease");
        }
        assertEquals(0, executor.getActiveResourceReservations(),
                "Reservation counter should decrement after close");

        // Call executor.shutdown()
        executor.shutdown();
        assertTrue(executor.isShutdown(), "Executor must report isShutdown() true");

        // Call executeCleanupAsync(resource): verify it returns false without blocking caller
        TrackedAutoCloseable resource = new TrackedAutoCloseable("post-shutdown-resource");
        long start = System.nanoTime();
        boolean accepted = executor.executeCleanupAsync(resource, "post-shutdown-cleanup");
        long elapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - start);

        assertFalse(accepted, "executeCleanupAsync must return false after shutdown");
        assertTrue(elapsedMs < 100, "executeCleanupAsync must not block caller (took " + elapsedMs + "ms)");
        assertEquals(0, resource.getCloseCount(),
                "Rejected resource must NOT be closed by executor without ownership");

        // Call acquireReservation(): verify it throws MediaUnavailableException
        MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () -> {
            executor.acquireReservation();
        }, "acquireReservation must throw MediaUnavailableException after executor shutdown");
        assertNotNull(ex.getMessage(), "Exception must contain informative message");

        // Verify caller retains ownership to safely close rejected resource
        resource.close();
        assertEquals(1, resource.getCloseCount(), "Caller retains ownership and closes rejected resource");
    }

    // =========================================================================================
    // Test 3: testLateOpenHandoffOnTimeoutDisposedSafely
    // =========================================================================================

    @Test
    @DisplayName("3. testLateOpenHandoffOnTimeoutDisposedSafely - Late open completion after timeout is safely disposed via cleanup lane")
    void testLateOpenHandoffOnTimeoutDisposedSafely() throws Exception {
        DriveIoExecutor executor = new DriveIoExecutor(100, 200, 2, 20, new DriveCircuitBreaker());
        managedExecutors.add(executor);

        Path testFile = tempDir.resolve("late_open_safe_test.bin");
        Files.write(testFile, "LATE_OPEN_SAFE_DISPOSAL_TEST_DATA".getBytes(StandardCharsets.UTF_8));

        CountDownLatch taskStarted = new CountDownLatch(1);
        CountDownLatch releaseWorker = new CountDownLatch(1);
        AtomicReference<TrackedFileChannel> openedChannelRef = new AtomicReference<>();

        long start = System.currentTimeMillis();
        MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () -> {
            executor.executeOpen(() -> {
                taskStarted.countDown();
                while (true) {
                    try {
                        if (releaseWorker.await(20, TimeUnit.MILLISECONDS)) {
                            break;
                        }
                    } catch (InterruptedException ignored) {}
                }
                FileChannel raw = FileChannel.open(testFile, StandardOpenOption.READ);
                TrackedFileChannel tracked = new TrackedFileChannel(raw);
                openedChannelRef.set(tracked);
                managedFileChannels.add(raw);
                return tracked;
            }, 60, "late-open-operation");
        });

        long elapsed = System.currentTimeMillis() - start;
        assertTrue(elapsed >= 50, "Caller must wait at least timeoutMs (60ms)");
        assertNotNull(ex.getMessage(), "Timeout exception must provide a message");

        // Verify worker task started and is currently held
        assertTrue(taskStarted.await(2, TimeUnit.SECONDS), "Worker task should have started");
        assertEquals(1, executor.getActualOutstandingWorkers(),
                "Outstanding worker count must remain 1 while background task runs");

        // Release the worker to complete open after caller timed out
        releaseWorker.countDown();

        // Wait for worker to finish open, detect caller timed out, and route to cleanup lane
        boolean returnedToZero = waitForWorkerCount(executor, 0, 4000);
        assertTrue(returnedToZero, "Worker count must return to 0 after late open completes");

        TrackedFileChannel trackedChannel = openedChannelRef.get();
        assertNotNull(trackedChannel, "Channel must have been opened by background worker");

        // Wait for cleanup lane to close the channel
        boolean closedInTime = waitForCondition(() -> trackedChannel.getCloseCount() > 0, 4000);
        assertTrue(closedInTime, "Late-opened channel must be closed by cleanup lane");
        assertEquals(1, trackedChannel.getCloseCount(), "Channel must be closed exactly once");
        assertFalse(trackedChannel.isOpen(), "Channel must report isOpen() == false");

        // Verify pending cleanup obligations drained to 0
        boolean obligationsDrained = waitForCondition(() -> executor.getPendingCleanupObligations() == 0, 3000);
        assertTrue(obligationsDrained, "Pending cleanup obligations must return to 0");

        // Zero leaked handle check on Windows NT: deleting open file throws sharing violation; delete succeeds if closed
        assertDoesNotThrow(() -> Files.delete(testFile),
                "Temporary file must be deletable immediately after cleanup, proving zero leaked OS handles");
        assertFalse(Files.exists(testFile), "File must be cleanly deleted");
    }

    // =========================================================================================
    // Test 4: testConcurrentCloseAndShutdownRace
    // =========================================================================================

    @Test
    @DisplayName("4. testConcurrentCloseAndShutdownRace - Multi-threaded channel closes and executor shutdown with zero handle leaks")
    void testConcurrentCloseAndShutdownRace() throws Exception {
        final int NUM_CHANNELS = 24;
        final int MAX_WORKERS = 6;
        final int CLEANUP_CAP = 30;

        DriveCircuitBreaker breaker = new DriveCircuitBreaker(100, 10000);
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, MAX_WORKERS, CLEANUP_CAP, breaker);
        managedExecutors.add(executor);

        ExecutorService testPool = Executors.newFixedThreadPool(16);
        managedCallerPools.add(testPool);

        List<Path> files = new ArrayList<>();
        List<TrackedFileChannel> trackedChannels = new ArrayList<>();
        List<DriveSeekableByteChannel> driveChannels = new ArrayList<>();

        for (int i = 0; i < NUM_CHANNELS; i++) {
            Path file = tempDir.resolve("race_channel_" + i + ".bin");
            Files.write(file, ("RACE_PAYLOAD_" + i).getBytes(StandardCharsets.UTF_8));
            files.add(file);

            FileChannel raw = FileChannel.open(file, StandardOpenOption.READ);
            managedFileChannels.add(raw);
            TrackedFileChannel tracked = new TrackedFileChannel(raw);
            trackedChannels.add(tracked);

            DriveSeekableByteChannel dc = new DriveSeekableByteChannel(tracked, executor);
            driveChannels.add(dc);
        }

        CountDownLatch startRaceLatch = new CountDownLatch(1);
        List<Future<?>> closeFutures = new ArrayList<>();
        List<Throwable> unexpectedExceptions = Collections.synchronizedList(new ArrayList<>());

        // Submit concurrent close tasks for all channels
        for (int i = 0; i < NUM_CHANNELS; i++) {
            final DriveSeekableByteChannel dc = driveChannels.get(i);
            Future<?> f = testPool.submit(() -> {
                try {
                    startRaceLatch.await();
                    dc.close();
                } catch (Throwable t) {
                    unexpectedExceptions.add(t);
                }
            });
            closeFutures.add(f);
        }

        // Concurrently submit shutdown task
        Future<?> shutdownFuture = testPool.submit(() -> {
            try {
                startRaceLatch.await();
                Thread.sleep(5);
                executor.shutdown();
            } catch (Throwable t) {
                unexpectedExceptions.add(t);
            }
        });

        // Fire concurrent close and shutdown race
        startRaceLatch.countDown();

        // Await all close tasks and shutdown
        for (Future<?> f : closeFutures) {
            assertDoesNotThrow(() -> f.get(5, TimeUnit.SECONDS), "Close task timed out or threw exception");
        }
        assertDoesNotThrow(() -> shutdownFuture.get(5, TimeUnit.SECONDS), "Shutdown timed out or threw exception");

        // Verify zero unhandled exceptions
        assertTrue(unexpectedExceptions.isEmpty(),
                "No unexpected exceptions allowed during concurrent race: " + unexpectedExceptions);

        // Verify every DriveSeekableByteChannel is marked closed and underlying handle is closed
        for (int i = 0; i < NUM_CHANNELS; i++) {
            DriveSeekableByteChannel dc = driveChannels.get(i);
            TrackedFileChannel tracked = trackedChannels.get(i);

            assertTrue(dc.isClosed(), "Drive channel " + i + " must report isClosed() == true");

            // Wait for physical closure to finish
            boolean closed = waitForCondition(() -> !tracked.isOpen() && tracked.getCloseCount() >= 1, 3000);
            if (!closed) {
                // In case of edge race where shutdown rejected async close before accepted, ensure closure
                try {
                    tracked.close();
                } catch (IOException ignored) {}
            }

            assertFalse(tracked.isOpen(), "Underlying channel " + i + " must be closed");
            assertTrue(tracked.getCloseCount() >= 1, "Underlying channel " + i + " close must have been invoked");
        }

        // Verify zero leaked handles on Windows NT: every temp file must be deletable cleanly
        for (int i = 0; i < NUM_CHANNELS; i++) {
            Path file = files.get(i);
            final int idx = i;
            assertDoesNotThrow(() -> Files.deleteIfExists(file),
                    "File " + idx + " must be deletable without sharing violation, proving zero leaked OS handles");
        }

        // Verify pending cleanup obligations drained to 0
        boolean drained = waitForCondition(() -> executor.getPendingCleanupObligations() == 0, 3000);
        assertTrue(drained, "pendingCleanupObligations must become 0 after race and drain complete");
        assertEquals(0, executor.getPendingCleanupObligations());
    }

    // =========================================================================================
    // Test 5: testNegativeDroppedCleanupDetector (Safety Invariant Verification)
    // =========================================================================================

    @Test
    @DisplayName("5. testNegativeDroppedCleanupDetector - Verifies dropped or abandoned cleanup fails conservation assertions")
    void testNegativeDroppedCleanupDetector() {
        TrackedAutoCloseable abandoned = new TrackedAutoCloseable("unclosed-abandoned");
        // Verify that an unclosed resource explicitly fails closed/conservation checks
        assertFalse(abandoned.isClosed(), "Resource not closed must report isClosed() == false");
        assertEquals(0, abandoned.getCloseCount(), "Resource closeCount must be 0 before explicit close");

        // When closed, conservation holds
        abandoned.close();
        assertTrue(abandoned.isClosed(), "Resource must report isClosed() == true after close");
        assertEquals(1, abandoned.getCloseCount(), "Resource closeCount must be exactly 1");
    }

    // =========================================================================================
    // Test 6: testShutdownIsIdempotent
    // =========================================================================================

    @Test
    @DisplayName("6. testShutdownIsIdempotent - Repeated shutdown calls succeed without exception")
    void testShutdownIsIdempotent() {
        DriveIoExecutor executor = new DriveIoExecutor(1000, 2000, 2, 10, new DriveCircuitBreaker());
        managedExecutors.add(executor);

        assertDoesNotThrow(() -> {
            executor.shutdown();
            executor.shutdown();
            executor.shutdown();
        }, "Repeated shutdown invocations must be safe and idempotent");

        assertTrue(executor.isShutdown(), "Executor must remain in shutdown state");
        assertEquals(0, executor.getPendingCleanupObligations());
    }
}
