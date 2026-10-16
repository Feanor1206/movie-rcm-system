package com.dippie.moviercm;

import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.service.storage.DriveCircuitBreaker;
import com.dippie.moviercm.service.storage.DriveIoExecutor;
import com.dippie.moviercm.service.storage.DriveResourceReservation;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.channels.FileChannel;
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

/**
 * DRIVE-01-F07 / Finding C1 Regression & Repro Test Suite.
 *
 * Verifies that:
 * 1. executeWithTimeout returning an AutoCloseable never silently drops native handles on timeout + close failure,
 *    even when lifecycle capacity is fully saturated (active + pending == capacity).
 * 2. Unreserved failed cleanups retained at saturated capacity are tracked in retainedFailedCleanups,
 *    increment failedCleanupObligations, and dynamically acquire pending permits upon retry once capacity frees up.
 * 3. Handles can be retried and recovered across shutdown without leaking handles or corrupting lifecycle counters.
 * 4. All lifecycle counters remain strictly non-negative (active >= 0, pending >= 0).
 */
@DisplayName("DriveGenericMetadataReproTest - Finding C1 Generic Metadata Cleanup at Saturated Capacity")
public class DriveGenericMetadataReproTest {

    private final List<DriveIoExecutor> managedExecutors = new CopyOnWriteArrayList<>();
    private final List<Path> tempFiles = new CopyOnWriteArrayList<>();

    @BeforeEach
    void setUp() {
        managedExecutors.clear();
        tempFiles.clear();
    }

    @AfterEach
    void tearDown() {
        for (DriveIoExecutor exec : managedExecutors) {
            try {
                if (!exec.isShutdown()) {
                    exec.shutdown();
                }
            } catch (Throwable ignored) {
            }
        }
        for (Path p : tempFiles) {
            try {
                Files.deleteIfExists(p);
            } catch (Throwable ignored) {
            }
        }
    }

    private DriveIoExecutor createExecutor(int maxWorkers, int queueCapacity) {
        DriveIoExecutor exec = new DriveIoExecutor(100, 100, maxWorkers, queueCapacity, new DriveCircuitBreaker(10_000, 10));
        managedExecutors.add(exec);
        return exec;
    }

    @Test
    @DisplayName("C1 Repro: executeWithTimeout retains failed handle at saturated capacity without silent drop")
    void executeWithTimeoutRetainsHandleAtSaturatedCapacity() throws Exception {
        DriveIoExecutor executor = createExecutor(2, 1);
        DriveResourceReservation reservation = executor.acquireReservation();
        assertNotNull(reservation);
        assertEquals(1, executor.getActiveResourceReservations());
        assertEquals(0, executor.getPendingCleanupObligations());

        CountDownLatch entered = new CountDownLatch(1);
        CountDownLatch releaseWorker = new CountDownLatch(1);
        AtomicInteger attempts = new AtomicInteger();
        AtomicReference<Throwable> callerError = new AtomicReference<>();

        Path file = Files.createTempFile("f07-c1-test-", ".bin");
        tempFiles.add(file);
        FileChannel nativeHandle = FileChannel.open(file, StandardOpenOption.READ);

        AutoCloseable resource = () -> {
            if (attempts.incrementAndGet() == 1) {
                throw new IOException("Simulated native close failure on attempt 1");
            }
            nativeHandle.close();
        };

        Thread caller = new Thread(() -> {
            try {
                executor.executeWithTimeout(() -> {
                    entered.countDown();
                    while (releaseWorker.getCount() != 0) {
                        try {
                            releaseWorker.await();
                        } catch (InterruptedException ignored) {
                        }
                    }
                    return resource;
                }, 100, "test-metadata-failure");
            } catch (Throwable t) {
                callerError.set(t);
            }
        });

        caller.start();
        assertTrue(entered.await(3, TimeUnit.SECONDS), "Worker should enter task");
        caller.join(3000);
        assertFalse(caller.isAlive(), "Caller should finish after timeout");
        assertInstanceOf(MediaUnavailableException.class, callerError.get(), "Caller should receive MediaUnavailableException");

        // Release worker so it can attempt close on worker thread
        releaseWorker.countDown();

        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
        while (executor.getActualOutstandingWorkers() != 0 && System.nanoTime() < deadline) {
            Thread.sleep(10);
        }
        assertEquals(0, executor.getActualOutstandingWorkers());

        // Assert no handle drop occurred:
        assertEquals(1, attempts.get(), "Should have attempted close once");
        assertTrue(nativeHandle.isOpen(), "Native handle must still be open after attempt 1 failure");
        assertEquals(1, executor.getRetainedFailedResources().size(), "Failed cleanup must be retained in executor");
        assertTrue(executor.hasFailedCleanup(resource), "Resource must be tracked as failed cleanup");
        assertEquals(1, executor.getFailedCleanupObligations());

        // Invariant checks:
        assertTrue(executor.getActiveResourceReservations() >= 0);
        assertTrue(executor.getPendingCleanupObligations() >= 0);

        // Now release the initial reservation to free capacity
        reservation.release();
        assertEquals(0, executor.getActiveResourceReservations());

        // Now retry failed cleanups: should dynamically acquire pending permit and successfully close
        int submitted = executor.retryFailedCleanups();
        assertEquals(1, submitted, "Should submit 1 retry task");

        deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
        while ((executor.getActiveCleanupWorkers() != 0 || executor.getFailedCleanupObligations() != 0)
                && System.nanoTime() < deadline) {
            Thread.sleep(10);
        }

        assertFalse(nativeHandle.isOpen(), "Native handle must be closed after successful retry");
        assertEquals(0, executor.getRetainedFailedResources().size(), "Retained cleanups must be 0 after successful retry");
        assertEquals(0, executor.getFailedCleanupObligations());
        assertEquals(0, executor.getPendingCleanupObligations());
    }

    @Test
    @DisplayName("Repeated saturated capacity + distinct late handles + close failures across shutdown and retry")
    void repeatedSaturatedCapacityAcrossShutdownAndRetry() throws Exception {
        int capacity = 2;
        DriveIoExecutor executor = createExecutor(4, capacity);

        // Saturate capacity with 2 active reservations
        DriveResourceReservation res1 = executor.acquireReservation();
        DriveResourceReservation res2 = executor.acquireReservation();
        assertNotNull(res1);
        assertNotNull(res2);
        assertEquals(2, executor.getActiveResourceReservations());

        int handleCount = 3;
        List<FileChannel> nativeChannels = new ArrayList<>();
        List<AutoCloseable> resources = new ArrayList<>();
        List<AtomicInteger> attemptCounters = new ArrayList<>();

        for (int i = 0; i < handleCount; i++) {
            Path file = Files.createTempFile("f07-c1-multi-" + i + "-", ".bin");
            tempFiles.add(file);
            FileChannel fc = FileChannel.open(file, StandardOpenOption.READ);
            nativeChannels.add(fc);

            AtomicInteger attempts = new AtomicInteger();
            attemptCounters.add(attempts);
            AutoCloseable res = () -> {
                if (attempts.incrementAndGet() == 1) {
                    throw new IOException("Attempt 1 close failure");
                }
                fc.close();
            };
            resources.add(res);

            CountDownLatch entered = new CountDownLatch(1);
            CountDownLatch release = new CountDownLatch(1);

            Thread caller = new Thread(() -> {
                try {
                    executor.executeWithTimeout(() -> {
                        entered.countDown();
                        while (release.getCount() != 0) {
                            try {
                                release.await();
                            } catch (InterruptedException ignored) {
                            }
                        }
                        return res;
                    }, 50, "multi-timeout-" + attempts);
                } catch (Throwable ignored) {
                }
            });

            caller.start();
            assertTrue(entered.await(2, TimeUnit.SECONDS));
            caller.join(2000);
            release.countDown();

            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(2);
            while (executor.getActualOutstandingWorkers() != 0 && System.nanoTime() < deadline) {
                Thread.sleep(10);
            }
        }

        // All 3 handles must be retained despite queue capacity being 2
        assertEquals(3, executor.getRetainedFailedResources().size());
        assertEquals(3, executor.getFailedCleanupObligations());
        for (FileChannel fc : nativeChannels) {
            assertTrue(fc.isOpen(), "All native channels must remain open");
        }

        // Initiate executor shutdown while retained cleanups exist
        executor.shutdown();
        assertTrue(executor.isShutdown(), "Executor must report isShutdown true");

        // Release the active reservations
        res1.release();
        res2.release();
        assertEquals(0, executor.getActiveResourceReservations());

        // Retry failed cleanups across shutdown
        int retried = executor.retryFailedCleanups();
        assertTrue(retried > 0, "Retry should accept tasks even across shutdown");

        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(4);
        while ((executor.getActiveCleanupWorkers() != 0 || executor.getFailedCleanupObligations() != 0)
                && System.nanoTime() < deadline) {
            // Keep retrying remaining ones if bounded queue filled up
            if (executor.getFailedCleanupObligations() > 0) {
                executor.retryFailedCleanups();
            }
            Thread.sleep(20);
        }

        for (FileChannel fc : nativeChannels) {
            assertFalse(fc.isOpen(), "All native channels must be closed after retry");
        }
        assertEquals(0, executor.getRetainedFailedResources().size());
        assertEquals(0, executor.getFailedCleanupObligations());
        assertEquals(0, executor.getPendingCleanupObligations());
        assertEquals(0, executor.getActiveResourceReservations());
    }
}
