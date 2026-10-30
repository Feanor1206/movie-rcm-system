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
 * DRIVE-01-F08 / Finding R1 Regression & Repro Test Suite.
 *
 * Verifies that:
 * 1. Resource-bounded admission: executeWithTimeout strictly requires a lifecycle reservation before opening resources.
 *    When lifecycle capacity is saturated, it fails fast at admission with MediaUnavailableException.
 * 2. Invariant holds at all times: retainedFailedResources.size() <= pendingCleanupObligations <= cleanupQueueCapacity.
 *    No off-budget retained handles are ever admitted or quarantined.
 * 3. Bounded retention within capacity: failed cleanups are charged to pendingCleanupObligations (chargesPending=true)
 *    and can be retried and recovered across shutdown without leaking handles or corrupting lifecycle counters.
 * 4. Scalar operations (executeMetadata, executeRead) do not consume lifecycle permits and strictly forbid AutoCloseable returns.
 */
@DisplayName("DriveGenericMetadataReproTest - Finding R1 Resource-Bounded Lifecycle Admission")
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
    @DisplayName("R1 Repro: executeWithTimeout fails fast at admission when capacity is saturated without opening/leaking handles")
    void executeWithTimeoutFailsFastWhenCapacitySaturated() throws Exception {
        DriveIoExecutor executor = createExecutor(2, 1);
        DriveResourceReservation reservation = executor.acquireReservation();
        assertNotNull(reservation);
        assertEquals(1, executor.getActiveResourceReservations());
        assertEquals(0, executor.getPendingCleanupObligations());

        CountDownLatch entered = new CountDownLatch(1);
        AtomicReference<Throwable> callerError = new AtomicReference<>();
        AtomicBoolean handleCreated = new AtomicBoolean(false);

        Thread caller = new Thread(() -> {
            try {
                executor.executeWithTimeout(() -> {
                    entered.countDown();
                    handleCreated.set(true);
                    return (AutoCloseable) () -> {};
                }, 100, "test-saturated-admission");
            } catch (Throwable t) {
                callerError.set(t);
            }
        });

        caller.start();
        caller.join(2000);
        assertFalse(caller.isAlive(), "Caller thread must finish");

        // Assert fail-fast admission:
        assertInstanceOf(MediaUnavailableException.class, callerError.get(),
                "executeWithTimeout must throw MediaUnavailableException at admission when capacity is saturated");
        assertEquals(1, entered.getCount(), "Worker must NEVER be entered when capacity is saturated");
        assertFalse(handleCreated.get(), "Handle must NEVER be created when admission fails");

        // Invariant check: zero retained handles, strictly bounded by capacity
        assertEquals(0, executor.getRetainedFailedResources().size());
        assertEquals(0, executor.getPendingCleanupObligations());
        assertEquals(1, executor.getActiveResourceReservations());
        assertTrue(executor.getRetainedFailedResources().size() <= executor.getPendingCleanupObligations());
        assertTrue(executor.getPendingCleanupObligations() <= 1);

        reservation.release();
        assertEquals(0, executor.getActiveResourceReservations());
    }

    @Test
    @DisplayName("R1 Bounded: executeWithTimeout retains on-budget within capacity and bounds further admission")
    void executeWithTimeoutRetainsOnBudgetWithinCapacity() throws Exception {
        int capacity = 2;
        DriveIoExecutor executor = createExecutor(2, capacity);

        // Pre-acquire 1 reservation; 1 permit remains
        DriveResourceReservation res1 = executor.acquireReservation();
        assertEquals(1, executor.getActiveResourceReservations());
        assertEquals(0, executor.getPendingCleanupObligations());

        Path file = Files.createTempFile("f08-r1-budget-", ".bin");
        tempFiles.add(file);
        FileChannel nativeHandle = FileChannel.open(file, StandardOpenOption.READ);
        AtomicInteger attempts = new AtomicInteger();

        AutoCloseable resource = () -> {
            if (attempts.incrementAndGet() == 1) {
                throw new IOException("Simulated close failure on attempt 1");
            }
            nativeHandle.close();
        };

        CountDownLatch entered = new CountDownLatch(1);
        CountDownLatch releaseWorker = new CountDownLatch(1);
        AtomicReference<Throwable> callerError = new AtomicReference<>();

        Thread caller = new Thread(() -> {
            try {
                executor.executeWithTimeout(() -> {
                    entered.countDown();
                    while (releaseWorker.getCount() != 0) {
                        try {
                            releaseWorker.await();
                        } catch (InterruptedException ignored) {}
                    }
                    return resource;
                }, 80, "resource-timeout");
            } catch (Throwable t) {
                callerError.set(t);
            }
        });

        caller.start();
        assertTrue(entered.await(2, TimeUnit.SECONDS), "Worker should enter task within capacity");
        caller.join(2000);
        assertFalse(caller.isAlive(), "Caller should finish after timeout");
        assertInstanceOf(MediaUnavailableException.class, callerError.get());

        // Release worker so worker thread initiates close and catches injected failure
        releaseWorker.countDown();

        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
        while (executor.getActualOutstandingWorkers() != 0 && System.nanoTime() < deadline) {
            Thread.sleep(10);
        }
        assertEquals(0, executor.getActualOutstandingWorkers());

        // Assert failure was retained ON-BUDGET with chargesPending=true:
        assertEquals(1, attempts.get());
        assertTrue(nativeHandle.isOpen());
        assertEquals(1, executor.getRetainedFailedResources().size());
        assertEquals(1, executor.getPendingCleanupObligations(), "Pending cleanup obligations must be charged 1");
        assertEquals(1, executor.getActiveResourceReservations(), "Active reservations remain 1 (res1)");

        // Mathematical invariant:
        // retained (1) <= pending (1) <= capacity (2)
        // total obligations: active (1) + pending (1) == 2 == capacity
        assertEquals(capacity, executor.getActiveResourceReservations() + executor.getPendingCleanupObligations());
        assertTrue(executor.getRetainedFailedResources().size() <= executor.getPendingCleanupObligations());
        assertTrue(executor.getPendingCleanupObligations() <= capacity);

        // Now that capacity (2) is fully saturated (1 active + 1 pending),
        // another executeWithTimeout MUST be rejected fail-fast at admission:
        AtomicBoolean secondTaskRan = new AtomicBoolean(false);
        assertThrows(MediaUnavailableException.class, () -> {
            executor.executeWithTimeout(() -> {
                secondTaskRan.set(true);
                return (AutoCloseable) () -> {};
            }, 100, "second-task");
        }, "Subsequent resource admission must be rejected when active + pending == capacity");
        assertFalse(secondTaskRan.get(), "Second task must never run");

        // Release res1: active becomes 0, pending remains 1
        res1.release();
        assertEquals(0, executor.getActiveResourceReservations());
        assertEquals(1, executor.getPendingCleanupObligations());

        // Retry the retained failure: should succeed and drain pending back to 0
        int submitted = executor.retryFailedCleanups();
        assertEquals(1, submitted);

        deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(3);
        while ((executor.getActiveCleanupWorkers() != 0 || executor.getFailedCleanupObligations() != 0)
                && System.nanoTime() < deadline) {
            Thread.sleep(10);
        }

        assertFalse(nativeHandle.isOpen(), "Native handle must be closed after successful retry");
        assertEquals(0, executor.getRetainedFailedResources().size());
        assertEquals(0, executor.getFailedCleanupObligations());
        assertEquals(0, executor.getPendingCleanupObligations());
        assertEquals(0, executor.getActiveResourceReservations());
    }

    @Test
    @DisplayName("Regression Repro Scenario: 3 sequential calls against capacity 1 cannot produce off-budget retained obligations")
    void reproScenarioThreeCallsAgainstCapacityOneCannotLeak() throws Exception {
        DriveIoExecutor executor = createExecutor(1, 1);
        DriveResourceReservation permit = executor.acquireReservation();
        assertEquals(1, executor.getActiveResourceReservations());
        assertEquals(0, executor.getPendingCleanupObligations());

        List<FileChannel> handles = new ArrayList<>();
        try {
            for (int i = 0; i < 3; i++) {
                Path file = Files.createTempFile("regression-f08-budget-", ".bin");
                tempFiles.add(file);
                FileChannel handle = FileChannel.open(file, StandardOpenOption.READ);
                handles.add(handle);

                AtomicReference<Throwable> error = new AtomicReference<>();
                AtomicBoolean entered = new AtomicBoolean(false);

                Thread caller = new Thread(() -> {
                    try {
                        executor.executeWithTimeout(() -> {
                            entered.set(true);
                            return (AutoCloseable) () -> { throw new IOException("Injected close failure"); };
                        }, 50, "metadata-resource");
                    } catch (Throwable t) {
                        error.set(t);
                    }
                });

                caller.start();
                caller.join(1000);

                // Fail-fast at admission: MediaUnavailableException thrown BEFORE worker entry
                assertInstanceOf(MediaUnavailableException.class, error.get(),
                        "Call " + i + " must fail fast at admission");
                assertFalse(entered.get(), "Worker " + i + " must never enter");
            }

            // Assert that retained obligations NEVER exceed capacity
            int retained = executor.getRetainedFailedResources().size();
            assertEquals(0, retained, "Retained obligations must be 0 (no off-budget quarantine)");
            assertEquals(0, executor.getPendingCleanupObligations());
            assertEquals(1, executor.getActiveResourceReservations());
            assertTrue(retained <= executor.getPendingCleanupObligations());
            assertTrue(executor.getPendingCleanupObligations() <= 1);
        } finally {
            for (FileChannel h : handles) {
                h.close();
            }
            permit.release();
        }
    }

    @Test
    @DisplayName("Scalar Lane: executeMetadata and executeRead do not consume lifecycle permits and forbid AutoCloseable")
    void scalarLaneEnforcesContract() throws Exception {
        DriveIoExecutor executor = createExecutor(2, 1);

        // Saturate lifecycle capacity with 1 reservation
        DriveResourceReservation permit = executor.acquireReservation();
        assertEquals(1, executor.getActiveResourceReservations());
        assertEquals(1, executor.getCleanupQueueCapacity());

        // executeMetadata (scalar) MUST succeed despite lifecycle capacity being saturated
        String metaResult = executor.executeMetadata(() -> "metadata-ok");
        assertEquals("metadata-ok", metaResult);

        // executeRead (scalar) MUST succeed despite lifecycle capacity being saturated
        Integer readResult = executor.executeRead(() -> 1024);
        assertEquals(1024, readResult);

        // executeScalar rejecting AutoCloseable return
        AtomicBoolean closeCalled = new AtomicBoolean(false);
        AutoCloseable forbiddenResource = () -> closeCalled.set(true);

        assertThrows(IllegalArgumentException.class, () -> {
            executor.executeMetadata(() -> forbiddenResource);
        }, "executeMetadata must reject AutoCloseable return with IllegalArgumentException");

        assertTrue(closeCalled.get(), "Forbidden AutoCloseable must be safely closed when rejected");

        permit.release();
        assertEquals(0, executor.getActiveResourceReservations());
    }

    @Test
    @DisplayName("R1 Bounded: executeScalar retains failed cleanup and chains exception when AutoCloseable close throws")
    void scalarLaneRetainsFailedCleanupWhenCloseThrows() throws Exception {
        DriveIoExecutor executor = createExecutor(2, 1);

        // Pre-saturate lifecycle capacity
        DriveResourceReservation permit = executor.acquireReservation();
        assertEquals(1, executor.getActiveResourceReservations());

        AtomicInteger closeAttempts = new AtomicInteger();
        AutoCloseable failingResource = () -> {
            if (closeAttempts.incrementAndGet() == 1) {
                throw new IOException("Simulated close failure in scalar lane");
            }
        };

        IllegalArgumentException iae = assertThrows(IllegalArgumentException.class, () -> {
            executor.executeMetadata(() -> failingResource);
        }, "executeMetadata must reject AutoCloseable return with IllegalArgumentException");

        assertNotNull(iae.getCause(), "Close failure must be chained as cause");
        assertInstanceOf(IOException.class, iae.getCause());
        assertEquals("Simulated close failure in scalar lane", iae.getCause().getMessage());

        // Invariant check: resource retained, not lost!
        assertEquals(1, closeAttempts.get());
        assertTrue(executor.hasFailedCleanup(failingResource), "Failed resource must be retained in executor");
        assertEquals(1, executor.getRetainedFailedResources().size());
        assertEquals(failingResource, executor.getRetainedFailedResources().get(0));

        // Retry cleanup should succeed on second attempt
        boolean retried = executor.retryFailedCleanup(failingResource);
        assertTrue(retried, "Retry must be accepted");

        // Wait for retry completion
        long deadline = System.currentTimeMillis() + 1000;
        while (System.currentTimeMillis() < deadline && executor.hasFailedCleanup(failingResource)) {
            Thread.sleep(10);
        }

        assertEquals(2, closeAttempts.get());
        assertFalse(executor.hasFailedCleanup(failingResource));
        assertEquals(0, executor.getRetainedFailedResources().size());

        permit.release();
        assertEquals(0, executor.getActiveResourceReservations());
    }

    @Test
    @DisplayName("REC-01 Bounded Ownership: repeated saturation and failed scalar close strictly bounds retained handles")
    void scalarLaneEnforcesStrictBoundUnderRepeatedSaturationAndFailedClose() throws Exception {
        int capacity = 2;
        DriveIoExecutor executor = createExecutor(4, capacity);

        List<AtomicInteger> closeAttempts = new ArrayList<>();
        List<AutoCloseable> resources = new ArrayList<>();

        for (int i = 0; i < capacity; i++) {
            AtomicInteger attempts = new AtomicInteger();
            closeAttempts.add(attempts);
            AutoCloseable res = () -> {
                if (attempts.incrementAndGet() == 1) {
                    throw new IOException("Injected close failure");
                }
            };
            resources.add(res);

            assertThrows(IllegalArgumentException.class, () -> {
                executor.executeMetadata(() -> res);
            });
        }

        assertEquals(capacity, executor.getRetainedFailedResources().size());
        assertTrue(executor.getRetainedFailedResources().size() <= executor.getCleanupQueueCapacity());

        AtomicInteger extraTasksRun = new AtomicInteger(0);
        for (int i = 0; i < 5; i++) {
            assertThrows(MediaUnavailableException.class, () -> {
                executor.executeMetadata(() -> {
                    extraTasksRun.incrementAndGet();
                    return "should-not-run";
                });
            }, "Calls must fail fast when retained cleanups saturate capacity");
        }

        assertEquals(0, extraTasksRun.get(), "No additional tasks permitted when capacity is full");
        assertEquals(capacity, executor.getRetainedFailedResources().size(), "Retained cleanups cannot exceed capacity");

        executor.retryFailedCleanups();
        long deadline = System.currentTimeMillis() + 2000;
        while (System.currentTimeMillis() < deadline && !executor.getRetainedFailedResources().isEmpty()) {
            Thread.sleep(10);
        }

        assertEquals(0, executor.getRetainedFailedResources().size(), "All failed cleanups must be recovered");

        String afterRecovery = executor.executeMetadata(() -> "recovered-ok");
        assertEquals("recovered-ok", afterRecovery);
    }
}
