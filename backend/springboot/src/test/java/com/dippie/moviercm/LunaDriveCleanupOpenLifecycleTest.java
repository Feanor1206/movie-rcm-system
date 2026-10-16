package com.dippie.moviercm;

import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.service.storage.DriveCircuitBreaker;
import com.dippie.moviercm.service.storage.DriveIoExecutor;
import com.dippie.moviercm.service.storage.DriveResourceReservation;
import com.dippie.moviercm.service.storage.DriveSeekableByteChannel;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.ReadableByteChannel;
import java.nio.channels.WritableByteChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("Luna Drive cleanup open lifecycle")
class LunaDriveCleanupOpenLifecycleTest {

    private static final long WAIT_SECONDS = 3;

    @TempDir
    Path tempDir;

    private static DriveIoExecutor newExecutor(int workers, int cleanupCapacity) {
        return new DriveIoExecutor(
                150,
                150,
                workers,
                cleanupCapacity,
                new DriveCircuitBreaker(10_000, 10_000)
        );
    }

    private static boolean awaitQuiescent(DriveIoExecutor executor, long timeout, TimeUnit unit)
            throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (System.nanoTime() < deadline) {
            if (executor.getActualOutstandingWorkers() == 0
                    && executor.getActiveCleanupWorkers() == 0
                    && executor.getActiveResourceReservations() == 0
                    && executor.getPendingCleanupObligations() == 0) {
                return true;
            }
            Thread.sleep(10);
        }
        return executor.getActualOutstandingWorkers() == 0
                && executor.getActiveCleanupWorkers() == 0
                && executor.getActiveResourceReservations() == 0
                && executor.getPendingCleanupObligations() == 0;
    }

    private static boolean awaitWorkersAndCleanup(DriveIoExecutor executor, long timeout, TimeUnit unit)
            throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (System.nanoTime() < deadline) {
            if (executor.getActualOutstandingWorkers() == 0
                    && executor.getActiveCleanupWorkers() == 0
                    && executor.getPendingCleanupObligations() == 0) {
                return true;
            }
            Thread.sleep(10);
        }
        return executor.getActualOutstandingWorkers() == 0
                && executor.getActiveCleanupWorkers() == 0
                && executor.getPendingCleanupObligations() == 0;
    }

    private static boolean awaitPhysicalWorkersStopped(DriveIoExecutor executor, long timeout, TimeUnit unit)
            throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (System.nanoTime() < deadline) {
            if (executor.getActualOutstandingWorkers() == 0 && executor.getActiveCleanupWorkers() == 0) {
                return true;
            }
            Thread.sleep(10);
        }
        return executor.getActualOutstandingWorkers() == 0 && executor.getActiveCleanupWorkers() == 0;
    }

    private static boolean awaitCounts(DriveIoExecutor executor, int active, int pending,
                                       long timeout, TimeUnit unit) throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (System.nanoTime() < deadline) {
            if (executor.getActiveResourceReservations() == active
                    && executor.getPendingCleanupObligations() == pending) {
                return true;
            }
            Thread.sleep(10);
        }
        return executor.getActiveResourceReservations() == active
                && executor.getPendingCleanupObligations() == pending;
    }

    private static void awaitIgnoringInterrupt(CountDownLatch latch) {
        boolean interrupted = false;
        while (true) {
            try {
                latch.await();
                break;
            } catch (InterruptedException ignored) {
                interrupted = true;
            }
        }
        if (interrupted) {
            Thread.currentThread().interrupt();
        }
    }

    /**
     * Delegates normal FileChannel operations while holding physical close behind a latch.
     * The delegate lets assertions distinguish wrapper close initiation from the underlying
     * file handle actually being released.
     */
    private static final class BlockingCloseFileChannel extends FileChannel {
        private final FileChannel delegate;
        private final CountDownLatch closeStarted = new CountDownLatch(1);
        private final CountDownLatch releaseClose = new CountDownLatch(1);
        private final CountDownLatch closeCompleted = new CountDownLatch(1);
        private final AtomicInteger closeCalls = new AtomicInteger();

        private BlockingCloseFileChannel(FileChannel delegate) {
            this.delegate = delegate;
        }

        CountDownLatch closeStarted() {
            return closeStarted;
        }

        CountDownLatch releaseClose() {
            return releaseClose;
        }

        CountDownLatch closeCompleted() {
            return closeCompleted;
        }

        int closeCalls() {
            return closeCalls.get();
        }

        boolean physicalHandleOpen() {
            return delegate.isOpen();
        }

        void forceCloseForTestTeardown() throws IOException {
            if (delegate.isOpen()) {
                delegate.close();
            }
        }

        @Override
        protected void implCloseChannel() throws IOException {
            closeCalls.incrementAndGet();
            closeStarted.countDown();
            try {
                awaitIgnoringInterrupt(releaseClose);
                delegate.close();
            } finally {
                closeCompleted.countDown();
            }
        }

        @Override
        public int read(ByteBuffer dst) throws IOException {
            return delegate.read(dst);
        }

        @Override
        public long read(ByteBuffer[] dsts, int offset, int length) throws IOException {
            return delegate.read(dsts, offset, length);
        }

        @Override
        public int write(ByteBuffer src) throws IOException {
            return delegate.write(src);
        }

        @Override
        public long write(ByteBuffer[] srcs, int offset, int length) throws IOException {
            return delegate.write(srcs, offset, length);
        }

        @Override
        public long position() throws IOException {
            return delegate.position();
        }

        @Override
        public FileChannel position(long newPosition) throws IOException {
            delegate.position(newPosition);
            return this;
        }

        @Override
        public long size() throws IOException {
            return delegate.size();
        }

        @Override
        public FileChannel truncate(long size) throws IOException {
            delegate.truncate(size);
            return this;
        }

        @Override
        public void force(boolean metaData) throws IOException {
            delegate.force(metaData);
        }

        @Override
        public long transferTo(long position, long count, WritableByteChannel target) throws IOException {
            return delegate.transferTo(position, count, target);
        }

        @Override
        public long transferFrom(ReadableByteChannel src, long position, long count) throws IOException {
            return delegate.transferFrom(src, position, count);
        }

        @Override
        public int read(ByteBuffer dst, long position) throws IOException {
            return delegate.read(dst, position);
        }

        @Override
        public int write(ByteBuffer src, long position) throws IOException {
            return delegate.write(src, position);
        }

        @Override
        public MappedByteBuffer map(MapMode mode, long position, long size) throws IOException {
            return delegate.map(mode, position, size);
        }

        @Override
        public FileLock lock(long position, long size, boolean shared) throws IOException {
            return delegate.lock(position, size, shared);
        }

        @Override
        public FileLock tryLock(long position, long size, boolean shared) throws IOException {
            return delegate.tryLock(position, size, shared);
        }
    }

    private static final class BlockingCleanup implements AutoCloseable {
        private final CountDownLatch workersEntered;
        private final CountDownLatch release;
        private final AtomicInteger closeCalls = new AtomicInteger();

        private BlockingCleanup(CountDownLatch workersEntered, CountDownLatch release) {
            this.workersEntered = workersEntered;
            this.release = release;
        }

        int closeCalls() {
            return closeCalls.get();
        }

        @Override
        public void close() {
            closeCalls.incrementAndGet();
            workersEntered.countDown();
            awaitIgnoringInterrupt(release);
        }
    }

    /** Late-open handle that fails its first close, then closes the real file on retry. */
    private static final class FailOnceOpenHandle implements AutoCloseable {
        private final FileChannel delegate;
        private final CountDownLatch firstCloseStarted = new CountDownLatch(1);
        private final CountDownLatch retryCloseStarted = new CountDownLatch(1);
        private final CountDownLatch releaseRetryClose = new CountDownLatch(1);
        private final AtomicInteger closeAttempts = new AtomicInteger();

        private FailOnceOpenHandle(FileChannel delegate) {
            this.delegate = delegate;
        }

        @Override
        public void close() throws IOException {
            if (closeAttempts.incrementAndGet() == 1) {
                firstCloseStarted.countDown();
                throw new IOException("Injected late-open close failure");
            }
            retryCloseStarted.countDown();
            awaitIgnoringInterrupt(releaseRetryClose);
            delegate.close();
        }

        CountDownLatch firstCloseStarted() {
            return firstCloseStarted;
        }

        CountDownLatch retryCloseStarted() {
            return retryCloseStarted;
        }

        CountDownLatch releaseRetryClose() {
            return releaseRetryClose;
        }

        void forceCloseForTestTeardown() throws IOException {
            if (delegate.isOpen()) {
                delegate.close();
            }
        }

        int closeAttempts() {
            return closeAttempts.get();
        }

        boolean physicalHandleOpen() {
            return delegate.isOpen();
        }
    }

    @Test
    @DisplayName("Unreserved executeOpen closes a late handle on worker when cleanup dispatch is rejected")
    void unreservedOpenLeavesPublishedLateHandleOpenWhenCleanupIsRejected() throws Exception {
        final class RecordingCleanupExecutor extends DriveIoExecutor {
            private final AtomicInteger cleanupDispatchCalls = new AtomicInteger();
            private final AtomicReference<Boolean> cleanupDispatchAccepted = new AtomicReference<>();

            private RecordingCleanupExecutor() {
                super(150, 150, 1, 2, new DriveCircuitBreaker(10_000, 10_000));
            }

            @Override
            public boolean executeCleanupAsync(AutoCloseable resource, String opName) {
                boolean accepted = super.executeCleanupAsync(resource, opName);
                cleanupDispatchAccepted.set(accepted);
                cleanupDispatchCalls.incrementAndGet();
                return accepted;
            }
        }

        RecordingCleanupExecutor executor = new RecordingCleanupExecutor();
        DriveResourceReservation heldReservation = executor.acquireReservation();
        CountDownLatch openStarted = new CountDownLatch(1);
        CountDownLatch allowOpenToFinish = new CountDownLatch(1);
        CountDownLatch openCallableFinished = new CountDownLatch(1);
        CountDownLatch callerReturned = new CountDownLatch(1);
        AtomicReference<DriveIoExecutor.OpenState> externalStateRef =
                new AtomicReference<>(DriveIoExecutor.OpenState.PENDING);
        AtomicReference<BlockingCloseFileChannel> externalResourceRef = new AtomicReference<>();
        AtomicReference<Throwable> callerFailure = new AtomicReference<>();
        Path file = Files.write(tempDir.resolve("unreserved-late-open-rejected.bin"), new byte[]{2, 4, 6});
        Thread caller = new Thread(() -> {
            try {
                executor.executeOpen(() -> {
                    try {
                        BlockingCloseFileChannel handle = new BlockingCloseFileChannel(
                                FileChannel.open(file, StandardOpenOption.READ));
                        externalResourceRef.set(handle);
                        openStarted.countDown();
                        awaitIgnoringInterrupt(allowOpenToFinish);
                        return handle;
                    } finally {
                        openCallableFinished.countDown();
                    }
                }, TimeUnit.SECONDS.toMillis(WAIT_SECONDS), "luna-unreserved-late-open",
                        externalStateRef, externalResourceRef);
                callerFailure.set(new AssertionError("Open should time out while its published resource is held"));
            } catch (Throwable t) {
                callerFailure.set(t);
            } finally {
                callerReturned.countDown();
            }
        }, "luna-unreserved-late-open-caller");

        try {
            caller.start();
            assertTrue(openStarted.await(1, TimeUnit.SECONDS),
                    "Open callable must publish its resource and reach the held gate");
            BlockingCloseFileChannel handle = externalResourceRef.get();
            assertNotNull(handle, "External resource reference must expose the open handle before timeout");
            assertTrue(callerReturned.await(WAIT_SECONDS + 1, TimeUnit.SECONDS),
                    "Unreserved open caller must return while the open gate remains held");
            assertInstanceOf(MediaUnavailableException.class, callerFailure.get());
            assertEquals(1, allowOpenToFinish.getCount(),
                    "Open callable must still be blocked when timeout returns");
            assertEquals(DriveIoExecutor.OpenState.TIMED_OUT, externalStateRef.get());
            assertEquals(2, executor.getActiveResourceReservations(),
                    "The held reservation plus pre-admitted unreserved open fills capacity");
            assertEquals(1, executor.cleanupDispatchCalls.get(),
                    "Timeout must attempt unreserved asynchronous cleanup exactly once");
            assertEquals(Boolean.FALSE, executor.cleanupDispatchAccepted.get(),
                    "The full bounded cleanup budget rejects the late handle");
            assertTrue(handle.physicalHandleOpen());
            assertEquals(0, handle.closeCalls(), "Rejected cleanup must not close on the caller thread");

            allowOpenToFinish.countDown();
            assertTrue(openCallableFinished.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "The open worker must finish after its gate is released");
            assertTrue(handle.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "The late-open worker must initiate close after its gate is released");
            assertTrue(handle.physicalHandleOpen(), "Physical handle stays open while close latch is held");
            assertEquals(1, handle.closeCalls(), "Close must be called exactly once");
            assertEquals(1, executor.getActualOutstandingWorkers(),
                    "The late-open worker remains accounted while physical close is blocked");

            handle.releaseClose().countDown();
            assertTrue(handle.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Physical close must complete after release");
            assertTrue(awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS),
                    "The late-open worker must exit within the bound");
            assertFalse(handle.physicalHandleOpen(),
                    "The late-open worker must physically close the handle after rejected cleanup dispatch");
            assertEquals(1, handle.closeCalls(),
                    "The worker must close the late handle exactly once");
        } finally {
            allowOpenToFinish.countDown();
            BlockingCloseFileChannel handle = externalResourceRef.get();
            if (handle != null) {
                handle.releaseClose().countDown();
            }
            caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            if (caller.isAlive()) {
                caller.interrupt();
                caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            }
            boolean callerStopped = !caller.isAlive();
            boolean openSettled = openCallableFinished.await(WAIT_SECONDS, TimeUnit.SECONDS);
            boolean workersStopped = awaitWorkersAndCleanup(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            IOException fixtureCloseFailure = null;
            if (handle != null) {
                try {
                    handle.forceCloseForTestTeardown();
                } catch (IOException failure) {
                    fixtureCloseFailure = failure;
                }
            }
            if (heldReservation.isActive()) {
                heldReservation.release();
            }
            boolean quiescent = awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            executor.shutdown();
            assertTrue(callerStopped, "Teardown must wait boundedly for the open caller");
            assertTrue(openSettled, "Teardown must wait boundedly for the open callable");
            assertTrue(workersStopped, "Teardown must wait boundedly for cleanup workers");
            assertNull(fixtureCloseFailure, "Teardown must explicitly close the temporary file handle");
            assertTrue(quiescent, "Teardown must drain workers and accounting within the bound");
        }
    }

    @Test
    @DisplayName("Unreserved open close failure retains failed cleanup and recovers on retry")
    void unreservedOpenCloseFailureRetainsFailedCleanupAndRecoversOnRetry() throws Exception {
        final class RecordingCleanupExecutor extends DriveIoExecutor {
            private final AtomicInteger cleanupDispatchCalls = new AtomicInteger();
            private final AtomicReference<Boolean> cleanupDispatchAccepted = new AtomicReference<>();

            private RecordingCleanupExecutor() {
                super(150, 150, 1, 2, new DriveCircuitBreaker(10_000, 10_000));
            }

            @Override
            public boolean executeCleanupAsync(AutoCloseable resource, String opName) {
                boolean accepted = super.executeCleanupAsync(resource, opName);
                cleanupDispatchAccepted.set(accepted);
                cleanupDispatchCalls.incrementAndGet();
                return accepted;
            }
        }

        RecordingCleanupExecutor executor = new RecordingCleanupExecutor();
        DriveResourceReservation heldReservation = executor.acquireReservation();
        CountDownLatch openStarted = new CountDownLatch(1);
        CountDownLatch allowOpenToFinish = new CountDownLatch(1);
        CountDownLatch openCallableFinished = new CountDownLatch(1);
        CountDownLatch callerReturned = new CountDownLatch(1);
        AtomicReference<DriveIoExecutor.OpenState> externalStateRef =
                new AtomicReference<>(DriveIoExecutor.OpenState.PENDING);
        AtomicReference<FailOnceOpenHandle> externalResourceRef = new AtomicReference<>();
        AtomicReference<Throwable> callerFailure = new AtomicReference<>();
        Path file = Files.write(tempDir.resolve("unreserved-close-failure-retry.bin"), new byte[]{3, 5, 7});

        Thread caller = new Thread(() -> {
            try {
                executor.executeOpen(() -> {
                    try {
                        openStarted.countDown();
                        awaitIgnoringInterrupt(allowOpenToFinish);
                        FailOnceOpenHandle handle = new FailOnceOpenHandle(
                                FileChannel.open(file, StandardOpenOption.READ));
                        externalResourceRef.set(handle);
                        return handle;
                    } finally {
                        openCallableFinished.countDown();
                    }
                }, 100, "luna-unreserved-close-failure-retry",
                        externalStateRef, externalResourceRef);
                callerFailure.set(new AssertionError("Open should time out while opener is held"));
            } catch (Throwable t) {
                callerFailure.set(t);
            } finally {
                callerReturned.countDown();
            }
        }, "luna-unreserved-close-failure-caller");

        try {
            caller.start();
            assertTrue(openStarted.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Worker should start open callable");
            assertTrue(callerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Caller must return after timeout");
            assertInstanceOf(MediaUnavailableException.class, callerFailure.get());

            // Release opener to complete open and attempt worker close
            allowOpenToFinish.countDown();
            assertTrue(openCallableFinished.await(WAIT_SECONDS, TimeUnit.SECONDS));

            FailOnceOpenHandle handle = externalResourceRef.get();
            assertNotNull(handle, "Handle must have been produced by open callable");
            assertTrue(handle.firstCloseStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Worker must attempt initial close");
            assertTrue(awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS));

            // Initial close threw IOException: handle remains physically open and retained for retry
            assertTrue(handle.physicalHandleOpen(), "Physical handle must remain open after first close failure");
            assertEquals(1, handle.closeAttempts(), "Initial close was attempted by worker");
            assertEquals(1, executor.getFailedCleanupObligations(), "Must be retained in failed obligations");
            assertTrue(executor.getRetainedFailedResources().contains(handle), "Resource must be retained");

            // Release held reservation to make capacity available for retry
            heldReservation.release();
            assertEquals(0, executor.getActiveResourceReservations());

            // Retry should now succeed in reserving pending capacity and closing handle
            boolean retrySubmitted = executor.retryFailedCleanup(handle);
            assertTrue(retrySubmitted, "Retry should be accepted after capacity opened up");
            assertTrue(handle.retryCloseStarted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            handle.releaseRetryClose().countDown();
            assertTrue(awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            assertFalse(handle.physicalHandleOpen(), "Physical handle must be closed after successful retry");
            assertEquals(2, handle.closeAttempts(), "Both initial failure and retry were attempted");
            assertEquals(0, executor.getFailedCleanupObligations(), "Failed obligation cleared");
            assertEquals(0, executor.getPendingCleanupObligations(), "Pending obligations cleared");
        } finally {
            allowOpenToFinish.countDown();
            FailOnceOpenHandle handle = externalResourceRef.get();
            if (handle != null) {
                handle.releaseRetryClose().countDown();
            }
            caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            if (caller.isAlive()) {
                caller.interrupt();
                caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            }
            if (heldReservation.isActive()) {
                heldReservation.release();
            }
            if (handle != null && handle.physicalHandleOpen()) {
                handle.forceCloseForTestTeardown();
            }
            awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            executor.shutdown();
        }
    }

    @Test
    @DisplayName("Late open keeps its reservation through timeout and blocked physical close")
    void lateOpenRetainsOwnershipUntilPhysicalCloseCompletes() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 4);
        DriveResourceReservation reservation = executor.acquireReservation();
        CountDownLatch openStarted = new CountDownLatch(1);
        CountDownLatch allowOpenToFinish = new CountDownLatch(1);
        CountDownLatch openCallableFinished = new CountDownLatch(1);
        CountDownLatch callerReturned = new CountDownLatch(1);
        AtomicReference<BlockingCloseFileChannel> opened = new AtomicReference<>();
        AtomicReference<Throwable> callerFailure = new AtomicReference<>();
        Path file = Files.write(tempDir.resolve("late-open.bin"), new byte[]{1, 2, 3});
        Thread caller = new Thread(() -> {
            try {
                executor.executeOpen(() -> {
                    try {
                        openStarted.countDown();
                        awaitIgnoringInterrupt(allowOpenToFinish);
                        BlockingCloseFileChannel channel = new BlockingCloseFileChannel(
                                FileChannel.open(file, StandardOpenOption.READ));
                        opened.set(channel);
                        return channel;
                    } finally {
                        openCallableFinished.countDown();
                    }
                }, 150, "luna-late-open", reservation);
                callerFailure.set(new AssertionError("Open should time out while the opener is held"));
            } catch (Throwable t) {
                callerFailure.set(t);
            } finally {
                callerReturned.countDown();
            }
        }, "luna-late-open-caller");

        try {
            caller.start();
            assertTrue(openStarted.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Open callable must reach its held gate before timeout is asserted");
            assertTrue(callerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Open caller must return at its finite timeout while opener remains held");
            assertInstanceOf(MediaUnavailableException.class, callerFailure.get());
            assertEquals(1, allowOpenToFinish.getCount(),
                    "Open latch must still be held when the timed-out caller returns");
            assertEquals(1, executor.getActualOutstandingWorkers(),
                    "Physical open worker remains accounted while its latch is held");
            assertEquals(1, executor.getActiveResourceReservations(),
                    "The opening reservation must not be released when the caller times out");
            assertEquals(0, executor.getPendingCleanupObligations());
            assertNull(opened.get());

            allowOpenToFinish.countDown();
            long openDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WAIT_SECONDS);
            while (opened.get() == null && System.nanoTime() < openDeadline) {
                Thread.sleep(5);
            }
            BlockingCloseFileChannel channel = opened.get();
            assertNotNull(channel, "Late open should eventually create the physical handle");
            assertTrue(channel.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Executor must transfer the late handle into asynchronous cleanup");

            // The physical close latch remains held throughout these caller and quota checks.
            assertEquals(0, callerReturned.getCount(), "Timed-out caller has already returned");
            assertTrue(channel.physicalHandleOpen(), "Underlying file handle remains live until close latch release");
            assertEquals(1, channel.closeCalls(), "Late handle close should be initiated exactly once");
            assertEquals(1, executor.getActualOutstandingWorkers(),
                    "The late-open worker remains accounted until its physical close returns");
            assertEquals(1, executor.getActiveResourceReservations(),
                    "The opening reservation stays active while the late handle is being closed");
            assertEquals(0, executor.getPendingCleanupObligations(),
                    "Late-open disposal remains owned by its still-running opener worker");

            channel.releaseClose().countDown();
            assertTrue(channel.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS),
                    "Worker and resource accounting return to baseline after physical close");
            assertFalse(channel.physicalHandleOpen());
            assertEquals(1, channel.closeCalls(), "Late handle must be disposed exactly once");
        } finally {
            allowOpenToFinish.countDown();
            boolean openSettled = openCallableFinished.await(WAIT_SECONDS, TimeUnit.SECONDS);
            BlockingCloseFileChannel channel = opened.get();
            if (openSettled && channel != null) {
                channel.releaseClose().countDown();
            }
            caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            if (caller.isAlive()) {
                caller.interrupt();
                caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            }
            boolean workersStopped = awaitWorkersAndCleanup(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            BlockingCloseFileChannel remaining = opened.get();
            if (workersStopped) {
                if (remaining != null) {
                    remaining.forceCloseForTestTeardown();
                }
                if (reservation.isActive()) {
                    reservation.release();
                }
            }
            boolean teardownQuiescent = awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            executor.shutdown();
            assertTrue(teardownQuiescent,
                    "Late-open teardown must drain workers and reservation accounting within the bound");
        }
    }

    @Test
    @DisplayName("Late-open close failure transfers exactly one reservation into a retryable obligation")
    void lateOpenCloseFailureKeepsAccountingNonNegativeAndRetryable() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 2);
        DriveResourceReservation reservation = executor.acquireReservation();
        CountDownLatch openStarted = new CountDownLatch(1);
        CountDownLatch allowOpenToFinish = new CountDownLatch(1);
        CountDownLatch openCallableFinished = new CountDownLatch(1);
        CountDownLatch callerReturned = new CountDownLatch(1);
        AtomicReference<FailOnceOpenHandle> opened = new AtomicReference<>();
        AtomicReference<Throwable> callerFailure = new AtomicReference<>();
        Path file = Files.write(tempDir.resolve("late-open-close-failure.bin"), new byte[]{8, 9});
        Thread caller = new Thread(() -> {
            try {
                executor.executeOpen(() -> {
                    try {
                        openStarted.countDown();
                        awaitIgnoringInterrupt(allowOpenToFinish);
                        FailOnceOpenHandle handle = new FailOnceOpenHandle(
                                FileChannel.open(file, StandardOpenOption.READ));
                        opened.set(handle);
                        return handle;
                    } finally {
                        openCallableFinished.countDown();
                    }
                }, 100, "luna-late-open-close-failure", reservation);
                callerFailure.set(new AssertionError("Open should time out while the opener is held"));
            } catch (Throwable t) {
                callerFailure.set(t);
            } finally {
                callerReturned.countDown();
            }
        }, "luna-late-open-close-failure-caller");
        CountDownLatch retryCallerReturned = new CountDownLatch(1);
        AtomicReference<Boolean> retryAccepted = new AtomicReference<>();
        AtomicReference<Throwable> retryFailure = new AtomicReference<>();
        Thread retryCaller = null;

        try {
            caller.start();
            assertTrue(openStarted.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Open callable must reach its held gate before timeout is asserted");
            assertTrue(callerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Timeout caller must return with the open latch still held");
            assertInstanceOf(MediaUnavailableException.class, callerFailure.get());
            assertEquals(1, allowOpenToFinish.getCount());
            assertEquals(1, executor.getActiveResourceReservations());
            assertEquals(0, executor.getPendingCleanupObligations());

            allowOpenToFinish.countDown();
            assertTrue(openCallableFinished.await(WAIT_SECONDS, TimeUnit.SECONDS));
            FailOnceOpenHandle handle = opened.get();
            assertNotNull(handle);
            assertTrue(handle.firstCloseStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "The late-open worker must attempt physical disposal");
            assertTrue(awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS),
                    "The opener must finish its failed physical close before accounting is inspected");

            int activeAfterFailure = executor.getActiveResourceReservations();
            int pendingAfterFailure = executor.getPendingCleanupObligations();
            int failedAfterFailure = executor.getFailedCleanupObligations();
            int totalAfterFailure = activeAfterFailure + pendingAfterFailure;
            assertEquals(1, handle.closeAttempts());
            assertTrue(handle.physicalHandleOpen());

            retryCaller = new Thread(() -> {
                try {
                    retryAccepted.set(executor.retryFailedCleanup(handle));
                } catch (Throwable t) {
                    retryFailure.set(t);
                } finally {
                    retryCallerReturned.countDown();
                }
            }, "luna-late-open-close-retry-caller");
            retryCaller.start();
            assertTrue(handle.retryCloseStarted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(retryCallerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Retry submission must return while the physical close latch is held");
            assertEquals(Boolean.TRUE, retryAccepted.get());
            assertNull(retryFailure.get());
            assertEquals(1, handle.releaseRetryClose().getCount());
            assertTrue(handle.physicalHandleOpen());
            assertEquals(1, executor.getPendingCleanupObligations());

            handle.releaseRetryClose().countDown();
            assertTrue(awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            assertFalse(handle.physicalHandleOpen());
            assertEquals(2, handle.closeAttempts());
            assertAll("late-open failure ownership and recovery",
                    () -> assertEquals(0, activeAfterFailure,
                            "Late-close failure must transfer the original reservation exactly once"),
                    () -> assertEquals(1, pendingAfterFailure,
                            "Failed late close remains in the pending lane"),
                    () -> assertEquals(1, failedAfterFailure),
                    () -> assertEquals(1, totalAfterFailure,
                            "Failure retains the original unit of bounded ownership"),
                    () -> assertEquals(0, executor.getActiveResourceReservations()),
                    () -> assertEquals(0, executor.getPendingCleanupObligations()),
                    () -> assertEquals(0, executor.getFailedCleanupObligations()),
                    () -> assertEquals(0, executor.getActualOutstandingWorkers()),
                    () -> assertEquals(0, executor.getActiveCleanupWorkers()));
        } finally {
            allowOpenToFinish.countDown();
            boolean openSettled = openCallableFinished.await(WAIT_SECONDS, TimeUnit.SECONDS);
            if (!openSettled) {
                awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS);
                openSettled = openCallableFinished.getCount() == 0;
            }
            FailOnceOpenHandle handle = opened.get();
            if (handle != null) {
                handle.releaseRetryClose().countDown();
            }
            caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            if (caller.isAlive()) {
                caller.interrupt();
                caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            }
            if (retryCaller != null) {
                retryCaller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
                if (retryCaller.isAlive()) {
                    retryCaller.interrupt();
                    retryCaller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
                }
            }
            if (openSettled && handle != null
                    && awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS)
                    && executor.getPendingCleanupObligations() > 0) {
                executor.retryFailedCleanup(handle);
                awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            }
            if (reservation.isActive() && awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS)) {
                reservation.release();
            }
            if (handle != null && handle.physicalHandleOpen()
                    && awaitPhysicalWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS)
                    && executor.getPendingCleanupObligations() == 0) {
                handle.forceCloseForTestTeardown();
            }
            boolean teardownQuiescent = awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            executor.shutdown();
            assertTrue(teardownQuiescent,
                    "Late-open failure teardown must drain workers and reservation accounting within the bound");
            assertTrue(openSettled,
                    "Late-open teardown must wait for the opener to publish or abandon its handle before returning");
        }
    }

    @Test
    @DisplayName("Caller interruption preserves late-open ownership and restores its interrupt flag")
    void interruptedOpenRetainsOwnershipUntilLateHandleIsClosed() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 4);
        DriveResourceReservation reservation = executor.acquireReservation();
        CountDownLatch openStarted = new CountDownLatch(1);
        CountDownLatch allowOpenToFinish = new CountDownLatch(1);
        CountDownLatch openCallableFinished = new CountDownLatch(1);
        CountDownLatch callerReturned = new CountDownLatch(1);
        AtomicReference<BlockingCloseFileChannel> opened = new AtomicReference<>();
        AtomicReference<Throwable> callerFailure = new AtomicReference<>();
        AtomicReference<Boolean> interruptRestored = new AtomicReference<>(false);
        Path file = Files.write(tempDir.resolve("interrupted-open.bin"), new byte[]{4, 5, 6});
        Thread caller = new Thread(() -> {
            try {
                executor.executeOpen(() -> {
                    openStarted.countDown();
                    try {
                        awaitIgnoringInterrupt(allowOpenToFinish);
                        BlockingCloseFileChannel channel = new BlockingCloseFileChannel(
                                FileChannel.open(file, StandardOpenOption.READ));
                        opened.set(channel);
                        return channel;
                    } finally {
                        openCallableFinished.countDown();
                    }
                }, 5_000, "luna-interrupted-open", reservation);
                callerFailure.set(new AssertionError("Interrupted open unexpectedly returned a handle"));
            } catch (Throwable t) {
                callerFailure.set(t);
            } finally {
                interruptRestored.set(Thread.currentThread().isInterrupted());
                callerReturned.countDown();
            }
        }, "luna-interrupted-open-caller");

        try {
            caller.start();
            assertTrue(openStarted.await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertEquals(1, executor.getActualOutstandingWorkers());
            assertEquals(1, executor.getActiveResourceReservations());

            caller.interrupt();
            assertTrue(callerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Interrupted caller must return without waiting for the physical opener");
            assertInstanceOf(MediaUnavailableException.class, callerFailure.get());
            assertTrue(interruptRestored.get(), "Executor must restore caller interrupt status");
            assertEquals(1, allowOpenToFinish.getCount(),
                    "Open latch must still be held when the interrupted caller returns");
            assertEquals(1, executor.getActualOutstandingWorkers(),
                    "The interrupted caller does not own or decrement the still-running worker");
            assertEquals(1, executor.getActiveResourceReservations(),
                    "Reservation remains held while the interrupted opener can still produce a handle");

            allowOpenToFinish.countDown();
            long openDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WAIT_SECONDS);
            while (opened.get() == null && System.nanoTime() < openDeadline) {
                Thread.sleep(5);
            }
            BlockingCloseFileChannel channel = opened.get();
            assertNotNull(channel, "Worker must finish the open after the caller is interrupted");
            assertTrue(channel.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS));

            // The close latch is still held. Caller returned before the late resource is disposed.
            assertEquals(0, callerReturned.getCount());
            assertTrue(channel.physicalHandleOpen());
            assertEquals(1, executor.getActualOutstandingWorkers());
            assertEquals(1, executor.getActiveResourceReservations());
            assertEquals(0, executor.getPendingCleanupObligations());

            channel.releaseClose().countDown();
            assertTrue(awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            assertFalse(channel.physicalHandleOpen());
            assertEquals(1, channel.closeCalls());
        } finally {
            allowOpenToFinish.countDown();
            boolean openSettled = openCallableFinished.await(WAIT_SECONDS, TimeUnit.SECONDS);
            BlockingCloseFileChannel channel = opened.get();
            if (openSettled && channel != null) {
                channel.releaseClose().countDown();
            }
            caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            if (caller.isAlive()) {
                caller.interrupt();
                caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            }
            boolean workersStopped = awaitWorkersAndCleanup(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            BlockingCloseFileChannel remaining = opened.get();
            if (workersStopped) {
                if (remaining != null) {
                    remaining.forceCloseForTestTeardown();
                }
                if (reservation.isActive()) {
                    reservation.release();
                }
            }
            boolean teardownQuiescent = awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            executor.shutdown();
            assertTrue(teardownQuiescent,
                    "Interrupted-open teardown must drain workers and reservation accounting within the bound");
        }
    }

    @Test
    @DisplayName("Channel close returns while native close is held and retains cleanup accounting")
    void channelCloseCallerReturnsBeforePhysicalCloseLatch() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 4);
        DriveResourceReservation reservation = executor.acquireReservation();
        BlockingCloseFileChannel delegate = new BlockingCloseFileChannel(
                FileChannel.open(Files.write(tempDir.resolve("blocked-close.bin"), new byte[]{7}),
                        StandardOpenOption.READ));
        DriveSeekableByteChannel channel = new DriveSeekableByteChannel(delegate, executor, reservation);
        CountDownLatch closeCallerReturned = new CountDownLatch(1);
        AtomicReference<Throwable> closeFailure = new AtomicReference<>();
        Thread caller = new Thread(() -> {
            try {
                channel.close();
            } catch (Throwable t) {
                closeFailure.set(t);
            } finally {
                closeCallerReturned.countDown();
            }
        }, "luna-close-caller");

        try {
            caller.start();
            assertTrue(delegate.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Cleanup worker must begin the physical close");
            assertTrue(closeCallerReturned.await(1, TimeUnit.SECONDS),
                    "Channel close caller must return while the native close latch remains held");
            assertNull(closeFailure.get());
            assertFalse(channel.isOpen(), "Wrapper becomes closed as soon as caller requests close");
            assertEquals(1, delegate.releaseClose().getCount(),
                    "Physical close latch must still be held when the caller returns");
            assertTrue(delegate.physicalHandleOpen(), "Underlying file handle is still physically open");
            assertEquals(1, delegate.closeCalls());
            assertEquals(1, executor.getPendingCleanupObligations(),
                    "Blocked physical close remains charged to the cleanup lane");

            delegate.releaseClose().countDown();
            assertTrue(delegate.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            assertFalse(delegate.physicalHandleOpen());
            assertEquals(1, delegate.closeCalls(), "Channel disposal occurs exactly once");
        } finally {
            delegate.releaseClose().countDown();
            caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            if (caller.isAlive()) {
                caller.interrupt();
                caller.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
            }
            boolean workersStopped = awaitWorkersAndCleanup(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            if (workersStopped) {
                delegate.forceCloseForTestTeardown();
                if (reservation.isActive()) {
                    reservation.release();
                }
            }
            boolean teardownQuiescent = awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS);
            executor.shutdown();
            assertTrue(teardownQuiescent,
                    "Blocked-close teardown must drain workers and reservation accounting within the bound");
        }
    }

    @Test
    @DisplayName("Three hundred twenty admission attempts stay within the configured reservation budget")
    void admissionAttemptsRemainBoundedAtThreeHundredPlus() throws Exception {
        final int capacity = 8;
        final int attempts = 320;
        final int concurrentCallers = 16;
        final int transferCount = capacity / 2;
        DriveIoExecutor executor = newExecutor(transferCount, capacity);
        List<DriveResourceReservation> reservations = new ArrayList<>();
        List<BlockingCleanup> pendingCleanups = new ArrayList<>();
        ConcurrentLinkedQueue<DriveResourceReservation> admittedDuringCleanup = new ConcurrentLinkedQueue<>();
        AtomicInteger rejected = new AtomicInteger();
        AtomicInteger transferCallsInProgress = new AtomicInteger();
        AtomicInteger admissionCallsInProgress = new AtomicInteger();
        AtomicInteger overlappingAdmissionTransferCalls = new AtomicInteger();
        AtomicReference<Throwable> unexpectedFailure = new AtomicReference<>();
        CountDownLatch callersReady = new CountDownLatch(concurrentCallers);
        CountDownLatch transferCallersReady = new CountDownLatch(transferCount);
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch admissionActive = new CountDownLatch(1);
        CountDownLatch transferActive = new CountDownLatch(1);
        CountDownLatch attemptsFinished = new CountDownLatch(attempts);
        CountDownLatch transfersFinished = new CountDownLatch(transferCount);
        CountDownLatch cleanupWorkersEntered = new CountDownLatch(transferCount);
        CountDownLatch releaseCleanup = new CountDownLatch(1);
        ExecutorService callers = Executors.newFixedThreadPool(concurrentCallers);
        ExecutorService transferCallers = Executors.newFixedThreadPool(transferCount);

        try {
            for (int i = 0; i < capacity; i++) {
                reservations.add(executor.acquireReservation());
            }
            for (int i = 0; i < transferCount; i++) {
                BlockingCleanup cleanup = new BlockingCleanup(cleanupWorkersEntered, releaseCleanup);
                pendingCleanups.add(cleanup);
            }

            for (int i = 0; i < attempts; i++) {
                callers.submit(() -> {
                    callersReady.countDown();
                    try {
                        if (!start.await(WAIT_SECONDS, TimeUnit.SECONDS)) {
                            throw new AssertionError("Admission start gate timed out");
                        }
                        admissionCallsInProgress.incrementAndGet();
                        admissionActive.countDown();
                        try {
                            transferActive.await(WAIT_SECONDS, TimeUnit.SECONDS);
                            if (transferCallsInProgress.get() > 0) {
                                overlappingAdmissionTransferCalls.incrementAndGet();
                            }
                            admittedDuringCleanup.add(executor.acquireReservation());
                        } finally {
                            admissionCallsInProgress.decrementAndGet();
                        }
                    } catch (MediaUnavailableException expectedAtCapacity) {
                        rejected.incrementAndGet();
                    } catch (Throwable failure) {
                        unexpectedFailure.compareAndSet(null, failure);
                    } finally {
                        attemptsFinished.countDown();
                    }
                });
            }
            for (int i = 0; i < transferCount; i++) {
                final int transferIndex = i;
                transferCallers.submit(() -> {
                    transferCallersReady.countDown();
                    try {
                        if (!start.await(WAIT_SECONDS, TimeUnit.SECONDS)) {
                            throw new AssertionError("Transfer start gate timed out");
                        }
                        transferCallsInProgress.incrementAndGet();
                        transferActive.countDown();
                        try {
                            admissionActive.await(WAIT_SECONDS, TimeUnit.SECONDS);
                            if (admissionCallsInProgress.get() > 0) {
                                overlappingAdmissionTransferCalls.incrementAndGet();
                            }
                            if (!reservations.get(transferIndex).closeAsync(
                                    pendingCleanups.get(transferIndex), "luna-admission-transfer-" + transferIndex)) {
                                throw new AssertionError("A pre-issued reservation must transfer its cleanup permit");
                            }
                        } finally {
                            transferCallsInProgress.decrementAndGet();
                        }
                    } catch (Throwable failure) {
                        unexpectedFailure.compareAndSet(null, failure);
                    } finally {
                        transfersFinished.countDown();
                    }
                });
            }

            assertTrue(callersReady.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "All admission workers must reach the start gate");
            assertTrue(transferCallersReady.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "All reservation-transfer workers must reach the same start gate");
            start.countDown();
            assertTrue(transfersFinished.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "All active-to-pending transfers must finish their non-blocking handoff");
            assertTrue(cleanupWorkersEntered.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Transferred cleanup workers must remain held while concurrent admissions run");
            assertTrue(attemptsFinished.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "All bounded admission attempts must finish");
            assertNull(unexpectedFailure.get(), "Admission attempts must not fail unexpectedly");
            assertEquals(attempts, admittedDuringCleanup.size() + rejected.get(),
                    "Every admission attempt must either own a permit or fail fast");
            assertEquals(0, admittedDuringCleanup.size(),
                    "Concurrent active-to-pending transfers must not create a transient admission gap");
            assertTrue(overlappingAdmissionTransferCalls.get() > 0,
                    "Admission and transfer method calls must overlap, not only run sequentially against a full budget");
            assertEquals(attempts, rejected.get());
            assertEquals(capacity - transferCount, executor.getActiveResourceReservations());
            assertEquals(transferCount, executor.getPendingCleanupObligations());
            assertEquals(capacity, executor.getActiveResourceReservations()
                    + executor.getPendingCleanupObligations());

            releaseCleanup.countDown();
            assertTrue(awaitCounts(executor, capacity - transferCount, 0, WAIT_SECONDS, TimeUnit.SECONDS),
                    "Releasing blocked cleanup returns pending accounting to baseline");
            for (BlockingCleanup cleanup : pendingCleanups) {
                assertEquals(1, cleanup.closeCalls(), "Each transferred cleanup must execute exactly once");
            }
            assertEquals(capacity - transferCount, executor.getActiveResourceReservations(),
                    "Active reservations remain owned until explicitly released");
            for (DriveResourceReservation reservation : reservations) {
                reservation.release();
            }
            assertTrue(awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS),
                    "Releasing still-active reservations returns accounting to baseline");
        } finally {
            start.countDown();
            admissionActive.countDown();
            transferActive.countDown();
            callers.shutdown();
            transferCallers.shutdown();
            boolean callersStopped = false;
            boolean transferCallersStopped = false;
            try {
                callersStopped = callers.awaitTermination(WAIT_SECONDS, TimeUnit.SECONDS);
                if (!callersStopped) {
                    callers.shutdownNow();
                    callersStopped = callers.awaitTermination(WAIT_SECONDS, TimeUnit.SECONDS);
                }
                transferCallersStopped = transferCallers.awaitTermination(WAIT_SECONDS, TimeUnit.SECONDS);
                if (!transferCallersStopped) {
                    transferCallers.shutdownNow();
                    transferCallersStopped = transferCallers.awaitTermination(WAIT_SECONDS, TimeUnit.SECONDS);
                }
            } finally {
                releaseCleanup.countDown();
                for (DriveResourceReservation reservation : reservations) {
                    reservation.release();
                }
                if (callersStopped) {
                    for (DriveResourceReservation reservation : admittedDuringCleanup) {
                        reservation.release();
                    }
                }
                boolean teardownQuiescent = awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS);
                executor.shutdown();
                assertTrue(teardownQuiescent,
                        "Admission-test teardown must drain workers and reservation accounting within the bound");
            }
            assertTrue(callersStopped,
                    "All admission callers must terminate before the test drains admitted permits");
            assertTrue(transferCallersStopped,
                    "All reservation-transfer callers must terminate before the test drains admitted permits");
        }
    }
}
