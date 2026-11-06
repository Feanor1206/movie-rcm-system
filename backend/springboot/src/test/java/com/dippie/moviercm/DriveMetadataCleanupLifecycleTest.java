package com.dippie.moviercm;

import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.service.storage.DriveCircuitBreaker;
import com.dippie.moviercm.service.storage.DriveIoExecutor;
import com.dippie.moviercm.service.storage.DriveSeekableByteChannel;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.ClosedChannelException;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.ReadableByteChannel;
import java.nio.channels.SeekableByteChannel;
import java.nio.channels.WritableByteChannel;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.BooleanSupplier;

import static org.junit.jupiter.api.Assertions.*;

/**
 * DRIVE-01-F03 / R1 Acceptance Test Suite.
 *
 * Recreates and exhaustively verifies the reviewer's reproduction scenario in
 * docs/reviews/repro/DRIVE_F02_position_close.java:
 *
 * 1. Simulates kernel FileChannel operations (position(long), size()) blocked on a release latch.
 * 2. Caller invokes metadata operations in a try-with-resources block under finite deadlines.
 * 3. When the operation deadline expires, an IOException is thrown and try-with-resources triggers close().
 * 4. Verifies:
 *    a) Caller thread is NOT blocked in close()! Exits try-with-resources promptly (<250ms).
 *    b) actualOutstandingWorkers accurately reflects 1 worker still running the in-flight kernel operation.
 *    c) After releaseLatch is counted down, the worker finishes, closes the delegate exactly once,
 *       and actualOutstandingWorkers safely returns to 0.
 *    d) Subsequent channel operations throw ClosedChannelException.
 *    e) Repeated cycles prove zero leakage of workers or file descriptors.
 */
@DisplayName("DriveMetadataCleanupLifecycleTest - R1 Metadata Stall Lifecycle & Exactly-Once Cleanup")
public class DriveMetadataCleanupLifecycleTest {

    /**
     * Controllable FileChannel simulating uninterruptible native WinFsp / CGO kernel operations.
     */
    static class BlockingFile extends FileChannel {
        final CountDownLatch releaseLatch = new CountDownLatch(1);
        final CountDownLatch opStarted = new CountDownLatch(1);
        final AtomicInteger closeCount = new AtomicInteger(0);
        final boolean blockOnPosition;
        final boolean blockOnSize;
        private volatile long currentPosition = 0;

        BlockingFile(boolean blockOnPosition, boolean blockOnSize) {
            this.blockOnPosition = blockOnPosition;
            this.blockOnSize = blockOnSize;
        }

        BlockingFile() {
            this(true, false);
        }

        void waitForRelease() {
            while (true) {
                try {
                    releaseLatch.await();
                    return;
                } catch (InterruptedException ignored) {
                }
            }
        }

        int getCloseCount() {
            return closeCount.get();
        }

        @Override
        public int read(ByteBuffer b) {
            return -1;
        }

        @Override
        protected void implCloseChannel() {
            closeCount.incrementAndGet();
            waitForRelease();
        }

        @Override
        public long position() {
            return currentPosition;
        }

        @Override
        public FileChannel position(long n) {
            opStarted.countDown();
            if (blockOnPosition) {
                waitForRelease();
            }
            this.currentPosition = n;
            return this;
        }

        @Override
        public long size() {
            opStarted.countDown();
            if (blockOnSize) {
                waitForRelease();
            }
            return 1024L;
        }

        @Override
        public FileChannel truncate(long n) {
            throw new UnsupportedOperationException();
        }

        @Override
        public void force(boolean m) {
        }

        @Override
        public long transferTo(long p, long c, WritableByteChannel t) {
            throw new UnsupportedOperationException();
        }

        @Override
        public long transferFrom(ReadableByteChannel s, long p, long c) {
            throw new UnsupportedOperationException();
        }

        @Override
        public int read(ByteBuffer b, long p) {
            return read(b);
        }

        @Override
        public int write(ByteBuffer b, long p) {
            throw new UnsupportedOperationException();
        }

        @Override
        public int write(ByteBuffer b) {
            throw new UnsupportedOperationException();
        }

        @Override
        public long read(ByteBuffer[] b, int o, int l) {
            throw new UnsupportedOperationException();
        }

        @Override
        public long write(ByteBuffer[] b, int o, int l) {
            throw new UnsupportedOperationException();
        }

        @Override
        public MappedByteBuffer map(MapMode m, long p, long s) {
            throw new UnsupportedOperationException();
        }

        @Override
        public FileLock lock(long p, long s, boolean sh) {
            throw new UnsupportedOperationException();
        }

        @Override
        public FileLock tryLock(long p, long s, boolean sh) {
            throw new UnsupportedOperationException();
        }
    }

    private boolean waitForWorkerCount(DriveIoExecutor executor, int expected, long maxWaitMs) throws InterruptedException {
        long deadline = System.currentTimeMillis() + maxWaitMs;
        while (System.currentTimeMillis() < deadline) {
            if (executor.getActualOutstandingWorkers() == expected) {
                return true;
            }
            Thread.sleep(20);
        }
        return executor.getActualOutstandingWorkers() == expected;
    }

    private boolean waitForCondition(BooleanSupplier condition, long maxWaitMs) throws InterruptedException {
        long deadline = System.currentTimeMillis() + maxWaitMs;
        while (System.currentTimeMillis() < deadline) {
            if (condition.getAsBoolean()) {
                return true;
            }
            Thread.sleep(20);
        }
        return condition.getAsBoolean();
    }

    @Test
    @DisplayName("Test 1: Stalled position(long) deadline timeout -> Non-blocking caller close -> Exactly-once cleanup")
    void testPositionStall_Timeout_NonBlockingClose_ExactlyOnceDelegateClose() throws Exception {
        BlockingFile raw = new BlockingFile(true, false);
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(10, 10000);
        // Matching reviewer setup: maxWorkers = 1, timeout = 40ms
        DriveIoExecutor io = new DriveIoExecutor(40, 40, 1, breaker);
        ExecutorService callerExecutor = Executors.newSingleThreadExecutor();
        AtomicBoolean positionFailed = new AtomicBoolean(false);
        AtomicReference<DriveSeekableByteChannel> channelRef = new AtomicReference<>();

        try {
            long start = System.currentTimeMillis();
            Future<?> future = callerExecutor.submit(() -> {
                try (DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io)) {
                    channelRef.set(channel);
                    try {
                        channel.position(1);
                    } catch (IOException expected) {
                        positionFailed.set(true);
                    }
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            });

            // a) Caller thread MUST NOT be blocked in close()!
            // Deadline is 40ms. Try-with-resources must complete and future must resolve in < 250ms.
            assertDoesNotThrow(() -> future.get(250, TimeUnit.MILLISECONDS),
                    "Caller thread must complete try-with-resources promptly without blocking in close()");
            long elapsed = System.currentTimeMillis() - start;

            assertTrue(future.isDone(), "Caller future must be done");
            assertTrue(positionFailed.get(), "channel.position(1) must throw IOException on deadline expiration");
            assertTrue(elapsed < 250, "Caller must exit try-with-resources within 250ms (actual: " + elapsed + "ms)");

            // b) ioExecutor.getActualOutstandingWorkers() accurately reflects 1 worker still running stalled kernel operation
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must accurately reflect 1 worker still running stalled position()");

            // Delegate channel should not have completed close while kernel IO is stuck
            assertEquals(0, raw.getCloseCount(),
                    "Delegate implCloseChannel must not have completed while latch is held");

            // c) Release latch: background worker finishes, performs exactly-once delegate close, workers return to 0
            raw.releaseLatch.countDown();

            boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
            assertTrue(returnedToZero, "actualOutstandingWorkers must safely return to 0 after latch release");
            assertEquals(0, io.getActualOutstandingWorkers());

            boolean closedOnce = waitForCondition(() -> raw.getCloseCount() == 1, 3000);
            assertTrue(closedOnce, "Delegate must be closed exactly once after background worker unblocks");
            assertEquals(1, raw.getCloseCount(), "Delegate closeCount must be exactly 1");

            // d) Verify channel operations after close throw ClosedChannelException
            DriveSeekableByteChannel ch = channelRef.get();
            assertNotNull(ch, "Channel reference must be captured");
            assertFalse(ch.isOpen(), "Channel must report isOpen() == false");
            assertTrue(ch.isClosed(), "Channel must report isClosed() == true");

            assertThrows(ClosedChannelException.class, ch::position,
                    "position() on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> ch.position(10),
                    "position(long) on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, ch::size,
                    "size() on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> ch.read(ByteBuffer.allocate(16)),
                    "read() on closed channel must throw ClosedChannelException");

            // Idempotent close
            assertDoesNotThrow(ch::close, "Subsequent channel.close() calls must be idempotent");
            assertEquals(1, raw.getCloseCount(), "Subsequent close() must not call delegate.close() again");
        } finally {
            raw.releaseLatch.countDown();
            callerExecutor.shutdownNow();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 2: Stalled size() deadline timeout -> Non-blocking caller close -> Exactly-once cleanup")
    void testSizeStall_Timeout_NonBlockingClose_ExactlyOnceDelegateClose() throws Exception {
        BlockingFile raw = new BlockingFile(false, true); // blockOnSize = true
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(10, 10000);
        DriveIoExecutor io = new DriveIoExecutor(40, 40, 1, breaker);
        ExecutorService callerExecutor = Executors.newSingleThreadExecutor();
        AtomicBoolean sizeFailed = new AtomicBoolean(false);
        AtomicReference<DriveSeekableByteChannel> channelRef = new AtomicReference<>();

        try {
            long start = System.currentTimeMillis();
            Future<?> future = callerExecutor.submit(() -> {
                try (DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io)) {
                    channelRef.set(channel);
                    try {
                        channel.size();
                    } catch (IOException expected) {
                        sizeFailed.set(true);
                    }
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            });

            // a) Caller thread MUST NOT be blocked in close()!
            assertDoesNotThrow(() -> future.get(250, TimeUnit.MILLISECONDS),
                    "Caller thread must complete try-with-resources promptly without blocking in close()");
            long elapsed = System.currentTimeMillis() - start;

            assertTrue(future.isDone(), "Caller future must be done");
            assertTrue(sizeFailed.get(), "channel.size() must throw IOException on deadline expiration");
            assertTrue(elapsed < 250, "Caller must exit try-with-resources within 250ms (actual: " + elapsed + "ms)");

            // b) ioExecutor.getActualOutstandingWorkers() accurately reflects 1 worker still running stalled kernel size()
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must accurately reflect 1 worker still running stalled size()");

            assertEquals(0, raw.getCloseCount(),
                    "Delegate implCloseChannel must not have completed while latch is held");

            // c) Release latch: background worker finishes, performs exactly-once delegate close, workers return to 0
            raw.releaseLatch.countDown();

            boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
            assertTrue(returnedToZero, "actualOutstandingWorkers must return to 0 after latch release");
            assertEquals(0, io.getActualOutstandingWorkers());

            boolean closedOnce = waitForCondition(() -> raw.getCloseCount() == 1, 3000);
            assertTrue(closedOnce, "Delegate must be closed exactly once after background worker unblocks");
            assertEquals(1, raw.getCloseCount(), "Delegate closeCount must be exactly 1");

            // d) Verify channel operations after close throw ClosedChannelException
            DriveSeekableByteChannel ch = channelRef.get();
            assertNotNull(ch, "Channel reference must be captured");
            assertFalse(ch.isOpen(), "Channel must report isOpen() == false");
            assertTrue(ch.isClosed(), "Channel must report isClosed() == true");

            assertThrows(ClosedChannelException.class, ch::position,
                    "position() on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> ch.position(10),
                    "position(long) on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, ch::size,
                    "size() on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> ch.read(ByteBuffer.allocate(16)),
                    "read() on closed channel must throw ClosedChannelException");

            assertDoesNotThrow(ch::close, "Subsequent channel.close() calls must be idempotent");
            assertEquals(1, raw.getCloseCount(), "Subsequent close() must not call delegate.close() again");
        } finally {
            raw.releaseLatch.countDown();
            callerExecutor.shutdownNow();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 3: Repeated cycles of stalled metadata operations show zero worker/descriptor leak")
    void testRepeatedCycles_NoWorkerOrFdLeak() throws Exception {
        final int CYCLES = 10;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(CYCLES * 2, 60000);
        DriveIoExecutor io = new DriveIoExecutor(40, 40, 1, breaker);
        ExecutorService callerExecutor = Executors.newSingleThreadExecutor();
        List<BlockingFile> files = new ArrayList<>();

        try {
            for (int i = 0; i < CYCLES; i++) {
                final int cycleIndex = i;
                BlockingFile raw = new BlockingFile(true, false);
                files.add(raw);
                AtomicBoolean failed = new AtomicBoolean(false);
                AtomicReference<DriveSeekableByteChannel> channelRef = new AtomicReference<>();

                Future<?> future = callerExecutor.submit(() -> {
                    try (DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io)) {
                        channelRef.set(channel);
                        try {
                            channel.position(100L + cycleIndex);
                        } catch (IOException expected) {
                            failed.set(true);
                        }
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                });

                // Caller must finish try-with-resources quickly
                assertDoesNotThrow(() -> future.get(250, TimeUnit.MILLISECONDS),
                        "Cycle " + i + ": caller must exit try-with-resources within 250ms");
                assertTrue(future.isDone(), "Cycle " + i + ": caller future must be done");
                assertTrue(failed.get(), "Cycle " + i + ": operation must time out");

                // Exactly 1 worker currently occupied
                assertEquals(1, io.getActualOutstandingWorkers(),
                        "Cycle " + i + ": exactly 1 worker must be occupied during stall");

                // Release latch and wait for full reclamation
                raw.releaseLatch.countDown();

                boolean drained = waitForWorkerCount(io, 0, 3000);
                assertTrue(drained, "Cycle " + i + ": worker count must return to 0");
                assertEquals(0, io.getActualOutstandingWorkers());

                boolean closed = waitForCondition(() -> raw.getCloseCount() == 1, 3000);
                assertTrue(closed, "Cycle " + i + ": delegate must be closed exactly once");
                assertEquals(1, raw.getCloseCount());

                // Channel is closed
                DriveSeekableByteChannel ch = channelRef.get();
                assertFalse(ch.isOpen());
                assertThrows(ClosedChannelException.class, ch::position);
            }

            // After all 10 cycles, worker count must be 0 and pool healthy
            assertEquals(0, io.getActualOutstandingWorkers(), "Pool must have 0 workers after all cycles");

            // Executor remains healthy and executes a normal metadata task
            int normalResult = io.executeMetadata(() -> 999);
            assertEquals(999, normalResult, "Executor must remain fully functional for subsequent tasks");
        } finally {
            for (BlockingFile f : files) {
                f.releaseLatch.countDown();
            }
            callerExecutor.shutdownNow();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 4: Alternating position and size stalls verify lifecycle integrity under operation churn")
    void testRepeatedCyclesAlternatingPositionAndSize_NoWorkerLeak() throws Exception {
        final int CYCLES = 8;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(CYCLES * 2, 60000);
        DriveIoExecutor io = new DriveIoExecutor(40, 40, 1, breaker);
        ExecutorService callerExecutor = Executors.newSingleThreadExecutor();
        List<BlockingFile> files = new ArrayList<>();

        try {
            for (int i = 0; i < CYCLES; i++) {
                boolean stallPosition = (i % 2 == 0);
                BlockingFile raw = new BlockingFile(stallPosition, !stallPosition);
                files.add(raw);
                AtomicBoolean failed = new AtomicBoolean(false);

                final int cycleIndex = i;
                Future<?> future = callerExecutor.submit(() -> {
                    try (DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io)) {
                        try {
                            if (stallPosition) {
                                channel.position(cycleIndex * 10L);
                            } else {
                                channel.size();
                            }
                        } catch (IOException expected) {
                            failed.set(true);
                        }
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                });

                assertDoesNotThrow(() -> future.get(250, TimeUnit.MILLISECONDS),
                        "Cycle " + i + " (" + (stallPosition ? "position" : "size") + "): caller must exit within 250ms");
                assertTrue(failed.get(), "Cycle " + i + ": operation must time out");
                assertEquals(1, io.getActualOutstandingWorkers(), "Cycle " + i + ": 1 worker occupied");

                raw.releaseLatch.countDown();

                boolean drained = waitForWorkerCount(io, 0, 3000);
                assertTrue(drained, "Cycle " + i + ": worker count must return to 0");

                boolean closed = waitForCondition(() -> raw.getCloseCount() == 1, 3000);
                assertTrue(closed, "Cycle " + i + ": delegate must be closed exactly once");
                assertEquals(1, raw.getCloseCount());
            }

            assertEquals(0, io.getActualOutstandingWorkers());
        } finally {
            for (BlockingFile f : files) {
                f.releaseLatch.countDown();
            }
            callerExecutor.shutdownNow();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 5: Saturated worker pool with stalled metadata operations, fast rejection, and full recovery")
    void testConcurrentMetadataStalls_BoundedPool_FastRejectionAndFullRecovery() throws Exception {
        final int MAX_WORKERS = 5;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(15, 60000);
        DriveIoExecutor io = new DriveIoExecutor(50, 50, MAX_WORKERS, breaker);

        List<BlockingFile> files = new ArrayList<>();
        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS);
        List<Future<?>> callerFutures = new ArrayList<>();

        try {
            // Fill all worker slots with stalled position operations
            for (int i = 0; i < MAX_WORKERS; i++) {
                BlockingFile raw = new BlockingFile(true, false);
                files.add(raw);
                final int slot = i;
                Future<?> future = callerPool.submit(() -> {
                    try (DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io)) {
                        try {
                            channel.position(slot + 1);
                        } catch (IOException ignored) {
                            // Expected metadata timeout
                        }
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                });
                callerFutures.add(future);
            }

            // All callers must exit try-with-resources promptly (<1000ms for all 5)
            for (int i = 0; i < MAX_WORKERS; i++) {
                final int slot = i;
                assertDoesNotThrow(() -> callerFutures.get(slot).get(1000, TimeUnit.MILLISECONDS),
                        "Caller " + slot + " must exit try-with-resources promptly");
            }

            // All worker slots are occupied by the stalled kernel operations
            assertEquals(MAX_WORKERS, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must reach maxWorkers (" + MAX_WORKERS + ")");

            // An additional request arrives: MUST be fast-rejected immediately (<100ms) with MediaUnavailableException
            long rejectStart = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () ->
                    io.executeMetadata(() -> "rejected-task")
            );
            long rejectDuration = System.currentTimeMillis() - rejectStart;

            assertTrue(rejectDuration < 100, "Fast-rejection must take < 100ms (actual: " + rejectDuration + "ms)");
            assertTrue(ex.getMessage().contains("đạt giới hạn tối đa") || ex.getMessage().contains(String.valueOf(MAX_WORKERS)),
                    "Exception message must indicate worker limit reached: " + ex.getMessage());

            // Release all kernel latches
            for (BlockingFile f : files) {
                f.releaseLatch.countDown();
            }

            // All workers must safely return to 0
            boolean allReturned = waitForWorkerCount(io, 0, 5000);
            assertTrue(allReturned, "All workers must return to 0 after releasing latches");
            assertEquals(0, io.getActualOutstandingWorkers());

            // All delegates must have been closed exactly once
            for (int i = 0; i < MAX_WORKERS; i++) {
                final int slot = i;
                boolean closed = waitForCondition(() -> files.get(slot).getCloseCount() == 1, 3000);
                assertTrue(closed, "File " + slot + " must be closed exactly once");
                assertEquals(1, files.get(slot).getCloseCount());
            }

            // Subsequent metadata request succeeds
            String ok = io.executeMetadata(() -> "recovered-ok");
            assertEquals("recovered-ok", ok);
        } finally {
            for (BlockingFile f : files) {
                f.releaseLatch.countDown();
            }
            callerPool.shutdownNow();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 6: All SeekableByteChannel operations throw ClosedChannelException after close")
    void testAllOperationsThrowClosedChannelExceptionAfterClose() throws Exception {
        BlockingFile raw = new BlockingFile(false, false);
        DriveCircuitBreaker breaker = new DriveCircuitBreaker();
        DriveIoExecutor io = new DriveIoExecutor(100, 100, 2, breaker);

        DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io);

        try {
            assertTrue(channel.isOpen(), "Channel must be open initially");
            assertFalse(channel.isClosed(), "Channel must not be closed initially");

            // Close channel explicitly
            channel.close();

            assertFalse(channel.isOpen(), "Channel must report isOpen() == false after close()");
            assertTrue(channel.isClosed(), "Channel must report isClosed() == true after close()");

            // Idempotent close
            assertDoesNotThrow(channel::close, "Subsequent close() must be idempotent");

            // All channel operations must immediately throw ClosedChannelException
            ByteBuffer buf = ByteBuffer.allocate(16);
            assertThrows(ClosedChannelException.class, () -> channel.read(buf),
                    "read() must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, channel::position,
                    "position() must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> channel.position(5L),
                    "position(long) must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, channel::size,
                    "size() must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> channel.write(buf),
                    "write() on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> channel.truncate(0L),
                    "truncate() on closed channel must throw ClosedChannelException");
        } finally {
            raw.releaseLatch.countDown();
            io.shutdown();
        }
    }
}
