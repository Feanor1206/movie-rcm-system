package com.dippie.moviercm;

import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.service.DriveMediaStorageAdapter;
import com.dippie.moviercm.service.storage.DriveCircuitBreaker;
import com.dippie.moviercm.service.storage.DriveIoExecutor;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.MappedByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.channels.ReadableByteChannel;
import java.nio.channels.SeekableByteChannel;
import java.nio.channels.WritableByteChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("DriveLateOpenLifecycleTest - Late Open Handshake, Exactly-Once Closure & Worker Accounting")
public class DriveLateOpenLifecycleTest {

    @TempDir
    Path tempDir;

    private Path sampleFile;
    private byte[] sampleData;

    @BeforeEach
    void setUp() throws IOException {
        sampleFile = tempDir.resolve("sample_video.mp4");
        sampleData = "LATE_OPEN_LIFECYCLE_TEST_PAYLOAD_0123456789".getBytes(StandardCharsets.UTF_8);
        Files.write(sampleFile, sampleData);
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

    /**
     * FileChannel decorator to accurately track close invocations for handshake race testing.
     */
    static class TrackedChannel extends FileChannel {
        private final FileChannel delegate;
        private final AtomicInteger closeCount = new AtomicInteger(0);

        TrackedChannel(FileChannel delegate) {
            this.delegate = delegate;
        }

        public int getCloseCount() {
            return closeCount.get();
        }

        @Override
        protected void implCloseChannel() throws IOException {
            closeCount.incrementAndGet();
            delegate.close();
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
    @DisplayName("Reviewer Repro Verification: DRIVE_F01_late_open repro scenario")
    void testReviewerReproScenario() throws Exception {
        var io = new DriveIoExecutor(40, 40, 1, new DriveCircuitBreaker(5, 100));
        var release = new CountDownLatch(1);
        var opened = new AtomicReference<FileChannel>();
        Path file = Files.createTempFile("codex-drive-late-", ".bin");
        try {
            try {
                io.executeOpen(() -> {
                    while (true) {
                        try {
                            release.await();
                            break;
                        } catch (InterruptedException ignored) {}
                    }
                    FileChannel ch = FileChannel.open(file, StandardOpenOption.READ);
                    opened.set(ch);
                    return ch;
                }, 40, "repro-open");
            } catch (Exception e) {
                // Expected timeout exception on caller side
            }
            release.countDown();
            long until = System.nanoTime() + TimeUnit.SECONDS.toNanos(2);
            while ((opened.get() == null || io.getActualOutstandingWorkers() != 0) && System.nanoTime() < until) {
                Thread.sleep(5);
            }
            assertNotNull(opened.get(), "Late open was not exercised");
            assertFalse(opened.get().isOpen(), "Late open channel must NOT stay open");
            assertEquals(0, io.getActualOutstandingWorkers(), "Outstanding workers must return to 0");
        } finally {
            release.countDown();
            if (opened.get() != null && opened.get().isOpen()) {
                opened.get().close();
            }
            io.shutdown();
            Files.deleteIfExists(file);
        }
    }

    @Test
    @DisplayName("Test 1: Late Open Disposal - Worker detects caller timeout, automatically closes channel, releases worker permit, and prevents fd leaks")
    void testLateOpenDisposalWorkerClosesResource() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(10, 10000);
        DriveIoExecutor io = new DriveIoExecutor(50, 50, 5, breaker);

        CountDownLatch taskStarted = new CountDownLatch(1);
        CountDownLatch releaseWorker = new CountDownLatch(1);
        AtomicReference<FileChannel> openedChannelRef = new AtomicReference<>();
        Path testFile = tempDir.resolve("late_disposal_test.bin");
        Files.write(testFile, "SAMPLE_BYTES_FOR_DISPOSAL".getBytes(StandardCharsets.UTF_8));

        try {
            // Caller initiates open with short timeout (50ms)
            long startTime = System.currentTimeMillis();
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () -> {
                io.executeOpen(() -> {
                    taskStarted.countDown();
                    // Worker is delayed until releaseWorker latch is opened
                    while (true) {
                        try {
                            if (releaseWorker.await(10, TimeUnit.MILLISECONDS)) {
                                break;
                            }
                        } catch (InterruptedException ignored) {}
                    }
                    FileChannel ch = FileChannel.open(testFile, StandardOpenOption.READ);
                    openedChannelRef.set(ch);
                    return ch;
                }, 50, "late-open-disposal");
            });

            long elapsed = System.currentTimeMillis() - startTime;
            assertTrue(elapsed >= 50, "Caller must wait at least timeoutMs (50ms)");
            assertNotNull(ex.getMessage(), "Exception must have an informative message");

            // Verify task actually started and entered worker thread execution
            assertTrue(taskStarted.await(2, TimeUnit.SECONDS), "Worker task should have started");

            // Caller has timed out, but worker is still stuck in latch:
            assertEquals(1, io.getActualOutstandingWorkers(),
                    "Worker permit must remain accounted for while background worker is still running");
            assertNull(openedChannelRef.get(), "Channel should not yet be opened while worker is stalled");

            // Open latch to allow worker to complete after caller has already timed out
            releaseWorker.countDown();

            // Wait for worker to complete open, detect caller abandonment, and close channel
            boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
            assertTrue(returnedToZero, "Worker count must return to 0 after worker completes and cleans up");
            assertEquals(0, io.getActualOutstandingWorkers());

            // Requirement a: Worker thread detects caller timed out and automatically closes channel
            FileChannel lateChannel = openedChannelRef.get();
            assertNotNull(lateChannel, "Worker must have eventually executed FileChannel.open");
            assertFalse(lateChannel.isOpen(), "Late-opened channel must be automatically closed by worker");

            // Requirement b: ioExecutor.getActualOutstandingWorkers() returned to 0 (verified above)

            // Requirement c: No file descriptor leak
            // On Windows NT filesystem, deleting an open file fails with sharing violation if fd is leaked.
            // When properly closed by worker, Files.delete succeeds cleanly.
            assertDoesNotThrow(() -> Files.delete(testFile),
                    "Temporary file must be deletable immediately after worker closes it, proving no leaked fd");
            assertFalse(Files.exists(testFile), "File must be deleted cleanly");

        } finally {
            releaseWorker.countDown();
            FileChannel ch = openedChannelRef.get();
            if (ch != null && ch.isOpen()) {
                try {
                    ch.close();
                } catch (IOException ignored) {}
            }
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 2: Timely Open Stays Usable - Channel received before timeout remains open and readable")
    void testTimelyOpenStaysUsable() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(10, 10000);
        DriveIoExecutor io = new DriveIoExecutor(1000, 1000, 5, breaker);

        try {
            // Direct executeOpen verification
            FileChannel channel = io.executeOpen(
                    () -> FileChannel.open(sampleFile, StandardOpenOption.READ),
                    1000, "timely-open");
            try {
                // Must be open
                assertTrue(channel.isOpen(), "Timely opened channel must be open");

                // Worker count must return to 0 (worker finished transferring ownership)
                boolean returnedToZero = waitForWorkerCount(io, 0, 2000);
                assertTrue(returnedToZero, "Worker count must return to 0 after ownership transfer");

                // Channel must remain open in caller's ownership
                assertTrue(channel.isOpen(), "Channel must remain open in caller's ownership");

                // Data can be read normally
                ByteBuffer dst = ByteBuffer.allocate(sampleData.length);
                int bytesRead = channel.read(dst);
                assertEquals(sampleData.length, bytesRead, "Must read exact number of bytes");
                assertArrayEquals(sampleData, dst.array(), "Read data must match written sample data");
            } finally {
                // Channel closes only when caller actively closes it
                channel.close();
                assertFalse(channel.isOpen(), "Channel must be closed after caller explicitly closes it");
            }

            // Also verify via DriveMediaStorageAdapter
            DriveMediaStorageAdapter adapter = new DriveMediaStorageAdapter(tempDir.toString(), io);
            SeekableByteChannel adapterChannel = adapter.openChannel("sample_video.mp4");
            try {
                assertTrue(adapterChannel.isOpen(), "Adapter channel must be open");
                ByteBuffer dst = ByteBuffer.allocate(sampleData.length);
                int bytesRead = adapterChannel.read(dst);
                assertEquals(sampleData.length, bytesRead, "Adapter channel must read exact data");
                assertArrayEquals(sampleData, dst.array(), "Adapter channel data must match sample payload");
            } finally {
                adapterChannel.close();
                assertFalse(adapterChannel.isOpen(), "Adapter channel must be closed after close()");
            }
        } finally {
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 3: Timeout / Completion Race - Exactly-once closure guarantee under race conditions")
    void testTimeoutCompletionRaceExactlyOnceClosure() throws Exception {
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(100, 10000);
        DriveIoExecutor io = new DriveIoExecutor(50, 50, 10, breaker);

        try {
            final int ITERATIONS = 20;
            for (int i = 0; i < ITERATIONS; i++) {
                Path file = tempDir.resolve("race_test_" + i + ".bin");
                Files.write(file, ("RACE_DATA_" + i).getBytes(StandardCharsets.UTF_8));
                final int delayMs = (i % 4) * 8; // Varied delay: 0ms, 8ms, 16ms, 24ms against ~20ms timeout
                AtomicReference<TrackedChannel> channelRef = new AtomicReference<>();

                final int iterationIndex = i;
                TrackedChannel channel = null;
                try {
                    channel = io.executeOpen(() -> {
                        if (delayMs > 0) {
                            try {
                                Thread.sleep(delayMs);
                            } catch (InterruptedException ignored) {}
                        }
                        FileChannel raw = FileChannel.open(file, StandardOpenOption.READ);
                        TrackedChannel tc = new TrackedChannel(raw);
                        channelRef.set(tc);
                        return tc;
                    }, 20, "race-test-" + iterationIndex);
                } catch (MediaUnavailableException e) {
                    // Timeout occurred
                }

                // Wait for worker thread to complete lifecycle resolution
                boolean returnedToZero = waitForWorkerCount(io, 0, 3000);
                assertTrue(returnedToZero, "Worker count must return to 0");

                TrackedChannel created = channelRef.get();
                if (channel != null) {
                    // Caller won the race: caller received ownership
                    assertSame(channel, created, "Returned channel must match created channel");
                    assertEquals(0, created.getCloseCount(), "Worker must not close caller-owned channel");
                    assertTrue(created.isOpen(), "Channel must remain open in caller ownership");

                    // Caller explicitly closes channel
                    channel.close();
                    assertEquals(1, created.getCloseCount(), "Channel must be closed exactly once by caller");
                    assertFalse(created.isOpen(), "Channel must be closed after caller closure");
                } else {
                    // Timeout won the race: caller received MediaUnavailableException
                    assertNotNull(created, "Worker must have completed opening the channel");
                    assertEquals(1, created.getCloseCount(), "Worker must have closed channel exactly once on timeout");
                    assertFalse(created.isOpen(), "Late channel must be closed by worker");
                }
            }
        } finally {
            io.shutdown();
        }
    }

    @Test
    @DisplayName("Test 4: Repeated Slow Open Cycles - 10 consecutive timeout cycles leave 0 workers, all channels closed, and no handle choking")
    void testRepeatedSlowOpenCycles() throws Exception {
        final int CYCLES = 10;
        DriveCircuitBreaker breaker = new DriveCircuitBreaker(CYCLES + 5, 10000);
        DriveIoExecutor io = new DriveIoExecutor(30, 30, 5, breaker);

        List<CountDownLatch> releaseLatches = new ArrayList<>();
        List<AtomicReference<FileChannel>> channelRefs = new ArrayList<>();
        List<Path> files = new ArrayList<>();

        try {
            for (int i = 0; i < CYCLES; i++) {
                Path cycleFile = tempDir.resolve("cycle_file_" + i + ".bin");
                Files.write(cycleFile, ("CYCLE_PAYLOAD_" + i).getBytes(StandardCharsets.UTF_8));
                files.add(cycleFile);

                CountDownLatch releaseLatch = new CountDownLatch(1);
                releaseLatches.add(releaseLatch);
                AtomicReference<FileChannel> channelRef = new AtomicReference<>();
                channelRefs.add(channelRef);

                final int currentCycle = i;
                assertThrows(MediaUnavailableException.class, () -> {
                    io.executeOpen(() -> {
                        while (true) {
                            try {
                                if (releaseLatch.await(10, TimeUnit.MILLISECONDS)) {
                                    break;
                                }
                            } catch (InterruptedException ignored) {}
                        }
                        FileChannel ch = FileChannel.open(cycleFile, StandardOpenOption.READ);
                        channelRef.set(ch);
                        return ch;
                    }, 30, "cycle-timeout-" + currentCycle);
                });

                // Release worker immediately after caller timeout
                releaseLatch.countDown();
            }

            // After all 10 cycles, wait for all workers to finish cleanup
            boolean allReturnedToZero = waitForWorkerCount(io, 0, 5000);
            assertTrue(allReturnedToZero, "Worker count must return to 0 after all 10 timeout cycles");
            assertEquals(0, io.getActualOutstandingWorkers());

            // Confirm all 10 channels were opened and subsequently closed by worker
            for (int i = 0; i < CYCLES; i++) {
                FileChannel ch = channelRefs.get(i).get();
                assertNotNull(ch, "Channel " + i + " must have been opened");
                assertFalse(ch.isOpen(), "Channel " + i + " must be closed by worker");
            }

            // Confirm pool worker is NOT choked: subsequent timely operation succeeds immediately
            FileChannel healthyChannel = io.executeOpen(
                    () -> FileChannel.open(sampleFile, StandardOpenOption.READ),
                    1000, "healthy-post-cycle-check");
            try {
                assertTrue(healthyChannel.isOpen(), "Healthy channel must be open");
                assertEquals(sampleData.length, healthyChannel.size(), "Size must match sample data length");
            } finally {
                healthyChannel.close();
            }

            // Confirm no handle choking / no file descriptor leak on all 10 files
            for (Path f : files) {
                assertDoesNotThrow(() -> Files.delete(f),
                        "All cycle files must be deletable without sharing violation, proving no leaked fd");
            }

        } finally {
            for (CountDownLatch latch : releaseLatches) {
                latch.countDown();
            }
            for (AtomicReference<FileChannel> ref : channelRefs) {
                FileChannel ch = ref.get();
                if (ch != null && ch.isOpen()) {
                    try {
                        ch.close();
                    } catch (IOException ignored) {}
                }
            }
            io.shutdown();
        }
    }
}
