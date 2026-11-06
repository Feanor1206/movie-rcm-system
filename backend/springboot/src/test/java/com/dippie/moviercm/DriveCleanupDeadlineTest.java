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
import java.nio.channels.*;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DriveCleanupDeadlineTest - Stalled Channel Cleanup & Kernel IO Deadline Verification")
public class DriveCleanupDeadlineTest {

    /**
     * Simulates uninterruptible native read and close operations waiting for that read,
     * mirroring the WinFsp / CGO kernel behavior where interrupt signals are ignored.
     */
    static class BlockingFile extends FileChannel {
        final CountDownLatch releaseLatch = new CountDownLatch(1);
        final CountDownLatch readStarted = new CountDownLatch(1);
        final CountDownLatch closeStarted = new CountDownLatch(1);
        final AtomicBoolean closeInvoked = new AtomicBoolean(false);

        void waitForRelease() {
            while (true) {
                try {
                    releaseLatch.await();
                    return;
                } catch (InterruptedException ignored) {
                }
            }
        }

        @Override
        public int read(ByteBuffer b) {
            readStarted.countDown();
            waitForRelease();
            return -1;
        }

        @Override
        protected void implCloseChannel() {
            closeStarted.countDown();
            closeInvoked.set(true);
            waitForRelease();
        }

        @Override
        public long position() {
            return 0;
        }

        @Override
        public FileChannel position(long n) {
            return this;
        }

        @Override
        public long size() {
            return 1;
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

    @Test
    @DisplayName("Test 1: Non-blocking caller close on read timeout")
    void testNonBlockingCallerCloseOnReadTimeout() throws Exception {
        BlockingFile raw = new BlockingFile();
        DriveCircuitBreaker breaker = new DriveCircuitBreaker();
        DriveIoExecutor io = new DriveIoExecutor(50, 50, 2, breaker);
        ExecutorService callerExecutor = Executors.newSingleThreadExecutor();
        AtomicBoolean readFailedWithIoException = new AtomicBoolean(false);

        try {
            long callerStart = System.currentTimeMillis();
            Future<?> callerFuture = callerExecutor.submit(() -> {
                try (DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io)) {
                    try {
                        channel.read(ByteBuffer.allocate(1));
                    } catch (IOException expected) {
                        readFailedWithIoException.set(true);
                    }
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            });

            // a) Caller thread MUST NOT be blocked in close()!
            // Read deadline is 50ms. Try-with-resources must complete and future must resolve in < 250ms.
            assertDoesNotThrow(() -> callerFuture.get(250, TimeUnit.MILLISECONDS),
                    "Caller thread must complete try-with-resources promptly without blocking on kernel release latch");
            long elapsed = System.currentTimeMillis() - callerStart;

            assertTrue(readFailedWithIoException.get(), "channel.read() must throw IOException on timeout");
            assertTrue(callerFuture.isDone(), "Caller future must be done");
            assertTrue(elapsed < 250, "Caller must complete try-with-resources within 250ms (actual: " + elapsed + "ms)");

            // b) ioExecutor.getActualOutstandingWorkers() accurately reflects 1 worker still running stalled kernel operation
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must accurately reflect 1 worker still stuck in kernel read");

            // c) When releaseLatch is released, background worker finishes and actualOutstandingWorkers returns to 0
            raw.releaseLatch.countDown();

            boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
            assertTrue(returnedToZero, "actualOutstandingWorkers must return to 0 after kernel latch is released");
            assertEquals(0, io.getActualOutstandingWorkers());
        } finally {
            raw.releaseLatch.countDown();
            callerExecutor.shutdownNow();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 2: Bounded capacity under stuck kernel IO")
    void testBoundedCapacityUnderStuckKernelIo() throws Exception {
        final int MAX_WORKERS = 10;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(15, 10000);
        DriveIoExecutor io = new DriveIoExecutor(50, 50, MAX_WORKERS, breaker);

        List<BlockingFile> files = new ArrayList<>();
        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS);
        List<Future<?>> callerFutures = new ArrayList<>();

        try {
            // Fill all 10 worker slots with stuck channel operations
            for (int i = 0; i < MAX_WORKERS; i++) {
                BlockingFile raw = new BlockingFile();
                files.add(raw);
                Future<?> future = callerPool.submit(() -> {
                    try (DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io)) {
                        try {
                            channel.read(ByteBuffer.allocate(1));
                        } catch (IOException ignored) {
                            // Expected read deadline timeout
                        }
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                });
                callerFutures.add(future);
            }

            // All caller threads must exit try-with-resources promptly (< 1000ms for all 10)
            for (Future<?> f : callerFutures) {
                assertDoesNotThrow(() -> f.get(1000, TimeUnit.MILLISECONDS),
                        "Caller threads must finish try-with-resources without blocking in close()");
            }

            // All 10 worker slots must be occupied by the stuck kernel IO
            assertEquals(MAX_WORKERS, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must reach maxWorkers (" + MAX_WORKERS + ")");

            // An 11th request arrives: MUST be fast-rejected immediately (< 100ms) with MediaUnavailableException (503)
            long rejectStart = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () ->
                    io.executeRead(() -> "task11")
            );
            long rejectDuration = System.currentTimeMillis() - rejectStart;

            assertTrue(rejectDuration < 100, "Fast-rejection must occur immediately (< 100ms), actual: " + rejectDuration + "ms");
            assertTrue(ex.getMessage().contains("đạt giới hạn tối đa") || ex.getMessage().contains(String.valueOf(MAX_WORKERS)),
                    "Exception message must mention worker limit reached: " + ex.getMessage());

            // Peak outstanding workers must remain strictly bounded at MAX_WORKERS (10)
            assertEquals(MAX_WORKERS, io.getActualOutstandingWorkers(),
                    "Worker count must remain bounded at " + MAX_WORKERS + " without creating unbounded threads");

            // Release all kernel latches and verify full recovery
            for (BlockingFile f : files) {
                f.releaseLatch.countDown();
            }

            boolean recovered = waitForWorkerCount(io, 0, 5000);
            assertTrue(recovered, "All workers must return to 0 after releasing all kernel latches");
            assertEquals(0, io.getActualOutstandingWorkers());

            // Subsequent requests must now succeed normally
            String successResult = io.executeRead(() -> "recovered-success");
            assertEquals("recovered-success", successResult);
        } finally {
            for (BlockingFile f : files) {
                f.releaseLatch.countDown();
            }
            callerPool.shutdownNow();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 3: Channel operations throw ClosedChannelException after close")
    void testChannelOperationsThrowClosedChannelExceptionAfterClose() throws Exception {
        BlockingFile raw = new BlockingFile();
        DriveCircuitBreaker breaker = new DriveCircuitBreaker();
        DriveIoExecutor io = new DriveIoExecutor(100, 100, 2, breaker);

        DriveSeekableByteChannel channel = new DriveSeekableByteChannel(raw, io);

        try {
            assertTrue(channel.isOpen(), "Channel must be open initially");

            // Close the channel
            channel.close();
            assertFalse(channel.isOpen(), "Channel must report isOpen() == false after close()");

            // Idempotent close - calling close() again must not throw an exception
            assertDoesNotThrow(() -> channel.close(), "Subsequent close() calls must be idempotent");

            // Subsequent read() must immediately throw ClosedChannelException
            ByteBuffer buf = ByteBuffer.allocate(16);
            assertThrows(ClosedChannelException.class, () -> channel.read(buf),
                    "read() on closed channel must throw ClosedChannelException");

            // Subsequent position() must immediately throw ClosedChannelException
            assertThrows(ClosedChannelException.class, () -> channel.position(),
                    "position() on closed channel must throw ClosedChannelException");

            // Subsequent position(long) must immediately throw ClosedChannelException
            assertThrows(ClosedChannelException.class, () -> channel.position(10),
                    "position(long) on closed channel must throw ClosedChannelException");

            // Subsequent size() must immediately throw ClosedChannelException
            assertThrows(ClosedChannelException.class, () -> channel.size(),
                    "size() on closed channel must throw ClosedChannelException");
        } finally {
            raw.releaseLatch.countDown();
            io.shutdown();
        }
    }
}
