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
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

/**
 * DRIVE-01-F06 / R1 Regression & Repro Test Suite.
 *
 * Verifies:
 * 1. Saturated capacity + unreserved executeOpen helper:
 *    When all capacity is held with legitimate reservations, public unreserved executeOpen
 *    is rejected fail-fast at admission gate, preventing off-budget handle leakage.
 * 2. Pre-admitted bounded ownership:
 *    When capacity is not saturated, unreserved executeOpen acquires an admission permit,
 *    transfers to charged pending failed obligation on close failure, and strictly enforces
 *    retainedFailedResources.size() <= cleanupQueueCapacity.
 * 3. Shutdown and retry recovery:
 *    Executor shutdown preserves cleanupExecutor while pending failed cleanups remain;
 *    retryFailedCleanups successfully drains and disposes retained resources, and cleanupExecutor
 *    terminates cleanly when total obligations reach 0.
 * 4. Invariant assertions:
 *    - activeResourceReservations >= 0
 *    - pendingCleanupObligations >= 0
 *    - activeResourceReservations + pendingCleanupObligations <= cleanupQueueCapacity
 *    - retainedFailedResources.size() <= pendingCleanupObligations
 */
@DisplayName("DriveUnreservedLifecycleReproTest - R1 Pre-Admitted Ownership & Bounded Retained Handles Suite")
public class DriveUnreservedLifecycleReproTest {

    private final List<DriveIoExecutor> managedExecutors = new CopyOnWriteArrayList<>();
    private final List<CountDownLatch> managedLatches = new CopyOnWriteArrayList<>();

    @BeforeEach
    void setUp() {
        managedExecutors.clear();
        managedLatches.clear();
    }

    @AfterEach
    void tearDown() {
        for (CountDownLatch latch : managedLatches) {
            while (latch.getCount() > 0) {
                latch.countDown();
            }
        }
        for (DriveIoExecutor exec : managedExecutors) {
            try {
                if (exec != null && !exec.isShutdown()) {
                    exec.shutdown();
                }
            } catch (Throwable ignored) {}
        }
    }

    static class ThrowingCloseableResource implements AutoCloseable {
        private final String id;
        private final AtomicInteger closeAttempts = new AtomicInteger(0);
        private final AtomicBoolean allowSuccess = new AtomicBoolean(false);
        private final CountDownLatch closedLatch = new CountDownLatch(1);

        public ThrowingCloseableResource(String id) {
            this.id = id;
        }

        public void setAllowSuccess(boolean allow) {
            this.allowSuccess.set(allow);
        }

        public int getCloseAttempts() {
            return closeAttempts.get();
        }

        public CountDownLatch getClosedLatch() {
            return closedLatch;
        }

        @Override
        public void close() throws IOException {
            closeAttempts.incrementAndGet();
            if (!allowSuccess.get()) {
                throw new IOException("Simulated physical close failure on resource " + id);
            }
            closedLatch.countDown();
        }

        @Override
        public String toString() {
            return "ThrowingCloseableResource[" + id + "]";
        }
    }

    @Test
    @DisplayName("Repro R1.1: Saturated capacity rejects unreserved executeOpen at admission - zero off-budget handles")
    void testSaturatedCapacityRejectsUnreservedExecuteOpen_ZeroOffBudgetHandles() throws Exception {
        int capacity = 5;
        int maxWorkers = 10;
        DriveCircuitBreaker cb = new DriveCircuitBreaker(100, 60000); // High threshold to isolate capacity bounds
        DriveIoExecutor io = new DriveIoExecutor(1000, 1000, maxWorkers, capacity, cb);
        managedExecutors.add(io);

        // 1. Hold all capacity with legitimate reservations
        List<DriveResourceReservation> reservations = new ArrayList<>();
        for (int i = 0; i < capacity; i++) {
            reservations.add(io.acquireReservation());
        }
        assertEquals(capacity, io.getActiveResourceReservations());
        assertEquals(0, io.getPendingCleanupObligations());
        assertEquals(capacity, io.getActiveResourceReservations() + io.getPendingCleanupObligations());
        assertEquals(0, io.getRetainedFailedResources().size());

        // 2. Repeatedly execute public unreserved executeOpen with timeout and throwing close
        List<ThrowingCloseableResource> lateResources = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            final String id = "late-saturated-" + i;
            final int opIdx = i;
            final ThrowingCloseableResource resource = new ThrowingCloseableResource(id);
            lateResources.add(resource);

            // Reset circuit breaker so failure threshold doesn't mask admission gate
            cb.reset();

            // Saturated capacity MUST reject unreserved executeOpen at admission gate fail-fast!
            MediaUnavailableException ex = assertThrows(MediaUnavailableException.class, () -> {
                io.executeOpen(() -> {
                    // This task should never run or admit
                    Thread.sleep(50);
                    return resource;
                }, 20, "test-open-" + opIdx);
            });
            assertTrue(ex.getMessage().contains("Dung lượng tài nguyên Google Drive đồng thời đã đạt giới hạn tối đa"));

            // Assert strict capacity invariants: retained resources MUST NOT grow off-budget!
            assertEquals(0, io.getRetainedFailedResources().size(),
                    "Off-budget retained failed resources must NOT leak when capacity is saturated!");
            assertEquals(0, io.getFailedCleanupObligations());
            assertEquals(capacity, io.getActiveResourceReservations());
            assertEquals(0, io.getPendingCleanupObligations());
            assertEquals(capacity, io.getActiveResourceReservations() + io.getPendingCleanupObligations());
        }

        // Release legitimate reservations
        for (DriveResourceReservation res : reservations) {
            res.release();
        }
        assertEquals(0, io.getActiveResourceReservations());
        assertEquals(0, io.getPendingCleanupObligations());
        assertEquals(0, io.getRetainedFailedResources().size());
    }

    @Test
    @DisplayName("Repro R1.2: Unreserved executeOpen pre-admits permit and enforces strict capacity bound")
    void testUnreservedExecuteOpen_PreAdmitsAndEnforcesStrictCapacityBound() throws Exception {
        int capacity = 3;
        int maxWorkers = 5;
        DriveCircuitBreaker cb = new DriveCircuitBreaker(100, 60000);
        DriveIoExecutor io = new DriveIoExecutor(1000, 1000, maxWorkers, capacity, cb);
        managedExecutors.add(io);

        List<ThrowingCloseableResource> lateResources = new ArrayList<>();

        // Fill capacity using unreserved executeOpen timeout + close failures
        for (int i = 0; i < capacity; i++) {
            final String id = "late-fill-" + i;
            final ThrowingCloseableResource resource = new ThrowingCloseableResource(id);
            lateResources.add(resource);
            cb.reset();

            final CountDownLatch releaseWorker = new CountDownLatch(1);
            managedLatches.add(releaseWorker);

            // Timeout occurs after 20ms while worker waits on releaseWorker
            assertThrows(MediaUnavailableException.class, () -> {
                io.executeOpen(() -> {
                    while (true) {
                        try {
                            releaseWorker.await();
                            break;
                        } catch (InterruptedException ignored) {}
                    }
                    return resource;
                }, 20, "open-" + id);
            });

            // Now release worker so it produces resource and attempts close
            releaseWorker.countDown();

            // Wait for worker to finish and record failed cleanup
            long deadline = System.currentTimeMillis() + 3000;
            while (!io.hasFailedCleanup(resource) && System.currentTimeMillis() < deadline) {
                Thread.sleep(10);
            }

            // Verify that this resource was retained AND charged to pending!
            assertTrue(io.hasFailedCleanup(resource));
            assertTrue(resource.getCloseAttempts() >= 1);
            assertEquals(i + 1, io.getRetainedFailedResources().size());
            assertEquals(i + 1, io.getPendingCleanupObligations());
            assertEquals(0, io.getActiveResourceReservations());
            assertEquals(i + 1, io.getActiveResourceReservations() + io.getPendingCleanupObligations());
        }

        // Now capacity is 100% full (3 pending failed obligations)
        assertEquals(capacity, io.getPendingCleanupObligations());
        assertEquals(capacity, io.getRetainedFailedResources().size());

        // Any further open (reserved or unreserved) MUST be rejected!
        cb.reset();
        ThrowingCloseableResource extraResource = new ThrowingCloseableResource("extra-at-cap");
        assertThrows(MediaUnavailableException.class, () -> {
            io.executeOpen(() -> extraResource, 50, "extra");
        });
        assertEquals(capacity, io.getRetainedFailedResources().size());
        assertEquals(capacity, io.getPendingCleanupObligations());

        // 3. Test shutdown with retained records:
        // Shutdown must NOT terminate cleanupExecutor while pending obligations exist!
        io.shutdown();
        assertTrue(io.isShutdown());

        // 4. Retry recovery: allow resources to close and execute retryFailedCleanups
        for (ThrowingCloseableResource r : lateResources) {
            r.setAllowSuccess(true);
        }

        int submitted = io.retryFailedCleanups();
        assertEquals(capacity, submitted);

        // Wait for all retries to complete
        for (ThrowingCloseableResource r : lateResources) {
            assertTrue(r.getClosedLatch().await(2, TimeUnit.SECONDS),
                    "Resource " + r.id + " should have closed successfully on retry");
        }

        // Verify that all retained resources are cleared and counters reach baseline 0
        Thread.sleep(100);
        assertEquals(0, io.getRetainedFailedResources().size());
        assertEquals(0, io.getFailedCleanupObligations());
        assertEquals(0, io.getPendingCleanupObligations());
        assertEquals(0, io.getActiveResourceReservations());
    }

    @Test
    @DisplayName("Repro R1.3: Helper vs Reserved path distinction and physical close retry idempotency")
    void testHelperVsReservedPath_PhysicalCloseRetryIdempotency() throws Exception {
        int capacity = 4;
        int maxWorkers = 5;
        DriveCircuitBreaker cb = new DriveCircuitBreaker(100, 60000);
        DriveIoExecutor io = new DriveIoExecutor(1000, 1000, maxWorkers, capacity, cb);
        managedExecutors.add(io);

        // 1. Reserved path: production adapter acquires reservation first
        DriveResourceReservation res = io.acquireReservation();
        assertEquals(1, io.getActiveResourceReservations());
        assertEquals(0, io.getPendingCleanupObligations());

        ThrowingCloseableResource resResource = new ThrowingCloseableResource("reserved-res-1");
        // Successful open on reserved path retains reservation active
        ThrowingCloseableResource acquired = io.executeOpen(() -> resResource, 500, "open-res", res);
        assertSame(resResource, acquired);
        assertTrue(res.isActive());
        assertEquals(1, io.getActiveResourceReservations());

        // Closing reserved resource through closeAsync accepts into cleanup queue and transfers active to pending
        assertTrue(res.closeAsync(resResource, "close-res-failing"));

        // Wait for cleanup worker to execute close and fail
        long deadline = System.currentTimeMillis() + 2000;
        while (!res.hasFailedCleanup() && System.currentTimeMillis() < deadline) {
            Thread.sleep(10);
        }

        assertEquals(0, io.getActiveResourceReservations());
        assertEquals(1, io.getPendingCleanupObligations());
        assertTrue(res.hasFailedCleanup());
        assertTrue(io.hasFailedCleanup(resResource));

        // 2. Helper unreserved path: open succeeds and releases internal admission permit
        ThrowingCloseableResource helperResource = new ThrowingCloseableResource("helper-res-1");
        ThrowingCloseableResource helperAcquired = io.executeOpen(() -> helperResource, 500, "open-helper");
        assertSame(helperResource, helperAcquired);
        // Helper path releases internal reservation upon caller acquisition!
        assertEquals(0, io.getActiveResourceReservations());
        assertEquals(1, io.getPendingCleanupObligations()); // Only the reserved failed resource remains

        // Recover reserved resource
        resResource.setAllowSuccess(true);
        assertTrue(res.retryCleanup());
        assertTrue(resResource.getClosedLatch().await(2, TimeUnit.SECONDS));

        Thread.sleep(50);
        assertEquals(0, io.getPendingCleanupObligations());
        assertEquals(0, io.getRetainedFailedResources().size());
        assertFalse(res.hasFailedCleanup());
    }
}
