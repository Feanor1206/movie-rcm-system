package com.dippie.moviercm;

import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.service.storage.DriveCircuitBreaker;
import com.dippie.moviercm.service.storage.DriveIoExecutor;
import com.dippie.moviercm.service.storage.DriveSeekableByteChannel;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DriveCleanupAdmissionRaceTest - Saturated Cleanup Admission & Disposal Race Suite")
public class DriveCleanupAdmissionRaceTest {

    @TempDir
    Path tempDir;

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

    /**
     * FileChannel decorator to accurately track close invocations, simulate kernel latch blocks,
     * and verify physical cleanup that ignores interrupt signals.
     */
    static class TrackedCloseFileChannel extends FileChannel {
        private final FileChannel delegate;
        private final AtomicInteger closeCount = new AtomicInteger(0);
        final CountDownLatch closeStartedLatch = new CountDownLatch(1);
        final CountDownLatch releaseCloseLatch = new CountDownLatch(1);
        private final boolean blockOnClose;
        private final boolean ignoreInterruptOnClose;
        final AtomicBoolean wasInterruptedOnClose = new AtomicBoolean(false);

        TrackedCloseFileChannel(FileChannel delegate, boolean blockOnClose, boolean ignoreInterruptOnClose) {
            this.delegate = delegate;
            this.blockOnClose = blockOnClose;
            this.ignoreInterruptOnClose = ignoreInterruptOnClose;
        }

        TrackedCloseFileChannel(FileChannel delegate, boolean blockOnClose) {
            this(delegate, blockOnClose, false);
        }

        TrackedCloseFileChannel(FileChannel delegate) {
            this(delegate, false, false);
        }

        public int getCloseCount() {
            return closeCount.get();
        }

        @Override
        protected void implCloseChannel() throws IOException {
            closeCount.incrementAndGet();
            closeStartedLatch.countDown();

            if (blockOnClose) {
                while (true) {
                    try {
                        if (releaseCloseLatch.await(20, TimeUnit.MILLISECONDS)) {
                            break;
                        }
                    } catch (InterruptedException e) {
                        wasInterruptedOnClose.set(true);
                        if (!ignoreInterruptOnClose) {
                            Thread.currentThread().interrupt();
                            break;
                        }
                        // If ignoreInterruptOnClose is true, keep waiting until releaseCloseLatch!
                    }
                }
            }

            if (delegate != null && delegate.isOpen()) {
                try {
                    delegate.close();
                } catch (IOException ignored) {}
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
        public long transferTo(long position, long count, WritableByteChannel target) throws IOException {
            return delegate != null ? delegate.transferTo(position, count, target) : 0;
        }

        @Override
        public long transferFrom(ReadableByteChannel src, long position, long count) throws IOException {
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
        public MappedByteBuffer map(MapMode mode, long position, long size) throws IOException {
            return delegate != null ? delegate.map(mode, position, size) : null;
        }

        @Override
        public FileLock lock(long position, long size, boolean shared) throws IOException {
            return delegate != null ? delegate.lock(position, size, shared) : null;
        }

        @Override
        public FileLock tryLock(long position, long size, boolean shared) throws IOException {
            return delegate != null ? delegate.tryLock(position, size, shared) : null;
        }
    }

    // =========================================================================================
    // Test 1: Saturated cleanup admission without active read
    // =========================================================================================

    @Test
    @DisplayName("Test 1: Saturated cleanup admission without active read - caller exits promptly and resources are safely admitted")
    void testSaturatedCleanupAdmissionWithoutActiveRead() throws Exception {
        final int MAX_WORKERS = 10;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(50, 10000);
        DriveIoExecutor io = new DriveIoExecutor(100, 100, MAX_WORKERS, breaker);

        CountDownLatch workerReleaseLatch = new CountDownLatch(1);
        CountDownLatch workersStartedLatch = new CountDownLatch(MAX_WORKERS);
        ExecutorService callerPool = Executors.newFixedThreadPool(MAX_WORKERS + 2);
        List<Future<?>> workerFutures = new ArrayList<>();

        Path file11 = tempDir.resolve("channel11_test.bin");
        Files.write(file11, "CHANNEL_11_TEST_BYTES".getBytes(StandardCharsets.UTF_8));
        FileChannel rawChannel11 = FileChannel.open(file11, StandardOpenOption.READ);
        TrackedCloseFileChannel channel11Delegate = new TrackedCloseFileChannel(rawChannel11, true, false);
        DriveSeekableByteChannel channel11 = new DriveSeekableByteChannel(channel11Delegate, io);

        try {
            // 1. Saturate all 10 worker slots with active tasks
            for (int i = 0; i < MAX_WORKERS; i++) {
                Future<?> f = callerPool.submit(() -> {
                    try {
                        io.executeRead(() -> {
                            workersStartedLatch.countDown();
                            while (true) {
                                try {
                                    if (workerReleaseLatch.await(20, TimeUnit.MILLISECONDS)) {
                                        break;
                                    }
                                } catch (InterruptedException ignored) {}
                            }
                            return -1;
                        });
                    } catch (Exception ignored) {}
                });
                workerFutures.add(f);
            }

            assertTrue(workersStartedLatch.await(3, TimeUnit.SECONDS),
                    "All 10 worker tasks must have started");
            assertEquals(MAX_WORKERS, io.getActualOutstandingWorkers(),
                    "All 10 workers must be occupied");

            // 2. channel11 has no active read running (activeWorkerReads is 0)
            assertTrue(channel11.isOpen(), "Channel 11 must be open initially");
            assertFalse(channel11.isClosed(), "Channel 11 must not be closed initially");

            // 3. Caller calls channel11.close() while worker pool is completely saturated
            long callerStart = System.currentTimeMillis();
            Future<?> closeFuture = callerPool.submit(() -> {
                try {
                    channel11.close();
                } catch (IOException e) {
                    throw new RuntimeException(e);
                }
            });

            // Caller MUST exit immediately without being synchronously blocked by delegate's close
            assertDoesNotThrow(() -> closeFuture.get(400, TimeUnit.MILLISECONDS),
                    "Caller must exit channel.close() promptly (<400ms) without blocking synchronously");
            long closeDuration = System.currentTimeMillis() - callerStart;
            assertTrue(closeDuration < 400,
                    "Caller close must finish within 400ms, actual: " + closeDuration + "ms");

            // Channel state must reflect closed
            assertFalse(channel11.isOpen(), "Channel must report isOpen() == false");
            assertTrue(channel11.isClosed(), "Channel must report isClosed() == true");

            // Outstanding workers must not spawn unbounded free threads
            assertTrue(io.getActualOutstandingWorkers() <= MAX_WORKERS + 1,
                    "Worker count must remain bounded without spawning unbounded free threads");

            // 4. Release all saturated workers and channel 11 close latch
            workerReleaseLatch.countDown();
            channel11Delegate.releaseCloseLatch.countDown();

            // 5. Verify safe cleanup completion and outstanding workers returning to 0
            boolean returnedToZero = waitForWorkerCount(io, 0, 5000);
            assertTrue(returnedToZero,
                    "actualOutstandingWorkers must return to 0 after worker release and safe cleanup");
            assertEquals(0, io.getActualOutstandingWorkers());

            // Channel 11 delegate must be physically closed
            assertTrue(channel11Delegate.getCloseCount() >= 1,
                    "Channel 11 delegate close must have been invoked safely");
            assertFalse(rawChannel11.isOpen(), "Underlying file channel must be closed");

        } finally {
            workerReleaseLatch.countDown();
            channel11Delegate.releaseCloseLatch.countDown();
            callerPool.shutdownNow();
            io.shutdown();
        }
    }

    // =========================================================================================
    // Test 2: Late open / completion / interruption races
    // =========================================================================================

    @Test
    @DisplayName("Test 2a: Late open caller timeout race - exactly-once close and accurate worker accounting")
    void testLateOpenCallerTimeoutRace_ExactlyOnceCloseAndWorkerAccounting() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(20, 10000);
        DriveIoExecutor io = new DriveIoExecutor(40, 40, 5, breaker);

        CountDownLatch openReleaseLatch = new CountDownLatch(1);
        CountDownLatch openStartedLatch = new CountDownLatch(1);
        AtomicReference<TrackedCloseFileChannel> channelRef = new AtomicReference<>();
        Path testFile = tempDir.resolve("late_open_timeout_test.bin");
        Files.write(testFile, "LATE_OPEN_TIMEOUT_DATA".getBytes(StandardCharsets.UTF_8));

        try {
            // Caller initiates open with 40ms timeout
            long startTime = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () -> {
                io.executeOpen(() -> {
                    openStartedLatch.countDown();
                    while (true) {
                        try {
                            if (openReleaseLatch.await(10, TimeUnit.MILLISECONDS)) {
                                break;
                            }
                        } catch (InterruptedException ignored) {}
                    }
                    FileChannel raw = FileChannel.open(testFile, StandardOpenOption.READ);
                    TrackedCloseFileChannel tc = new TrackedCloseFileChannel(raw, true);
                    channelRef.set(tc);
                    return tc;
                }, 40, "late-open-timeout-race");
            });

            long elapsed = System.currentTimeMillis() - startTime;
            assertTrue(elapsed >= 40, "Caller must wait at least timeoutMs (40ms)");
            assertNotNull(ex.getMessage(), "Exception message must be present");

            // Task started and is waiting in openReleaseLatch
            assertTrue(openStartedLatch.await(2, TimeUnit.SECONDS), "Worker task must have started");
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "Outstanding worker count must be 1 while worker is running");

            // Release worker open latch so worker completes opening the channel
            openReleaseLatch.countDown();

            // Wait until worker detects timeout and begins closing the channel
            TrackedCloseFileChannel createdChannel = null;
            long waitStart = System.currentTimeMillis();
            while (createdChannel == null && (System.currentTimeMillis() - waitStart) < 3000) {
                createdChannel = channelRef.get();
                if (createdChannel == null) {
                    Thread.sleep(10);
                }
            }
            assertNotNull(createdChannel, "Worker must have opened the channel");
            assertTrue(createdChannel.closeStartedLatch.await(3, TimeUnit.SECONDS),
                    "Worker must have initiated channel close due to timeout");

            // While physical close is blocked on releaseCloseLatch, worker occupancy MUST remain 1!
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must remain 1 while physical close is running");

            // Release physical close latch
            createdChannel.releaseCloseLatch.countDown();

            // Worker accounting must now return to 0
            boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
            assertTrue(returnedToZero, "Worker count must return to 0 after physical close completes");
            assertEquals(0, io.getActualOutstandingWorkers());

            // Exactly-once close verification:
            // Must be closed exactly 1 time! Not 0 (fd leak), not 2 (race double-close).
            assertEquals(1, createdChannel.getCloseCount(),
                    "Resource must be closed EXACTLY once on late-open timeout");
            assertFalse(createdChannel.isOpen(), "Channel must be closed");

        } finally {
            openReleaseLatch.countDown();
            TrackedCloseFileChannel tc = channelRef.get();
            if (tc != null) {
                tc.releaseCloseLatch.countDown();
            }
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 2b: Late open caller interruption race - exactly-once close and accurate worker accounting")
    void testLateOpenCallerInterruptionRace_ExactlyOnceCloseAndWorkerAccounting() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(20, 10000);
        DriveIoExecutor io = new DriveIoExecutor(1000, 1000, 5, breaker);

        CountDownLatch openReleaseLatch = new CountDownLatch(1);
        CountDownLatch openStartedLatch = new CountDownLatch(1);
        AtomicReference<TrackedCloseFileChannel> channelRef = new AtomicReference<>();
        AtomicReference<Throwable> callerErrorRef = new AtomicReference<>();
        Path testFile = tempDir.resolve("late_open_interrupt_test.bin");
        Files.write(testFile, "LATE_OPEN_INTERRUPT_DATA".getBytes(StandardCharsets.UTF_8));

        ExecutorService callerPool = Executors.newSingleThreadExecutor();
        CountDownLatch callerWaitingLatch = new CountDownLatch(1);
        AtomicReference<Thread> callerThreadRef = new AtomicReference<>();

        try {
            Future<?> callerFuture = callerPool.submit(() -> {
                callerThreadRef.set(Thread.currentThread());
                callerWaitingLatch.countDown();
                try {
                    io.executeOpen(() -> {
                        openStartedLatch.countDown();
                        while (true) {
                            try {
                                if (openReleaseLatch.await(10, TimeUnit.MILLISECONDS)) {
                                    break;
                                }
                            } catch (InterruptedException ignored) {}
                        }
                        FileChannel raw = FileChannel.open(testFile, StandardOpenOption.READ);
                        TrackedCloseFileChannel tc = new TrackedCloseFileChannel(raw, true);
                        channelRef.set(tc);
                        return tc;
                    }, 5000, "late-open-interrupt-race");
                } catch (Throwable t) {
                    callerErrorRef.set(t);
                }
            });

            assertTrue(callerWaitingLatch.await(2, TimeUnit.SECONDS), "Caller must start waiting");
            assertTrue(openStartedLatch.await(2, TimeUnit.SECONDS), "Worker must start task");
            assertEquals(1, io.getActualOutstandingWorkers(), "Worker permit occupied");

            // Interrupt caller thread while awaiting future.get
            Thread callerThread = callerThreadRef.get();
            assertNotNull(callerThread, "Caller thread must be present");
            callerThread.interrupt();

            // Caller thread exits with MediaUnavailableException due to interruption
            assertDoesNotThrow(() -> callerFuture.get(1, TimeUnit.SECONDS),
                    "Caller must exit promptly after interruption");
            Throwable error = callerErrorRef.get();
            assertNotNull(error, "Caller must catch interruption error");
            assertTrue(error instanceof MediaUnavailableException,
                    "Expected MediaUnavailableException on interrupt, got: " + error.getClass().getName());

            // Worker is still in openReleaseLatch
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "Worker permit must remain accounted for");

            // Release worker open latch
            openReleaseLatch.countDown();

            // Wait for worker to open channel and attempt close
            TrackedCloseFileChannel createdChannel = null;
            long waitStart = System.currentTimeMillis();
            while (createdChannel == null && (System.currentTimeMillis() - waitStart) < 3000) {
                createdChannel = channelRef.get();
                if (createdChannel == null) {
                    Thread.sleep(10);
                }
            }
            assertNotNull(createdChannel, "Worker must open channel");
            assertTrue(createdChannel.closeStartedLatch.await(3, TimeUnit.SECONDS),
                    "Channel close must be triggered on interruption race");

            // While physical close is blocked on releaseCloseLatch, worker permit remains occupied
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must remain 1 while physical close is running");

            // Release close latch
            createdChannel.releaseCloseLatch.countDown();

            // Worker returns to 0
            boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
            assertTrue(returnedToZero, "Worker count must return to 0 after interrupt disposal");
            assertEquals(0, io.getActualOutstandingWorkers());

            // Exactly-once close:
            assertEquals(1, createdChannel.getCloseCount(),
                    "Resource must be closed EXACTLY once on interruption race");
            assertFalse(createdChannel.isOpen(), "Channel must be closed");

        } finally {
            openReleaseLatch.countDown();
            TrackedCloseFileChannel tc = channelRef.get();
            if (tc != null) {
                tc.releaseCloseLatch.countDown();
            }
            callerPool.shutdownNow();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 2c: High-concurrency timeout/completion race stress - exactly-once close across all iterations")
    void testLateOpenConcurrentRaceStress_ExactlyOnceCloseGuaranteed() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(100, 10000);
        DriveIoExecutor io = new DriveIoExecutor(30, 30, 10, breaker);

        final int ITERATIONS = 30;
        try {
            for (int i = 0; i < ITERATIONS; i++) {
                Path file = tempDir.resolve("race_stress_" + i + ".bin");
                Files.write(file, ("RACE_STRESS_PAYLOAD_" + i).getBytes(StandardCharsets.UTF_8));

                // Vary delay between 0ms and 30ms around 20ms timeout to maximize race conditions
                final int delayMs = (i % 5) * 6;
                AtomicReference<TrackedCloseFileChannel> channelRef = new AtomicReference<>();

                TrackedCloseFileChannel acquiredChannel = null;
                try {
                    acquiredChannel = io.executeOpen(() -> {
                        if (delayMs > 0) {
                            try {
                                Thread.sleep(delayMs);
                            } catch (InterruptedException ignored) {}
                        }
                        FileChannel raw = FileChannel.open(file, StandardOpenOption.READ);
                        TrackedCloseFileChannel tc = new TrackedCloseFileChannel(raw, false);
                        channelRef.set(tc);
                        return tc;
                    }, 20, "stress-race-" + i);
                } catch (MediaUnavailableException ignored) {
                    // Timeout occurred
                }

                // Wait for background worker to complete resolution
                boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
                assertTrue(returnedToZero, "Worker count must return to 0 on iteration " + i);
                assertEquals(0, io.getActualOutstandingWorkers());

                TrackedCloseFileChannel createdChannel = channelRef.get();
                if (acquiredChannel != null) {
                    // Caller won the race: caller received ownership
                    assertSame(acquiredChannel, createdChannel, "Returned channel must match created");
                    assertEquals(0, createdChannel.getCloseCount(),
                            "Worker must NOT close caller-owned channel during race on iteration " + i);
                    assertTrue(createdChannel.isOpen(), "Channel must remain open in caller ownership");

                    // Caller explicitly closes channel
                    acquiredChannel.close();
                    assertEquals(1, createdChannel.getCloseCount(),
                            "Channel must be closed exactly once by caller on iteration " + i);
                    assertFalse(createdChannel.isOpen(), "Channel must be closed");
                } else {
                    // Timeout won the race: worker closed it
                    assertNotNull(createdChannel, "Worker must have created channel on iteration " + i);
                    assertEquals(1, createdChannel.getCloseCount(),
                            "Resource must be closed EXACTLY once by worker on timeout on iteration " + i);
                    assertFalse(createdChannel.isOpen(), "Late channel must be closed by worker");
                }
            }
        } finally {
            io.shutdown();
        }
    }

    // =========================================================================================
    // Test 3: Timely open stays open and usable
    // =========================================================================================

    @Test
    @DisplayName("Test 3: Timely open stays open and usable - channel returned intact, closed=false, normal read/seek/size")
    void testTimelyOpenStaysOpenAndUsable() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(10, 10000);
        DriveIoExecutor io = new DriveIoExecutor(1000, 1000, 5, breaker);

        byte[] payload = "TIMELY_OPEN_VERIFICATION_PAYLOAD_ABC_123456789".getBytes(StandardCharsets.UTF_8);
        Path sampleFile = tempDir.resolve("timely_open_sample.bin");
        Files.write(sampleFile, payload);

        try {
            // 1. Direct executeOpen verification
            FileChannel rawChannel = io.executeOpen(
                    () -> FileChannel.open(sampleFile, StandardOpenOption.READ),
                    1000, "timely-open");

            assertNotNull(rawChannel, "Channel must not be null");
            assertTrue(rawChannel.isOpen(), "Channel must be open upon return");

            // Worker count must return to 0 promptly (ownership transferred to caller)
            boolean returnedToZero = waitForWorkerCount(io, 0, 2000);
            assertTrue(returnedToZero, "Worker count must return to 0 after ownership transfer");
            assertEquals(0, io.getActualOutstandingWorkers());

            // 2. Wrap in DriveSeekableByteChannel and verify operational integrity
            DriveSeekableByteChannel seekable = new DriveSeekableByteChannel(rawChannel, io);
            try {
                assertTrue(seekable.isOpen(), "Seekable channel must be open");
                assertFalse(seekable.isClosed(), "Seekable channel closed flag must be false");

                // Read full payload
                ByteBuffer dst = ByteBuffer.allocate(payload.length);
                int bytesRead = seekable.read(dst);
                assertEquals(payload.length, bytesRead, "Must read exact number of bytes");
                assertArrayEquals(payload, dst.array(), "Read data must match written payload");

                // Position operations
                assertEquals(payload.length, seekable.position(), "Position must match bytes read");
                seekable.position(5);
                assertEquals(5, seekable.position(), "Position must be updated to 5");

                // Read from position 5
                ByteBuffer partialDst = ByteBuffer.allocate(4);
                int partialRead = seekable.read(partialDst);
                assertEquals(4, partialRead, "Must read 4 bytes from position 5");
                byte[] expectedSlice = new byte[4];
                System.arraycopy(payload, 5, expectedSlice, 0, 4);
                assertArrayEquals(expectedSlice, partialDst.array(), "Partial read must match slice");

                // Size verification
                assertEquals(payload.length, seekable.size(), "Size must match file length");

            } finally {
                // Channel closes only when caller explicitly closes it
                seekable.close();
                assertFalse(seekable.isOpen(), "Channel must report isOpen() == false after caller close");
                assertTrue(seekable.isClosed(), "Channel must report isClosed() == true after caller close");
            }

            // Subsequent operations must throw ClosedChannelException
            assertThrows(ClosedChannelException.class, () -> seekable.read(ByteBuffer.allocate(1)),
                    "read() on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> seekable.position(),
                    "position() on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> seekable.position(0),
                    "position(0) on closed channel must throw ClosedChannelException");
            assertThrows(ClosedChannelException.class, () -> seekable.size(),
                    "size() on closed channel must throw ClosedChannelException");

        } finally {
            io.shutdown();
        }
    }

    // =========================================================================================
    // Test 4: Physical cleanup that ignores interrupts
    // =========================================================================================

    @Test
    @DisplayName("Test 4a: Asynchronous cleanup that ignores interrupts - retains worker capacity until physical finish")
    void testAsyncCleanupIgnoresInterrupt_RetainsCapacityUntilPhysicalFinish() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(10, 10000);
        DriveIoExecutor io = new DriveIoExecutor(100, 100, 3, breaker);

        Path testFile = tempDir.resolve("async_cleanup_interrupt_ignore.bin");
        Files.write(testFile, "CLEANUP_DATA".getBytes(StandardCharsets.UTF_8));
        FileChannel rawChannel = FileChannel.open(testFile, StandardOpenOption.READ);

        // Channel that BLOCKS on close and IGNORES interrupt signals
        TrackedCloseFileChannel channel = new TrackedCloseFileChannel(rawChannel, true, true);

        try {
            // Caller executes async cleanup
            long submitStart = System.currentTimeMillis();
            io.executeCleanupAsync(channel, "interrupt-ignoring-cleanup");
            long submitDuration = System.currentTimeMillis() - submitStart;

            // Caller thread MUST return immediately (< 100ms)
            assertTrue(submitDuration < 100,
                    "Caller must return immediately from executeCleanupAsync, actual: " + submitDuration + "ms");

            // Wait for worker to enter implCloseChannel()
            assertTrue(channel.closeStartedLatch.await(3, TimeUnit.SECONDS),
                    "Cleanup task must have started in background worker");

            // Outstanding worker count MUST be exactly 1 while physical close is blocked
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "Outstanding workers must be 1 while physical cleanup is running");

            // Find worker thread and interrupt it
            ThreadGroup rootGroup = Thread.currentThread().getThreadGroup();
            while (rootGroup.getParent() != null) {
                rootGroup = rootGroup.getParent();
            }
            Thread[] threads = new Thread[rootGroup.activeCount() + 10];
            int count = rootGroup.enumerate(threads);
            boolean interruptedAny = false;
            for (int i = 0; i < count; i++) {
                if (threads[i] != null && threads[i].getName().startsWith("drive-io-worker-")) {
                    threads[i].interrupt();
                    interruptedAny = true;
                }
            }
            assertTrue(interruptedAny, "Must find and interrupt at least one drive-io-worker thread");

            // Give a moment for interrupt to be processed
            Thread.sleep(50);

            // Channel must record having received the interrupt
            assertTrue(channel.wasInterruptedOnClose.get(),
                    "Channel must have intercepted and handled InterruptedException during close");

            // Crucial verification: worker permit MUST NOT be leaked or decremented early!
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must STILL be 1 while physical close is running, despite interrupt!");

            // Release physical close latch
            channel.releaseCloseLatch.countDown();

            // Wait for worker to finish physical cleanup
            boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
            assertTrue(returnedToZero,
                    "actualOutstandingWorkers must return to 0 after physical close unblocks");
            assertEquals(0, io.getActualOutstandingWorkers());

            // Resource closed exactly once
            assertEquals(1, channel.getCloseCount(), "Resource must be closed exactly once");
            assertFalse(rawChannel.isOpen(), "Underlying channel must be closed");

            // Capacity check: pool is healthy, subsequent task executes normally
            String healthyResult = io.executeRead(() -> "pool-is-healthy");
            assertEquals("pool-is-healthy", healthyResult, "Pool must remain fully functional");

        } finally {
            channel.releaseCloseLatch.countDown();
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 4b: Timeout in executeOpen when close ignores interrupts - no capacity leak")
    void testTimeoutInOpen_WhenCloseIgnoresInterrupt_DoesNotLeakWorkerPermit() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(10, 10000);
        DriveIoExecutor io = new DriveIoExecutor(40, 40, 3, breaker);

        Path testFile = tempDir.resolve("timeout_open_interrupt_ignore.bin");
        Files.write(testFile, "TIMEOUT_OPEN_INTERRUPT_IGNORE_DATA".getBytes(StandardCharsets.UTF_8));

        CountDownLatch openReleaseLatch = new CountDownLatch(1);
        CountDownLatch openStartedLatch = new CountDownLatch(1);
        AtomicReference<TrackedCloseFileChannel> channelRef = new AtomicReference<>();

        try {
            // Caller times out at 40ms
            long start = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () -> {
                io.executeOpen(() -> {
                    openStartedLatch.countDown();
                    while (true) {
                        try {
                            if (openReleaseLatch.await(10, TimeUnit.MILLISECONDS)) {
                                break;
                            }
                        } catch (InterruptedException ignored) {}
                    }
                    FileChannel raw = FileChannel.open(testFile, StandardOpenOption.READ);
                    // blockOnClose=true, ignoreInterruptOnClose=true
                    TrackedCloseFileChannel tc = new TrackedCloseFileChannel(raw, true, true);
                    channelRef.set(tc);
                    return tc;
                }, 40, "timeout-interrupt-ignore");
            });

            long duration = System.currentTimeMillis() - start;
            assertTrue(duration >= 40, "Caller must wait at least 40ms timeout");
            assertNotNull(ex.getMessage(), "Exception must have message");

            // Worker started
            assertTrue(openStartedLatch.await(2, TimeUnit.SECONDS), "Worker must have started");
            assertEquals(1, io.getActualOutstandingWorkers(), "Worker permit occupied");

            // Release open latch so worker creates channel and detects timeout
            openReleaseLatch.countDown();

            // Wait for worker to open channel and start close
            TrackedCloseFileChannel tc = null;
            long waitStart = System.currentTimeMillis();
            while (tc == null && (System.currentTimeMillis() - waitStart) < 3000) {
                tc = channelRef.get();
                if (tc == null) {
                    Thread.sleep(10);
                }
            }
            assertNotNull(tc, "Channel must have been opened");
            assertTrue(tc.closeStartedLatch.await(3, TimeUnit.SECONDS),
                    "Worker must have initiated channel close");

            // Future cancellation may interrupt worker, but close ignores interrupt
            // Permit MUST remain occupied while physical close is running
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "actualOutstandingWorkers must remain 1 while physical close is running");

            // Release close latch
            tc.releaseCloseLatch.countDown();

            // Worker returns to 0
            boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
            assertTrue(returnedToZero, "Worker count must return to 0 after physical close completes");
            assertEquals(0, io.getActualOutstandingWorkers());

            // Resource was closed exactly once
            assertEquals(1, tc.getCloseCount(), "Resource must be closed exactly once");
            assertFalse(tc.isOpen(), "Channel must be closed");

            // Confirm no capacity leak
            String result = io.executeRead(() -> "capacity-restored");
            assertEquals("capacity-restored", result);

        } finally {
            openReleaseLatch.countDown();
            TrackedCloseFileChannel tc = channelRef.get();
            if (tc != null) {
                tc.releaseCloseLatch.countDown();
            }
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 4c: Repeated interrupt-ignoring cleanup cycles - zero capacity leak across consecutive cycles")
    void testRepeatedInterruptIgnoringCleanupCycles_ZeroCapacityLeak() throws Exception {
        final int CYCLES = 5;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(CYCLES + 5, 10000);
        DriveIoExecutor io = new DriveIoExecutor(50, 50, 3, breaker);

        List<TrackedCloseFileChannel> channels = new ArrayList<>();
        List<CountDownLatch> releaseLatches = new ArrayList<>();

        try {
            for (int i = 0; i < CYCLES; i++) {
                Path cycleFile = tempDir.resolve("cycle_interrupt_" + i + ".bin");
                Files.write(cycleFile, ("CYCLE_INTERRUPT_DATA_" + i).getBytes(StandardCharsets.UTF_8));
                FileChannel raw = FileChannel.open(cycleFile, StandardOpenOption.READ);
                TrackedCloseFileChannel tc = new TrackedCloseFileChannel(raw, true, true);
                channels.add(tc);
                releaseLatches.add(tc.releaseCloseLatch);

                io.executeCleanupAsync(tc, "cycle-cleanup-" + i);

                // Wait for close to start
                assertTrue(tc.closeStartedLatch.await(2, TimeUnit.SECONDS),
                        "Cycle " + i + " cleanup must start");
                assertEquals(1, io.getActualOutstandingWorkers(),
                        "Permit must be occupied during physical close of cycle " + i);

                // Release close latch
                tc.releaseCloseLatch.countDown();

                // Wait for worker to finish
                boolean zero = waitForWorkerCount(io, 0, 3000);
                assertTrue(zero, "Worker count must return to 0 after cycle " + i);
                assertEquals(0, io.getActualOutstandingWorkers());
                assertEquals(1, tc.getCloseCount(), "Channel " + i + " must be closed exactly once");
            }

            // All channels closed
            for (TrackedCloseFileChannel tc : channels) {
                assertFalse(tc.isOpen(), "All cycle channels must be closed");
            }

            // Verify healthy pool
            String ok = io.executeRead(() -> "all-cycles-clean");
            assertEquals("all-cycles-clean", ok);

        } finally {
            for (CountDownLatch latch : releaseLatches) {
                latch.countDown();
            }
            io.shutdown();
        }
    }
}
