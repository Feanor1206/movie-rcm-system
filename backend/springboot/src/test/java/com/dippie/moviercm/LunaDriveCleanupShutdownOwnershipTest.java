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
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("Luna Drive cleanup shutdown ownership")
class LunaDriveCleanupShutdownOwnershipTest {

    private static final long WAIT_SECONDS = 3;
    private static final long SHUTDOWN_WAIT_SECONDS = 7;

    @TempDir
    Path tempDir;

    private static DriveIoExecutor newExecutor(int workers, int cleanupCapacity) {
        // A long finite deadline lets the test hold a physical read worker without racing a timeout.
        return new DriveIoExecutor(
                TimeUnit.SECONDS.toMillis(30),
                TimeUnit.SECONDS.toMillis(30),
                workers,
                cleanupCapacity,
                new DriveCircuitBreaker(10_000, 10_000)
        );
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

    private static boolean awaitQuiescent(DriveIoExecutor executor, long timeout, TimeUnit unit)
            throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (System.nanoTime() < deadline) {
            if (executor.getActualOutstandingWorkers() == 0
                    && executor.getActiveCleanupWorkers() == 0
                    && executor.getPendingCleanupObligations() == 0
                    && executor.getActiveResourceReservations() == 0) {
                return true;
            }
            Thread.sleep(5);
        }
        return executor.getActualOutstandingWorkers() == 0
                && executor.getActiveCleanupWorkers() == 0
                && executor.getPendingCleanupObligations() == 0
                && executor.getActiveResourceReservations() == 0;
    }

    private static void joinOrInterrupt(Thread thread) throws InterruptedException {
        if (thread == null) {
            return;
        }
        thread.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
        if (thread.isAlive()) {
            thread.interrupt();
            thread.join(TimeUnit.SECONDS.toMillis(WAIT_SECONDS));
        }
    }

    /** A small tracked close action that can hold a cleanup worker behind a test latch. */
    private static final class BlockingCloseResource implements AutoCloseable {
        private final CountDownLatch closeStarted = new CountDownLatch(1);
        private final CountDownLatch releaseClose;
        private final CountDownLatch closeCompleted = new CountDownLatch(1);
        private final AtomicInteger closeCalls = new AtomicInteger();

        private BlockingCloseResource(CountDownLatch releaseClose) {
            this.releaseClose = releaseClose;
        }

        @Override
        public void close() {
            closeCalls.incrementAndGet();
            closeStarted.countDown();
            try {
                awaitIgnoringInterrupt(releaseClose);
            } finally {
                closeCompleted.countDown();
            }
        }

        int closeCalls() {
            return closeCalls.get();
        }

        CountDownLatch closeStarted() {
            return closeStarted;
        }

        CountDownLatch closeCompleted() {
            return closeCompleted;
        }
    }

    /** First close fails; retry closes the real handle. Latches make both attempts observable. */
    private static final class FailOnceCloseResource implements AutoCloseable {
        private final FileChannel delegate;
        private final CountDownLatch firstCloseStarted = new CountDownLatch(1);
        private final CountDownLatch releaseFirstClose = new CountDownLatch(1);
        private final CountDownLatch retryCloseStarted = new CountDownLatch(1);
        private final CountDownLatch releaseRetryClose = new CountDownLatch(1);
        private final CountDownLatch duplicateRetryCompleted = new CountDownLatch(1);
        private final AtomicInteger attempts = new AtomicInteger();

        private FailOnceCloseResource(FileChannel delegate) {
            this.delegate = delegate;
        }

        @Override
        public void close() throws IOException {
            int attempt = attempts.incrementAndGet();
            if (attempt == 1) {
                firstCloseStarted.countDown();
                awaitIgnoringInterrupt(releaseFirstClose);
                throw new IOException("Injected failure before physical close");
            }
            retryCloseStarted.countDown();
            awaitIgnoringInterrupt(releaseRetryClose);
            delegate.close();
            if (attempt > 2) {
                duplicateRetryCompleted.countDown();
            }
        }

        CountDownLatch firstCloseStarted() {
            return firstCloseStarted;
        }

        CountDownLatch releaseFirstClose() {
            return releaseFirstClose;
        }

        CountDownLatch retryCloseStarted() {
            return retryCloseStarted;
        }

        CountDownLatch releaseRetryClose() {
            return releaseRetryClose;
        }

        CountDownLatch duplicateRetryCompleted() {
            return duplicateRetryCompleted;
        }

        int attempts() {
            return attempts.get();
        }

        boolean physicalHandleOpen() {
            return delegate.isOpen();
        }
    }

    /** Fails once so bounded-admission teardown can retry and release its retained slot. */
    private static final class FailOnceCleanupAction implements AutoCloseable {
        private final AtomicInteger attempts = new AtomicInteger();
        private final CountDownLatch firstAttemptFinished = new CountDownLatch(1);

        @Override
        public void close() throws IOException {
            if (attempts.incrementAndGet() == 1) {
                firstAttemptFinished.countDown();
                throw new IOException("Injected one-time cleanup failure");
            }
        }

        CountDownLatch firstAttemptFinished() {
            return firstAttemptFinished;
        }

        int attempts() {
            return attempts.get();
        }
    }

    private static boolean awaitMainWorkersStopped(DriveIoExecutor executor, long timeout, TimeUnit unit)
            throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (System.nanoTime() < deadline) {
            if (executor.getActualOutstandingWorkers() == 0) {
                return true;
            }
            Thread.sleep(5);
        }
        return executor.getActualOutstandingWorkers() == 0;
    }

    private static boolean awaitCleanupWorkersStopped(DriveIoExecutor executor, long timeout, TimeUnit unit)
            throws InterruptedException {
        long deadline = System.nanoTime() + unit.toNanos(timeout);
        while (System.nanoTime() < deadline) {
            if (executor.getActiveCleanupWorkers() == 0) {
                return true;
            }
            Thread.sleep(5);
        }
        return executor.getActiveCleanupWorkers() == 0;
    }

    /**
     * FileChannel wrapper that holds physical close while keeping the underlying handle observable.
     * Normal IO delegates to a real temporary file so the test can distinguish wrapper state from
     * actual resource disposal.
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

    @Test
    @DisplayName("Shutdown before channel close retains its reservation until asynchronous close finishes")
    void shutdownBeforeCloseRetainsOwnershipAndReturnsWhileNativeCloseIsHeld() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 2);
        DriveResourceReservation reservation = executor.acquireReservation();
        BlockingCloseFileChannel delegate = new BlockingCloseFileChannel(
                FileChannel.open(Files.write(tempDir.resolve("shutdown-before-close.bin"), new byte[]{1}),
                        StandardOpenOption.READ));
        DriveSeekableByteChannel channel = new DriveSeekableByteChannel(delegate, executor, reservation);
        CountDownLatch shutdownReturned = new CountDownLatch(1);
        AtomicReference<Throwable> shutdownFailure = new AtomicReference<>();
        Thread shutdownCaller = new Thread(() -> {
            try {
                executor.shutdown();
            } catch (Throwable t) {
                shutdownFailure.set(t);
            } finally {
                shutdownReturned.countDown();
            }
        }, "luna-shutdown-before-close-shutdown-caller");
        CountDownLatch callerReturned = new CountDownLatch(1);
        AtomicReference<Throwable> closeFailure = new AtomicReference<>();
        Thread caller = new Thread(() -> {
            try {
                channel.close();
            } catch (Throwable t) {
                closeFailure.set(t);
            } finally {
                callerReturned.countDown();
            }
        }, "luna-shutdown-before-close-caller");

        try {
            assertTrue(reservation.isActive());
            assertEquals(1, executor.getActiveResourceReservations());
            shutdownCaller.start();
            assertTrue(shutdownReturned.await(SHUTDOWN_WAIT_SECONDS, TimeUnit.SECONDS),
                    "Shutdown must finish while an already granted reservation still belongs to its caller");
            assertNull(shutdownFailure.get());
            assertTrue(executor.isShutdown());

            caller.start();
            assertTrue(delegate.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "A pre-shutdown reservation must still admit cleanup after shutdown begins");
            assertTrue(callerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "The channel close caller must return while native close remains blocked");

            // Keep releaseClose held until after caller completion and all ownership assertions.
            assertEquals(1, delegate.releaseClose().getCount(), "Native close latch must still be held");
            assertNull(closeFailure.get());
            assertFalse(reservation.isActive(),
                    "An accepted close transfers the permit from the active lane to the pending lane");
            assertTrue(channel.isClosed());
            assertFalse(channel.isOpen());
            assertTrue(delegate.physicalHandleOpen(), "The OS handle remains live while native close is held");
            assertEquals(1, delegate.closeCalls());
            assertEquals(0, executor.getActiveResourceReservations(),
                    "The transferred handle no longer occupies the active-reservation lane");
            assertEquals(1, executor.getPendingCleanupObligations());
            assertEquals(1, executor.getActiveCleanupWorkers());
            assertEquals(0, executor.getActualOutstandingWorkers());

            delegate.releaseClose().countDown();
            assertTrue(delegate.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            assertFalse(delegate.physicalHandleOpen());
            assertFalse(reservation.isActive(), "Physical close completion releases the reservation");
            assertEquals(1, delegate.closeCalls(), "Physical close must occur exactly once");
        } finally {
            delegate.releaseClose().countDown();
            joinOrInterrupt(caller);
            if (delegate.closeStarted().getCount() == 0) {
                delegate.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS);
            } else if (reservation.isActive()) {
                // The close caller did not transfer ownership; finish fixture cleanup before releasing its permit.
                try {
                    delegate.close();
                } catch (IOException ignored) {
                } finally {
                    reservation.release();
                }
            }
            joinOrInterrupt(shutdownCaller);
            reservation.release();
            executor.shutdown();
        }
    }

    @Test
    @DisplayName("Cleanup rejection leaves the resource caller-owned")
    void cleanupRejectionAfterShutdownLeavesResourceCallerOwned() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 1);
        CountDownLatch releaseClose = new CountDownLatch(1);
        BlockingCloseResource resource = new BlockingCloseResource(releaseClose);
        CountDownLatch callerReturned = new CountDownLatch(1);
        AtomicReference<Boolean> accepted = new AtomicReference<>();
        AtomicReference<Throwable> callerFailure = new AtomicReference<>();
        Thread caller = new Thread(() -> {
            try {
                accepted.set(executor.executeCleanupAsync(resource, "luna-rejected-after-shutdown"));
            } catch (Throwable t) {
                callerFailure.set(t);
            } finally {
                callerReturned.countDown();
            }
        }, "luna-rejected-cleanup-caller");

        try {
            executor.shutdown();
            caller.start();
            assertTrue(callerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Rejected cleanup must return while any physical close latch remains held");
            assertNull(callerFailure.get());
            assertEquals(Boolean.FALSE, accepted.get(), "Shutdown executor must reject new cleanup work");
            assertEquals(1, releaseClose.getCount(), "The rejected resource's close latch remains held");
            assertEquals(0, resource.closeCalls(), "Rejected cleanup must not dispose a resource it does not own");
            assertEquals(0, executor.getActualOutstandingWorkers());
            assertEquals(0, executor.getActiveCleanupWorkers());
            assertEquals(0, executor.getPendingCleanupObligations());
            assertEquals(0, executor.getActiveResourceReservations());

            // The original owner remains responsible for disposal after rejection.
            releaseClose.countDown();
            resource.close();
            assertEquals(1, resource.closeCalls());
        } finally {
            releaseClose.countDown();
            joinOrInterrupt(caller);
            executor.shutdown();
        }
    }

    @Test
    @DisplayName("Shutdown preserves blocked cleanup workers and drains already queued obligations")
    void shutdownDrainsQueuedCleanupWhilePhysicalClosesAreBlocked() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 3);
        CountDownLatch readStarted = new CountDownLatch(1);
        CountDownLatch releaseRead = new CountDownLatch(1);
        AtomicReference<Throwable> readFailure = new AtomicReference<>();
        Thread readCaller = new Thread(() -> {
            try {
                executor.executeRead(() -> {
                    readStarted.countDown();
                    awaitIgnoringInterrupt(releaseRead);
                    return 1;
                });
            } catch (MediaUnavailableException expectedOnForcedShutdown) {
                // Shutdown interrupts the main IO worker; the test only uses it to fill that lane.
            } catch (Throwable unexpected) {
                readFailure.set(unexpected);
            }
        }, "luna-blocked-read-caller");

        CountDownLatch releaseFirst = new CountDownLatch(1);
        CountDownLatch releaseSecond = new CountDownLatch(1);
        BlockingCloseResource first = new BlockingCloseResource(releaseFirst);
        BlockingCloseResource second = new BlockingCloseResource(releaseSecond);
        AtomicInteger queuedCloseCalls = new AtomicInteger();
        AutoCloseable queued = queuedCloseCalls::incrementAndGet;
        AtomicInteger rejectedCloseCalls = new AtomicInteger();
        AutoCloseable rejected = rejectedCloseCalls::incrementAndGet;
        CountDownLatch shutdownReturned = new CountDownLatch(1);
        AtomicReference<Throwable> shutdownFailure = new AtomicReference<>();
        Thread shutdownCaller = new Thread(() -> {
            try {
                executor.shutdown();
            } catch (Throwable t) {
                shutdownFailure.set(t);
            } finally {
                shutdownReturned.countDown();
            }
        }, "luna-blocked-queue-shutdown-caller");

        try {
            readCaller.start();
            assertTrue(readStarted.await(WAIT_SECONDS, TimeUnit.SECONDS), "Main IO worker must be occupied");
            assertEquals(1, executor.getActualOutstandingWorkers());

            assertTrue(executor.executeCleanupAsync(first, "luna-blocker-1"));
            assertTrue(executor.executeCleanupAsync(second, "luna-blocker-2"));
            assertTrue(first.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(second.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(executor.executeCleanupAsync(queued, "luna-queued-cleanup"));

            assertEquals(3, executor.getPendingCleanupObligations(),
                    "Two active closes and one queued close consume exactly three obligations");
            assertEquals(2, executor.getActiveCleanupWorkers());
            assertEquals(1, executor.getActualOutstandingWorkers());
            assertEquals(0, queuedCloseCalls.get(), "Queued cleanup must wait behind both held workers");

            shutdownCaller.start();
            assertTrue(shutdownReturned.await(SHUTDOWN_WAIT_SECONDS, TimeUnit.SECONDS),
                    "Shutdown must return within its bounded drain window while physical closes stay blocked");
            assertNull(shutdownFailure.get());
            assertTrue(executor.isShutdown());
            assertEquals(3, executor.getPendingCleanupObligations(),
                    "Shutdown must not discard already accepted obligations");
            assertEquals(2, executor.getActiveCleanupWorkers());
            assertEquals(1, releaseFirst.getCount(), "First native close must remain held after shutdown returns");
            assertEquals(1, releaseSecond.getCount(), "Second native close must remain held after shutdown returns");
            assertEquals(0, queuedCloseCalls.get());

            assertFalse(executor.executeCleanupAsync(rejected, "luna-post-shutdown-rejection"));
            assertEquals(0, rejectedCloseCalls.get(), "Rejected post-shutdown work remains caller-owned");
            assertEquals(3, executor.getPendingCleanupObligations(),
                    "Rejected work must not corrupt accepted-obligation accounting");
            rejected.close();
            assertEquals(1, rejectedCloseCalls.get());

            releaseFirst.countDown();
            releaseSecond.countDown();
            assertTrue(first.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(second.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            long queuedDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WAIT_SECONDS);
            while (queuedCloseCalls.get() == 0 && System.nanoTime() < queuedDeadline) {
                Thread.sleep(5);
            }
            assertEquals(1, queuedCloseCalls.get(), "Accepted queued cleanup must drain during shutdown");

            releaseRead.countDown();
            joinOrInterrupt(readCaller);
            joinOrInterrupt(shutdownCaller);
            assertNull(readFailure.get(), "The held main worker must finish without an unexpected error");
            assertTrue(awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            assertEquals(1, first.closeCalls());
            assertEquals(1, second.closeCalls());
            assertEquals(0, executor.getActualOutstandingWorkers());
            assertEquals(0, executor.getPendingCleanupObligations());
            assertEquals(0, executor.getActiveCleanupWorkers());
            assertEquals(0, executor.getActiveResourceReservations());
        } finally {
            releaseFirst.countDown();
            releaseSecond.countDown();
            releaseRead.countDown();
            joinOrInterrupt(shutdownCaller);
            joinOrInterrupt(readCaller);
            executor.shutdown();
        }
    }

    @Test
    @DisplayName("Rejected channel close preserves ownership and succeeds on explicit retry")
    void rejectedChannelCloseCanBeRetriedAfterCleanupCapacityReturns() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 3);
        CountDownLatch readStarted = new CountDownLatch(1);
        CountDownLatch releaseRead = new CountDownLatch(1);
        Thread readCaller = new Thread(() -> {
            try {
                executor.executeRead(() -> {
                    readStarted.countDown();
                    awaitIgnoringInterrupt(releaseRead);
                    return 1;
                });
            } catch (Throwable ignored) {
                // The occupied worker is only a deterministic way to route cleanup to the cleanup lane.
            }
        }, "luna-retry-blocked-read-caller");

        CountDownLatch releaseFirst = new CountDownLatch(1);
        CountDownLatch releaseSecond = new CountDownLatch(1);
        BlockingCloseResource first = new BlockingCloseResource(releaseFirst);
        BlockingCloseResource second = new BlockingCloseResource(releaseSecond);
        AtomicInteger queuedCloseCalls = new AtomicInteger();
        AutoCloseable queued = queuedCloseCalls::incrementAndGet;
        BlockingCloseFileChannel delegate = new BlockingCloseFileChannel(
                FileChannel.open(Files.write(tempDir.resolve("retry-close.bin"), new byte[]{9}),
                        StandardOpenOption.READ));
        DriveSeekableByteChannel channel = new DriveSeekableByteChannel(delegate, executor);
        CountDownLatch retryCallerReturned = new CountDownLatch(1);
        AtomicReference<Throwable> retryFailure = new AtomicReference<>();
        CountDownLatch rejectedCallerReturned = new CountDownLatch(1);
        AtomicReference<Throwable> rejectedFailure = new AtomicReference<>();
        Thread rejectedCaller = new Thread(() -> {
            try {
                channel.close();
            } catch (Throwable t) {
                rejectedFailure.set(t);
            } finally {
                rejectedCallerReturned.countDown();
            }
        }, "luna-rejected-channel-close-caller");
        Thread retryCaller = null;

        try {
            readCaller.start();
            assertTrue(readStarted.await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertEquals(1, executor.getActualOutstandingWorkers());

            assertTrue(executor.executeCleanupAsync(first, "luna-retry-blocker-1"));
            assertTrue(executor.executeCleanupAsync(second, "luna-retry-blocker-2"));
            assertTrue(first.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(second.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(executor.executeCleanupAsync(queued, "luna-retry-queued"));

            assertEquals(3, executor.getPendingCleanupObligations());
            assertEquals(2, executor.getActiveCleanupWorkers());
            assertEquals(1, executor.getActualOutstandingWorkers());

            rejectedCaller.start();
            assertTrue(rejectedCallerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Rejected channel close must return without waiting on the delegate");
            assertInstanceOf(IOException.class, rejectedFailure.get(),
                    "A full cleanup budget must reject the channel close");
            assertFalse(channel.isClosed(), "Rejected close must restore wrapper state so it can be retried");
            assertTrue(channel.isOpen(), "The rejected channel remains caller-owned and usable");
            assertTrue(delegate.physicalHandleOpen());
            assertEquals(0, delegate.closeCalls(), "Rejected close must not invoke the delegate");
            assertEquals(3, executor.getPendingCleanupObligations(), "Rejected close consumes no obligation slot");
            assertEquals(2, executor.getActiveCleanupWorkers());

            // Free one slot, and wait until its worker has admitted the previously queued close.
            releaseFirst.countDown();
            assertTrue(first.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            long capacityDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WAIT_SECONDS);
            while ((queuedCloseCalls.get() == 0 || executor.getPendingCleanupObligations() > 1)
                    && System.nanoTime() < capacityDeadline) {
                Thread.sleep(5);
            }
            assertEquals(1, queuedCloseCalls.get(), "Previously queued cleanup must finish before retry");
            assertEquals(1, executor.getPendingCleanupObligations(),
                    "Only the second blocked close remains before the explicit retry");

            retryCaller = new Thread(() -> {
                try {
                    channel.close();
                } catch (Throwable t) {
                    retryFailure.set(t);
                } finally {
                    retryCallerReturned.countDown();
                }
            }, "luna-explicit-close-retry-caller");
            retryCaller.start();
            assertTrue(delegate.closeStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Explicit retry must hand the delegate to the cleanup lane");
            assertTrue(retryCallerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Retry caller must finish while the physical close latch remains held");

            // Do not release the native close until after proving retry completion and exact handoff.
            assertEquals(1, delegate.releaseClose().getCount(), "Native close must still be blocked");
            assertNull(retryFailure.get());
            assertTrue(channel.isClosed());
            assertFalse(channel.isOpen());
            assertTrue(delegate.physicalHandleOpen());
            assertEquals(1, delegate.closeCalls());
            assertEquals(2, executor.getPendingCleanupObligations(),
                    "The remaining blocker plus retried channel close own two pending obligations");
            assertEquals(2, executor.getActiveCleanupWorkers());
            assertEquals(1, executor.getActualOutstandingWorkers());

            delegate.releaseClose().countDown();
            releaseSecond.countDown();
            assertTrue(delegate.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(second.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertEquals(1, queuedCloseCalls.get(), "Queued cleanup was drained exactly once");
            releaseRead.countDown();
            joinOrInterrupt(readCaller);
            joinOrInterrupt(retryCaller);
            assertTrue(awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            assertFalse(delegate.physicalHandleOpen());
            assertEquals(1, delegate.closeCalls(), "Explicit retry closes the delegate exactly once");
            assertEquals(1, first.closeCalls());
            assertEquals(1, second.closeCalls());
            assertEquals(0, executor.getPendingCleanupObligations());
            assertEquals(0, executor.getActiveCleanupWorkers());
            assertEquals(0, executor.getActualOutstandingWorkers());
            assertEquals(0, executor.getActiveResourceReservations());
        } finally {
            delegate.releaseClose().countDown();
            releaseFirst.countDown();
            releaseSecond.countDown();
            releaseRead.countDown();
            joinOrInterrupt(retryCaller);
            joinOrInterrupt(rejectedCaller);
            joinOrInterrupt(readCaller);
            if (delegate.closeStarted().getCount() == 0) {
                delegate.closeCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS);
            } else if (delegate.physicalHandleOpen()) {
                // A failed assertion may leave this channel with caller ownership; close it in fixture cleanup.
                try {
                    delegate.close();
                } catch (IOException ignored) {
                }
            }
            executor.shutdown();
        }
    }

    @Test
    @DisplayName("A failed physical close stays accounted until one non-blocking retry disposes it")
    void failedPhysicalCloseRemainsOwnedAndAccounted() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 1);
        DriveResourceReservation reservation = executor.acquireReservation();
        Path file = Files.write(tempDir.resolve("retry-failed-native-close.bin"), new byte[]{3, 4});
        FileChannel raw = FileChannel.open(file, StandardOpenOption.READ);
        FailOnceCloseResource resource = new FailOnceCloseResource(raw);
        CountDownLatch firstCallerReturned = new CountDownLatch(1);
        AtomicReference<Boolean> firstCloseAccepted = new AtomicReference<>();
        AtomicReference<Throwable> firstCallerFailure = new AtomicReference<>();
        Thread firstCaller = new Thread(() -> {
            try {
                firstCloseAccepted.set(reservation.closeAsync(resource, "luna-first-failing-close"));
            } catch (Throwable t) {
                firstCallerFailure.set(t);
            } finally {
                firstCallerReturned.countDown();
            }
        }, "luna-failed-close-caller");
        CountDownLatch retryCallerReturned = new CountDownLatch(1);
        AtomicReference<Boolean> retryAccepted = new AtomicReference<>();
        AtomicReference<Throwable> retryCallerFailure = new AtomicReference<>();
        Thread retryCaller = null;

        try {
            firstCaller.start();
            assertTrue(resource.firstCloseStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "First close attempt must enter the cleanup lane");
            assertTrue(firstCallerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "closeAsync must return while the first physical-close latch remains held");
            assertEquals(Boolean.TRUE, firstCloseAccepted.get());
            assertNull(firstCallerFailure.get());
            assertEquals(1, resource.releaseFirstClose().getCount(),
                    "The first physical-close latch must still be held at caller return");
            assertFalse(reservation.isActive(), "Accepted close transfers reservation ownership");
            assertEquals(0, executor.getActiveResourceReservations());
            assertEquals(1, executor.getPendingCleanupObligations(),
                    "The in-flight close owns the same bounded slot before it either succeeds or fails");

            resource.releaseFirstClose().countDown();
            long failureDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WAIT_SECONDS);
            while ((executor.getFailedCleanupObligations() == 0
                    || executor.getActiveCleanupWorkers() != 0)
                    && System.nanoTime() < failureDeadline) {
                Thread.sleep(5);
            }
            assertEquals(1, resource.attempts());
            assertTrue(reservation.hasFailedCleanup(), "The failed reservation must expose its retained retry state");
            assertEquals(1, executor.getFailedCleanupObligations(),
                    "The failure must remain observable instead of being reported as disposed");
            assertTrue(resource.physicalHandleOpen(), "The failed attempt did not physically close the file handle");
            assertEquals(0, executor.getActiveResourceReservations());
            assertEquals(1, executor.getPendingCleanupObligations(),
                    "The retained failed close remains charged until physical disposal succeeds");
            assertEquals(0, executor.getActiveCleanupWorkers());

            DriveResourceReservation unexpectedAdmission = null;
            try {
                unexpectedAdmission = executor.acquireReservation();
            } catch (MediaUnavailableException expectedAtCapacity) {
                // A retained failed close consumes the only admission slot.
            }
            assertNull(unexpectedAdmission,
                    "A failed close must continue to consume bounded capacity until disposal succeeds");
            if (unexpectedAdmission != null) {
                unexpectedAdmission.release();
            }

            retryCaller = new Thread(() -> {
                try {
                    retryAccepted.set(reservation.retryCleanup());
                } catch (Throwable t) {
                    retryCallerFailure.set(t);
                } finally {
                    retryCallerReturned.countDown();
                }
            }, "luna-failed-close-retry-caller");
            retryCaller.start();
            assertTrue(resource.retryCloseStarted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Explicit retry must start the retained physical close");
            assertTrue(retryCallerReturned.await(WAIT_SECONDS, TimeUnit.SECONDS),
                    "Retry must return while the physical close latch remains held");
            assertEquals(Boolean.TRUE, retryAccepted.get());
            assertNull(retryCallerFailure.get());
            assertEquals(1, resource.releaseRetryClose().getCount(),
                    "The retry close latch must still be held at caller return");
            assertEquals(1, executor.getPendingCleanupObligations(),
                    "Retry does not double-charge or release the retained obligation before close succeeds");
            assertEquals(1, executor.getFailedCleanupObligations());
            assertTrue(resource.physicalHandleOpen());

            // A second retry while the first retry is still blocked must not enqueue a duplicate close.
            boolean duplicateRetryAccepted = reservation.retryCleanup();
            resource.releaseRetryClose().countDown();
            if (duplicateRetryAccepted) {
                assertTrue(resource.duplicateRetryCompleted().await(WAIT_SECONDS, TimeUnit.SECONDS),
                        "Every accepted retry task must reach the injected close action");
            }
            assertTrue(awaitQuiescent(executor, WAIT_SECONDS, TimeUnit.SECONDS),
                    "Successful retry must clear all lifecycle accounting");
            joinOrInterrupt(firstCaller);
            joinOrInterrupt(retryCaller);

            assertAll("retry disposition and accounting",
                    () -> assertFalse(duplicateRetryAccepted,
                            "A retry already in flight must not submit a second physical close"),
                    () -> assertEquals(2, resource.attempts(),
                            "One initial failure and one successful retry are expected"),
                    () -> assertFalse(resource.physicalHandleOpen(),
                            "Retry must physically dispose the original handle"),
                    () -> assertFalse(reservation.hasFailedCleanup(),
                            "Successful disposal clears the reservation failure state"),
                    () -> assertEquals(0, executor.getFailedCleanupObligations()),
                    () -> assertEquals(0, executor.getPendingCleanupObligations()),
                    () -> assertEquals(0, executor.getActiveResourceReservations()),
                    () -> assertEquals(0, executor.getActiveCleanupWorkers()),
                    () -> assertEquals(0, executor.getActualOutstandingWorkers()));
        } finally {
            resource.releaseFirstClose().countDown();
            resource.releaseRetryClose().countDown();
            joinOrInterrupt(firstCaller);
            joinOrInterrupt(retryCaller);

            // If an assertion failed before retry was submitted, retry the retained obligation so
            // this isolated executor and its temporary OS handle do not leak into later tests.
            if (executor.getPendingCleanupObligations() > 0
                    && !Boolean.TRUE.equals(retryAccepted.get())
                    && awaitCleanupWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS)) {
                reservation.retryCleanup();
            }
            long retryCleanupDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WAIT_SECONDS);
            while (executor.getPendingCleanupObligations() > 0 && System.nanoTime() < retryCleanupDeadline) {
                Thread.sleep(5);
            }
            if (raw.isOpen() && awaitCleanupWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS)
                    && executor.getPendingCleanupObligations() == 0) {
                raw.close();
            }
            reservation.release();
            executor.shutdown();
        }
    }

    @Test
    @DisplayName("Unreserved failed cleanup cannot grow retained obligations beyond admission capacity")
    void failedMainWorkerCleanupCannotExceedConfiguredCapacity() throws Exception {
        DriveIoExecutor executor = newExecutor(1, 1);
        FailOnceCleanupAction first = new FailOnceCleanupAction();
        FailOnceCleanupAction second = new FailOnceCleanupAction();
        try {
            assertTrue(executor.executeCleanupAsync(first, "luna-capacity-first-failure"));
            assertTrue(first.firstAttemptFinished().await(WAIT_SECONDS, TimeUnit.SECONDS));
            assertTrue(awaitMainWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            assertEquals(1, executor.getPendingCleanupObligations());
            assertEquals(1, executor.getFailedCleanupObligations());
            assertEquals(1, executor.getRetainedFailedResources().size());

            boolean secondAccepted = executor.executeCleanupAsync(second, "luna-capacity-overflow-failure");
            if (secondAccepted) {
                assertTrue(second.firstAttemptFinished().await(WAIT_SECONDS, TimeUnit.SECONDS));
                assertTrue(awaitMainWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS));
            }

            assertFalse(secondAccepted,
                    "At capacity, an unreserved cleanup submission must be rejected without closing caller-owned resource");
            assertEquals(0, second.attempts(), "Rejected overflow cleanup must not call close()");
            assertEquals(1, executor.getPendingCleanupObligations());
            assertEquals(1, executor.getFailedCleanupObligations());
            assertEquals(1, executor.getRetainedFailedResources().size());
        } finally {
            if (awaitCleanupWorkersStopped(executor, WAIT_SECONDS, TimeUnit.SECONDS)
                    && executor.getPendingCleanupObligations() > 0) {
                executor.retryFailedCleanups();
                long retryDeadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(WAIT_SECONDS);
                while (executor.getPendingCleanupObligations() > 0 && System.nanoTime() < retryDeadline) {
                    Thread.sleep(5);
                }
            }
            executor.shutdown();
        }
    }
}
