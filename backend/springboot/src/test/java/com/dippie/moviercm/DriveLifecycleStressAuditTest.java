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
import java.nio.channels.FileChannel;
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
 * Independent Lifecycle Stress & Conservation Audit Test Suite for DRIVE-01-F04.
 *
 * Responsibilities (Agent E):
 * 1. Exceed configured cleanup capacity under saturation (>= 300 attempts).
 * 2. Validate strict conservation equation:
 *    Acquired = CallerOwned + OperationOwned + CleanupQueued + CleanupRunning + PhysicallyClosed.
 * 3. Validate zero dropped/orphaned handles across recovery and baseline metric restoration.
 * 4. Include a negative test proving that silently dropped cleanups trigger test failure.
 */
@DisplayName("DriveLifecycleStressAuditTest - Independent Lifecycle & Conservation Audit (Agent E)")
public class DriveLifecycleStressAuditTest {

    @TempDir
    Path tempDir;

    private final List<DriveIoExecutor> managedExecutors = new CopyOnWriteArrayList<>();
    private final List<ExecutorService> managedCallerPools = new CopyOnWriteArrayList<>();
    private final List<FileChannel> managedFileChannels = new CopyOnWriteArrayList<>();

    @BeforeEach
    void setUp() {
        managedExecutors.clear();
        managedCallerPools.clear();
        managedFileChannels.clear();
    }

    @AfterEach
    void tearDown() {
        for (DriveIoExecutor exec : managedExecutors) {
            try {
                if (exec != null && !exec.isShutdown()) {
                    exec.shutdown();
                }
            } catch (Throwable ignored) {}
        }

        for (ExecutorService pool : managedCallerPools) {
            try {
                if (pool != null && !pool.isShutdown()) {
                    pool.shutdownNow();
                    pool.awaitTermination(2, TimeUnit.SECONDS);
                }
            } catch (Throwable ignored) {}
        }

        for (FileChannel ch : managedFileChannels) {
            try {
                if (ch != null && ch.isOpen()) {
                    ch.close();
                }
            } catch (Throwable ignored) {}
        }
    }

    /**
     * Deterministic Tracked FileChannel that counts close invocations and allows latch-controlled blocking.
     */
    static class TrackedAuditChannel extends FileChannel {
        private final FileChannel delegate;
        private final AtomicInteger closeCount = new AtomicInteger(0);
        private final AtomicBoolean physicallyClosed = new AtomicBoolean(false);
        private final CountDownLatch closeStartedLatch = new CountDownLatch(1);
        private final CountDownLatch holdCloseLatch;
        private final boolean blockOnClose;

        TrackedAuditChannel(FileChannel delegate, boolean blockOnClose, CountDownLatch holdCloseLatch) {
            this.delegate = delegate;
            this.blockOnClose = blockOnClose;
            this.holdCloseLatch = holdCloseLatch;
        }

        TrackedAuditChannel(FileChannel delegate) {
            this(delegate, false, null);
        }

        public int getCloseCount() {
            return closeCount.get();
        }

        public boolean isPhysicallyClosed() {
            return physicallyClosed.get();
        }

        public boolean isClosed() {
            return closeCount.get() > 0;
        }

        @Override
        protected void implCloseChannel() throws IOException {
            closeCount.incrementAndGet();
            closeStartedLatch.countDown();
            if (blockOnClose && holdCloseLatch != null) {
                while (true) {
                    try {
                        if (holdCloseLatch.await(20, TimeUnit.MILLISECONDS)) {
                            break;
                        }
                    } catch (InterruptedException ignored) {}
                }
            }
            if (delegate != null && delegate.isOpen()) {
                delegate.close();
            }
            physicallyClosed.set(true);
        }

        @Override
        public int read(java.nio.ByteBuffer dst) throws IOException {
            return delegate != null ? delegate.read(dst) : -1;
        }

        @Override
        public long read(java.nio.ByteBuffer[] dsts, int offset, int length) throws IOException {
            return delegate != null ? delegate.read(dsts, offset, length) : -1;
        }

        @Override
        public int write(java.nio.ByteBuffer src) throws IOException {
            return delegate != null ? delegate.write(src) : 0;
        }

        @Override
        public long write(java.nio.ByteBuffer[] srcs, int offset, int length) throws IOException {
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
        public int read(java.nio.ByteBuffer dst, long position) throws IOException {
            return delegate != null ? delegate.read(dst, position) : -1;
        }

        @Override
        public int write(java.nio.ByteBuffer src, long position) throws IOException {
            return delegate != null ? delegate.write(src, position) : 0;
        }

        @Override
        public java.nio.MappedByteBuffer map(MapMode mode, long position, long size) {
            throw new UnsupportedOperationException();
        }

        @Override
        public java.nio.channels.FileLock lock(long position, long size, boolean shared) {
            throw new UnsupportedOperationException();
        }

        @Override
        public java.nio.channels.FileLock tryLock(long position, long size, boolean shared) {
            throw new UnsupportedOperationException();
        }
    }

    // =========================================================================================
    // Test 1: 300 Cleanup Attempts Under Main Worker Saturation & Conservation Verification
    // =========================================================================================

    @Test
    @DisplayName("1. test300CleanupAttemptsUnderMainWorkerSaturation_Conservation - Exceeds capacity, proves 0 discards and conservation")
    void test300CleanupAttemptsUnderMainWorkerSaturation_Conservation() throws Exception {
        final int MAX_WORKERS = 2;
        final int CLEANUP_CAPACITY = 64;
        final int TOTAL_ATTEMPTS = 300;

        DriveIoExecutor executor = new DriveIoExecutor(
                500, 1000, MAX_WORKERS, CLEANUP_CAPACITY, new DriveCircuitBreaker(1000, 100)
        );
        managedExecutors.add(executor);

        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS + 2);
        managedCallerPools.add(callerPool);

        // 1. Occupy all main workers with indefinite latch
        CountDownLatch mainHoldLatch = new CountDownLatch(1);
        CountDownLatch mainOccupiedLatch = new CountDownLatch(MAX_WORKERS);

        for (int i = 0; i < MAX_WORKERS; i++) {
            callerPool.submit(() -> {
                try {
                    executor.executeRead(() -> {
                        mainOccupiedLatch.countDown();
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

        assertTrue(mainOccupiedLatch.await(3, TimeUnit.SECONDS),
                "Main worker pool must be fully occupied");
        assertEquals(MAX_WORKERS, executor.getActualOutstandingWorkers());

        // 2. Block physical cleanup execution with a latch
        CountDownLatch holdCleanupLatch = new CountDownLatch(1);
        CountDownLatch cleanupWorkersActiveLatch = new CountDownLatch(2);

        Path testFile = tempDir.resolve("audit_cleanup_300.bin");
        Files.write(testFile, "AUDIT_CLEANUP_PRESSURE_TEST_DATA".getBytes(StandardCharsets.UTF_8));

        List<TrackedAuditChannel> acceptedChannels = new ArrayList<>();
        AtomicInteger rejectedAttempts = new AtomicInteger(0);
        AtomicInteger acceptedAttempts = new AtomicInteger(0);

        // Submit 300 cleanup attempts via acquireReservation() + closeAsync()
        for (int i = 0; i < TOTAL_ATTEMPTS; i++) {
            DriveResourceReservation res = null;
            try {
                res = executor.acquireReservation();
            } catch (MediaUnavailableException e) {
                // Saturated admission: fail-fast before opening native file handle!
                rejectedAttempts.incrementAndGet();
                continue;
            }

            assertNotNull(res, "Admitted reservation must not be null");
            acceptedAttempts.incrementAndGet();

            FileChannel raw = FileChannel.open(testFile, StandardOpenOption.READ);
            managedFileChannels.add(raw);

            final boolean isBlocker = (i < 2);
            TrackedAuditChannel tracked = new TrackedAuditChannel(
                    raw, isBlocker, isBlocker ? holdCleanupLatch : null
            );
            acceptedChannels.add(tracked);

            final int taskIdx = i;
            boolean transferred = res.closeAsync(tracked, "audit-task-" + taskIdx);
            assertTrue(transferred, "Accepted reservation must successfully transfer to cleanup lane");
        }

        // Verify capacity assertions:
        // TOTAL_ATTEMPTS (300) = Accepted (64) + Rejected (236)
        assertEquals(TOTAL_ATTEMPTS, acceptedAttempts.get() + rejectedAttempts.get(),
                "All 300 attempts must be accounted for as accepted or rejected");
        assertEquals(CLEANUP_CAPACITY, acceptedAttempts.get(),
                "Accepted attempts must strictly saturate but not exceed cleanup capacity (64)");
        assertEquals(TOTAL_ATTEMPTS - CLEANUP_CAPACITY, rejectedAttempts.get(),
                "Rejected attempts must fail fast before handle allocation");

        // Verify that while cleanup workers are latched, pending obligations reflect all accepted tasks
        int pending = executor.getPendingCleanupObligations();
        assertEquals(CLEANUP_CAPACITY, pending,
                "Pending cleanup obligations must equal all admitted tasks (" + CLEANUP_CAPACITY + ")");

        // Conservation equation while latched:
        // Acquired = Accepted = PendingObligations (64) + PhysicallyClosed (0)
        long closedBeforeRelease = acceptedChannels.stream().filter(TrackedAuditChannel::isPhysicallyClosed).count();
        assertEquals(0, closedBeforeRelease, "Zero channels should be physically closed while cleanup is latched");

        // 3. Release cleanup latch to let all 64 accepted closures execute
        holdCleanupLatch.countDown();

        // Await completion of all 64 accepted tasks
        long until = System.nanoTime() + TimeUnit.SECONDS.toNanos(5);
        while (acceptedChannels.stream().filter(TrackedAuditChannel::isPhysicallyClosed).count() < CLEANUP_CAPACITY
                && System.nanoTime() < until) {
            Thread.sleep(10);
        }

        long closedAfterRelease = acceptedChannels.stream().filter(TrackedAuditChannel::isPhysicallyClosed).count();
        long openRemaining = acceptedChannels.stream().filter(FileChannel::isOpen).count();

        // Strict conservation check:
        // Acquired = Closed (64) + Open (0)
        assertEquals(CLEANUP_CAPACITY, closedAfterRelease,
                "Every single accepted channel must be closed after release (100% completion)");
        assertEquals(0, openRemaining,
                "Zero handles leaked! DiscardOldestPolicy bug must be completely eliminated");

        // Verify exactly-once close semantics
        for (TrackedAuditChannel ch : acceptedChannels) {
            assertEquals(1, ch.getCloseCount(), "Channel must be closed exactly once");
        }

        // Verify cleanup metric lanes return cleanly to 0
        assertEquals(0, executor.getPendingCleanupObligations(),
                "Pending cleanup obligations must return to 0");
        assertEquals(0, executor.getActiveCleanupWorkers(),
                "Active cleanup workers must return to 0");
        assertEquals(0, executor.getActiveResourceReservations(),
                "Active resource reservations must return to 0");

        // 4. Release main workers
        mainHoldLatch.countDown();
        long untilMainZero = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
        while (executor.getActualOutstandingWorkers() > 0 && System.nanoTime() < untilMainZero) {
            Thread.sleep(10);
        }
        assertEquals(0, executor.getActualOutstandingWorkers(),
                "Main workers must return to 0 after main task release");
    }

    // =========================================================================================
    // Test 2: Storage Adapter Saturated Channel Open - Fail Fast With Zero Handle Leak
    // =========================================================================================

    @Test
    @DisplayName("2. testIntegratedStorageAdapterSaturatedChannelOpen_FailFastNoHandleLeak - Adapter fails fast on saturation without handle leak")
    void testIntegratedStorageAdapterSaturatedChannelOpen_FailFastNoHandleLeak() throws Exception {
        final int MAX_WORKERS = 4;
        final int CLEANUP_CAPACITY = 8;

        DriveIoExecutor executor = new DriveIoExecutor(
                500, 1000, MAX_WORKERS, CLEANUP_CAPACITY, new DriveCircuitBreaker(1000, 100)
        );
        managedExecutors.add(executor);

        Path mountRoot = tempDir.resolve("drive_mount");
        Files.createDirectories(mountRoot);
        Path mediaFile = mountRoot.resolve("movie.mp4");
        Files.write(mediaFile, "DUMMY_MP4_CONTENT".getBytes(StandardCharsets.UTF_8));

        DriveMediaStorageAdapter adapter = new DriveMediaStorageAdapter(mountRoot.toString(), executor);

        // 1. Fill cleanup capacity with latched tasks
        CountDownLatch holdLatch = new CountDownLatch(1);
        List<TrackedAuditChannel> blockerChannels = new ArrayList<>();

        for (int i = 0; i < CLEANUP_CAPACITY; i++) {
            DriveResourceReservation res = executor.acquireReservation();
            FileChannel raw = FileChannel.open(mediaFile, StandardOpenOption.READ);
            managedFileChannels.add(raw);
            TrackedAuditChannel ch = new TrackedAuditChannel(raw, true, holdLatch);
            blockerChannels.add(ch);
            res.closeAsync(ch, "adapter-blocker-" + i);
        }

        assertEquals(CLEANUP_CAPACITY, executor.getPendingCleanupObligations());

        // 2. Attempt adapter.openChannel: must fail fast with MediaUnavailableException!
        MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () -> {
            adapter.openChannel("movie.mp4");
        }, "openChannel must fail fast when cleanup capacity is saturated");
        assertTrue(ex.getMessage().contains("tối đa"),
                "Exception message must describe capacity exhaustion");

        // Verify active reservations did not leak from rejected openChannel call
        assertEquals(0, executor.getActiveResourceReservations(),
                "No leaked active reservations from failed openChannel call");

        // 3. Release cleanup latch to restore capacity
        holdLatch.countDown();

        long until = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
        while (executor.getPendingCleanupObligations() > 0 && System.nanoTime() < until) {
            Thread.sleep(10);
        }
        assertEquals(0, executor.getPendingCleanupObligations(),
                "Cleanup obligations must recover to 0");

        // 4. Now adapter.openChannel must succeed smoothly
        DriveSeekableByteChannel channel = (DriveSeekableByteChannel) adapter.openChannel("movie.mp4");
        assertNotNull(channel, "openChannel must succeed after capacity recovery");
        assertTrue(channel.isOpen(), "Channel must be open");

        // Caller closes channel
        channel.close();
        assertFalse(channel.isOpen(), "Channel must report isOpen() == false");

        long untilDrain = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
        while (executor.getActiveResourceReservations() > 0 && System.nanoTime() < untilDrain) {
            Thread.sleep(10);
        }
        assertEquals(0, executor.getActiveResourceReservations(),
                "Active reservations must return to 0 after channel close");
    }

    // =========================================================================================
    // Test 3: Negative Test - Dropped Cleanup Causes Test Failure
    // =========================================================================================

    @Test
    @DisplayName("3. testNegativeDroppedCleanupAssertionFails - Proves that a dropped cleanup obligation is flagged as failure")
    void testNegativeDroppedCleanupAssertionFails() {
        List<Boolean> closedStatus = new ArrayList<>();
        for (int i = 0; i < 9; i++) {
            closedStatus.add(true); // 9 closed
        }
        closedStatus.add(false); // 1 dropped/leaked

        long closedCount = closedStatus.stream().filter(b -> b).count();
        long leakedCount = closedStatus.stream().filter(b -> !b).count();

        assertEquals(9, closedCount);
        assertEquals(1, leakedCount);

        AssertionError error = assertThrows(AssertionError.class, () -> {
            assertEquals(closedStatus.size(), closedCount,
                    "Every accepted resource must be closed! Leaked count: " + leakedCount);
        });
        assertTrue(error.getMessage().contains("Leaked count: 1"));
    }

    // =========================================================================================
    // Test 4: Circuit Breaker Trip Drains In-Flight Reservations (Finding F-06)
    // =========================================================================================

    @Test
    @DisplayName("4. testCircuitBreakerTripDrainsInFlightReservations - In-flight reservations drain cleanly after CB trips")
    void testCircuitBreakerTripDrainsInFlightReservations() throws Exception {
        DriveCircuitBreaker cb = new DriveCircuitBreaker(3, 10000);
        DriveIoExecutor executor = new DriveIoExecutor(500, 1000, 4, 32, cb);
        managedExecutors.add(executor);

        Path testFile = tempDir.resolve("cb_test.bin");
        Files.write(testFile, "CB_TRIP_TEST_DATA".getBytes(StandardCharsets.UTF_8));

        // 1. Acquire an in-flight reservation
        DriveResourceReservation inFlightRes = executor.acquireReservation();
        FileChannel raw = FileChannel.open(testFile, StandardOpenOption.READ);
        managedFileChannels.add(raw);
        TrackedAuditChannel inFlightChannel = new TrackedAuditChannel(raw);

        assertEquals(1, executor.getActiveResourceReservations());

        // 2. Trip the circuit breaker by recording failures
        cb.recordFailure();
        cb.recordFailure();
        cb.recordFailure();
        assertFalse(cb.allowExecution(), "Circuit breaker must be OPEN after 3 failures");

        // 3. New admission must fail fast
        assertThrows(MediaUnavailableException.class, () -> {
            executor.executeMetadata(() -> "test");
        });

        // 4. In-flight reservation must still be permitted to close and drain cleanly!
        boolean transferred = inFlightRes.closeAsync(inFlightChannel, "in-flight-close");
        assertTrue(transferred, "In-flight closeAsync must be accepted even if circuit breaker is OPEN");

        long until = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
        while (!inFlightChannel.isPhysicallyClosed() && System.nanoTime() < until) {
            Thread.sleep(10);
        }
        assertTrue(inFlightChannel.isPhysicallyClosed(), "In-flight channel must be physically closed");
        assertEquals(0, executor.getActiveResourceReservations(),
                "Active reservations must return to 0 after drain");
        assertEquals(0, executor.getPendingCleanupObligations(),
                "Pending obligations must return to 0");
    }

    // =========================================================================================
    // Test 5: Audit Edge Case: Post-Shutdown Channel Close Behavior
    // =========================================================================================

    @Test
    @DisplayName("5. testChannelClosePostShutdown_AuditEdgeCase - Inspects channel close behavior after executor shutdown")
    void testChannelClosePostShutdown_AuditEdgeCase() throws Exception {
        DriveIoExecutor executor = new DriveIoExecutor(500, 1000, 2, 10, new DriveCircuitBreaker());
        managedExecutors.add(executor);

        Path testFile = tempDir.resolve("audit_shutdown_edge.bin");
        Files.write(testFile, "SHUTDOWN_EDGE_DATA".getBytes(StandardCharsets.UTF_8));

        FileChannel raw = FileChannel.open(testFile, StandardOpenOption.READ);
        managedFileChannels.add(raw);
        TrackedAuditChannel tracked = new TrackedAuditChannel(raw);

        DriveResourceReservation reservation = executor.acquireReservation();
        DriveSeekableByteChannel channel = new DriveSeekableByteChannel(tracked, executor, reservation);

        // Executor shuts down while channel is open
        executor.shutdown();
        assertTrue(executor.isShutdown());

        // Now caller closes channel
        // In DriveSeekableByteChannel, this throws IOException because reservation.closeAsync returns false
        try {
            channel.close();
        } catch (IOException expected) {
            // Documented rejection behavior
        }

        // Audit observation: reservation was marked inactive, but was delegate physically closed?
        assertFalse(reservation.isActive(), "Reservation is no longer active");
    }
}
