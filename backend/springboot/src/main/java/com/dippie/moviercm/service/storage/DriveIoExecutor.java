package com.dippie.moviercm.service.storage;

import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.exception.SecurityPathTraversalException;

import java.io.IOException;
import java.util.List;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Executes Drive IO operations with finite deadlines, bounded worker pool,
 * accurate physical worker accounting, circuit breaking, cleanup queue admission control,
 * and resource ownership handshakes.
 */
public class DriveIoExecutor {

    public enum OpenState {
        PENDING,
        CALLER_ACQUIRED,
        TIMED_OUT
    }

    /**
     * Immutable atomic composite state representing active reservations,
     * pending cleanup obligations, and shutdown state in a single reference.
     * Guarantees zero transient gap or undercount during transfers.
     */
    public static final class LifecycleState {
        private final int active;
        private final int pending;
        private final boolean shutdown;

        public LifecycleState(int active, int pending, boolean shutdown) {
            this.active = active;
            this.pending = pending;
            this.shutdown = shutdown;
        }

        public int getActive() { return active; }
        public int getPending() { return pending; }
        public boolean isShutdown() { return shutdown; }
        public int getTotal() { return active + pending; }

        @Override
        public String toString() {
            return "LifecycleState[active=" + active + ", pending=" + pending + ", shutdown=" + shutdown + "]";
        }
    }

    /**
     * Bounded record of a failed cleanup obligation retaining the actual resource reference,
     * failure diagnostics, and associated reservation for controlled retry.
     */
    public static final class RetainedFailedCleanup {
        private final AutoCloseable resource;
        private final String operationName;
        private volatile Throwable cause;
        private volatile long failedTimestamp;
        private final DriveResourceReservation reservation;
        private final boolean chargesPending;
        private final AtomicBoolean inFlight = new AtomicBoolean(false);

        public RetainedFailedCleanup(AutoCloseable resource, String operationName, Throwable cause, DriveResourceReservation reservation) {
            this(resource, operationName, cause, reservation, true);
        }

        public RetainedFailedCleanup(AutoCloseable resource, String operationName, Throwable cause, DriveResourceReservation reservation, boolean chargesPending) {
            this.resource = resource;
            this.operationName = operationName;
            this.cause = cause;
            this.failedTimestamp = System.currentTimeMillis();
            this.reservation = reservation;
            this.chargesPending = chargesPending;
        }

        public boolean markInFlight() {
            return inFlight.compareAndSet(false, true);
        }

        public void clearInFlight() {
            inFlight.set(false);
        }

        public void updateFailure(Throwable newCause) {
            this.cause = newCause;
            this.failedTimestamp = System.currentTimeMillis();
            this.inFlight.set(false);
        }

        public boolean isInFlight() { return inFlight.get(); }
        public AutoCloseable getResource() { return resource; }
        public String getOperationName() { return operationName; }
        public Throwable getCause() { return cause; }
        public long getFailedTimestamp() { return failedTimestamp; }
        public DriveResourceReservation getReservation() { return reservation; }
        public boolean chargesPending() { return chargesPending; }
    }

    private final long metadataTimeoutMs;
    private final long readTimeoutMs;
    private final int maxWorkers;
    private final int cleanupQueueCapacity;
    private final DriveCircuitBreaker circuitBreaker;
    private final ExecutorService executor;
    private final ThreadPoolExecutor cleanupExecutor;

    // Truthful physical metric lanes & failure tracking
    private final AtomicInteger actualOutstandingWorkers = new AtomicInteger(0);
    private final AtomicInteger activeCleanupWorkers = new AtomicInteger(0);
    private final AtomicInteger failedCleanupObligations = new AtomicInteger(0);

    // Atomic shared lifecycle budget/state: eliminates transient undercount/gaps
    private final AtomicReference<LifecycleState> lifecycle =
            new AtomicReference<>(new LifecycleState(0, 0, false));

    // Bounded retained failed cleanup obligations for explicit controlled retry
    private final ConcurrentMap<AutoCloseable, RetainedFailedCleanup> retainedFailedCleanups =
            new ConcurrentHashMap<>();

    // Disposal handshake states for late-opened / timed-out resources
    private static final int DISPOSAL_UNCLAIMED = 0;
    private static final int DISPOSAL_CALLER_DISPATCHING = 1;
    private static final int DISPOSAL_DISPATCH_ACCEPTED = 2;
    private static final int DISPOSAL_DISPATCH_FAILED = 3;
    private static final int DISPOSAL_WORKER_CLAIMED = 4;
    private static final int DISPOSAL_RETAINED = 5;

    public DriveIoExecutor(long metadataTimeoutMs,
                           long readTimeoutMs,
                           int maxWorkers,
                           int cleanupQueueCapacity,
                           DriveCircuitBreaker circuitBreaker) {
        this.metadataTimeoutMs = metadataTimeoutMs > 0 ? metadataTimeoutMs : 3000;
        this.readTimeoutMs = readTimeoutMs > 0 ? readTimeoutMs : 5000;
        this.maxWorkers = maxWorkers > 0 ? maxWorkers : 10;
        this.cleanupQueueCapacity = cleanupQueueCapacity > 0 ? cleanupQueueCapacity : 256;
        this.circuitBreaker = circuitBreaker != null ? circuitBreaker : new DriveCircuitBreaker();

        ThreadFactory threadFactory = new ThreadFactory() {
            private final AtomicInteger threadId = new AtomicInteger(0);
            @Override
            public Thread newThread(Runnable r) {
                Thread t = new Thread(r, "drive-io-worker-" + threadId.incrementAndGet());
                t.setDaemon(true);
                return t;
            }
        };

        this.executor = new ThreadPoolExecutor(
                0,
                this.maxWorkers,
                60L,
                TimeUnit.SECONDS,
                new SynchronousQueue<>(),
                threadFactory,
                new ThreadPoolExecutor.AbortPolicy()
        );

        ThreadFactory cleanupThreadFactory = new ThreadFactory() {
            private final AtomicInteger cleanupThreadId = new AtomicInteger(0);
            @Override
            public Thread newThread(Runnable r) {
                Thread t = new Thread(r, "drive-io-cleanup-" + cleanupThreadId.incrementAndGet());
                t.setDaemon(true);
                return t;
            }
        };

        int cleanupMaxThreads = Math.max(2, Math.min(8, this.maxWorkers));
        this.cleanupExecutor = new ThreadPoolExecutor(
                cleanupMaxThreads,
                cleanupMaxThreads,
                60L,
                TimeUnit.SECONDS,
                new LinkedBlockingQueue<>(this.cleanupQueueCapacity),
                cleanupThreadFactory,
                new ThreadPoolExecutor.AbortPolicy()
        );
        this.cleanupExecutor.allowCoreThreadTimeOut(true);
    }

    public DriveIoExecutor(long metadataTimeoutMs,
                           long readTimeoutMs,
                           int maxWorkers,
                           DriveCircuitBreaker circuitBreaker) {
        this(metadataTimeoutMs, readTimeoutMs, maxWorkers, 256, circuitBreaker);
    }

    public DriveIoExecutor() {
        this(3000, 5000, 10, 256, new DriveCircuitBreaker());
    }

    public <T> T executeMetadata(Callable<T> task) {
        return executeScalar(task, metadataTimeoutMs, "metadata");
    }

    public <T> T executeRead(Callable<T> task) {
        return executeScalar(task, readTimeoutMs, "read");
    }

    /**
     * Executes a pure scalar metadata or read operation without consuming lifecycle reservation permits.
     * Guaranteed to never return or leak an AutoCloseable resource.
     */
    public <T> T executeScalar(Callable<T> task, long timeoutMs, String operationDescription) {
        if (!circuitBreaker.allowExecution()) {
            throw new MediaUnavailableException("Dịch vụ lưu trữ Google Drive tạm thời không khả dụng (Circuit Breaker OPEN)");
        }

        if (retainedFailedCleanups.size() >= cleanupQueueCapacity) {
            circuitBreaker.recordFailure();
            throw new MediaUnavailableException("Hàng đợi giải phóng tài nguyên Google Drive đã đầy ("
                    + cleanupQueueCapacity + " tài nguyên lỗi đang chờ giải phóng)");
        }

        int current = actualOutstandingWorkers.incrementAndGet();
        if (current > maxWorkers) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            throw new MediaUnavailableException("Số lượng tác vụ truy xuất Google Drive đồng thời đã đạt giới hạn tối đa (" + maxWorkers + ")");
        }

        Future<T> future;
        try {
            future = executor.submit(() -> {
                try {
                    T result = task.call();
                    if (result instanceof AutoCloseable ac) {
                        try {
                            ac.close();
                        } catch (Throwable closeEx) {
                            // Close failed: acquire pending permit if capacity allows and retain failed cleanup
                            boolean acquiredPending = false;
                            while (true) {
                                LifecycleState cur = lifecycle.get();
                                if (cur.isShutdown() || cur.getTotal() >= cleanupQueueCapacity) {
                                    break;
                                }
                                LifecycleState next = new LifecycleState(cur.getActive(), cur.getPending() + 1, cur.isShutdown());
                                if (lifecycle.compareAndSet(cur, next)) {
                                    acquiredPending = true;
                                    break;
                                }
                            }
                            recordFailedCleanup(ac, operationDescription, closeEx, null, acquiredPending);
                            throw new IllegalArgumentException(
                                    "Thao tác vô hướng (scalar) không được phép trả về tài nguyên AutoCloseable: " + operationDescription, closeEx);
                        }
                        throw new IllegalArgumentException("Thao tác vô hướng (scalar) không được phép trả về tài nguyên AutoCloseable: " + operationDescription);
                    }
                    return result;
                } finally {
                    actualOutstandingWorkers.decrementAndGet();
                }
            });
        } catch (RejectedExecutionException e) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            throw new MediaUnavailableException("Hàng đợi tác vụ truy xuất Google Drive đã đầy");
        }

        try {
            T result = future.get(timeoutMs, TimeUnit.MILLISECONDS);
            circuitBreaker.recordSuccess();
            return result;
        } catch (TimeoutException e) {
            future.cancel(true);
            circuitBreaker.recordFailure();
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive (" + operationDescription + ") vượt quá thời gian chờ (" + timeoutMs + "ms)");
        } catch (ExecutionException e) {
            Throwable cause = e.getCause();
            if (cause instanceof SecurityPathTraversalException || cause instanceof MediaNotFoundException) {
                throw (RuntimeException) cause;
            }
            circuitBreaker.recordFailure();
            if (cause instanceof RuntimeException re) {
                throw re;
            }
            if (cause instanceof Error err) {
                throw err;
            }
            MediaUnavailableException ex = new MediaUnavailableException("Lỗi IO khi truy xuất Google Drive: " + cause.getMessage());
            ex.initCause(cause);
            throw ex;
        } catch (InterruptedException e) {
            future.cancel(true);
            circuitBreaker.recordFailure();
            Thread.currentThread().interrupt();
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive bị gián đoạn");
        }
    }

    /**
     * Executes a resource-producing operation with strict lifecycle admission,
     * finite deadline, and guaranteed bounded cleanup on timeout/failure.
     */
    public <T> T executeWithTimeout(Callable<T> task, long timeoutMs, String operationDescription) {
        if (!circuitBreaker.allowExecution()) {
            throw new MediaUnavailableException("Dịch vụ lưu trữ Google Drive tạm thời không khả dụng (Circuit Breaker OPEN)");
        }

        // Strict lifecycle admission: every resource-producing task MUST hold a pre-admitted permit!
        final DriveResourceReservation reservation = acquireReservation();

        int current = actualOutstandingWorkers.incrementAndGet();
        if (current > maxWorkers) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            if (reservation.isActive()) {
                reservation.release();
            }
            throw new MediaUnavailableException("Số lượng tác vụ truy xuất Google Drive đồng thời đã đạt giới hạn tối đa (" + maxWorkers + ")");
        }

        final AtomicReference<OpenState> state = new AtomicReference<>(OpenState.PENDING);
        final AtomicReference<T> resultRef = new AtomicReference<>(null);
        final AtomicInteger disposalState = new AtomicInteger(DISPOSAL_UNCLAIMED);
        final AtomicBoolean workerCompleted = new AtomicBoolean(false);

        Future<T> future;
        try {
            future = executor.submit(() -> {
                T result = null;
                try {
                    result = task.call();
                    resultRef.set(result);
                    if (state.get() == OpenState.TIMED_OUT) {
                        claimAndCloseLateResult(result, reservation, operationDescription, disposalState);
                    }
                    return result;
                } finally {
                    try {
                        if (state.get() == OpenState.TIMED_OUT) {
                            T late = resultRef.get();
                            claimAndCloseLateResult(late, reservation, operationDescription, disposalState);
                        } else if (result == null && reservation.isActive()) {
                            reservation.release();
                        }
                    } finally {
                        workerCompleted.set(true);
                        if (disposalState.compareAndSet(DISPOSAL_DISPATCH_FAILED, DISPOSAL_WORKER_CLAIMED)) {
                            T late = resultRef.get();
                            claimAndCloseLateResult(late, reservation, operationDescription, disposalState);
                        }
                        actualOutstandingWorkers.decrementAndGet();
                    }
                }
            });
        } catch (RejectedExecutionException e) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            if (reservation.isActive()) {
                reservation.release();
            }
            throw new MediaUnavailableException("Hàng đợi tác vụ truy xuất Google Drive đã đầy");
        }

        try {
            T result = future.get(timeoutMs, TimeUnit.MILLISECONDS);
            if (state.compareAndSet(OpenState.PENDING, OpenState.CALLER_ACQUIRED)) {
                circuitBreaker.recordSuccess();
                if (reservation.isActive()) {
                    reservation.release();
                }
                return result;
            } else {
                T late = resultRef.get() != null ? resultRef.get() : result;
                if (late instanceof AutoCloseable ac) {
                    dispatchLateDisposal(ac, reservation, true, operationDescription, disposalState, workerCompleted);
                } else if (reservation.isActive()) {
                    reservation.release();
                }
                throw new MediaUnavailableException("Thao tác truy xuất Google Drive (" + operationDescription + ") đã bị quá hạn");
            }
        } catch (TimeoutException e) {
            future.cancel(true);
            circuitBreaker.recordFailure();
            state.compareAndSet(OpenState.PENDING, OpenState.TIMED_OUT);
            T late = resultRef.get();
            if (late instanceof AutoCloseable ac) {
                dispatchLateDisposal(ac, reservation, true, operationDescription, disposalState, workerCompleted);
            } else if (late == null && !workerCompleted.get()) {
                // Worker still running; will claim when done
            } else if (reservation.isActive()) {
                reservation.release();
            }
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive (" + operationDescription + ") vượt quá thời gian chờ (" + timeoutMs + "ms)");
        } catch (InterruptedException e) {
            future.cancel(true);
            circuitBreaker.recordFailure();
            state.compareAndSet(OpenState.PENDING, OpenState.TIMED_OUT);
            T late = resultRef.get();
            if (late instanceof AutoCloseable ac) {
                dispatchLateDisposal(ac, reservation, true, operationDescription, disposalState, workerCompleted);
            } else if (late == null && !workerCompleted.get()) {
                // Worker still running; will claim when done
            } else if (reservation.isActive()) {
                reservation.release();
            }
            Thread.currentThread().interrupt();
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive bị gián đoạn");
        } catch (ExecutionException e) {
            state.compareAndSet(OpenState.PENDING, OpenState.TIMED_OUT);
            if (reservation.isActive()) {
                reservation.release();
            }
            Throwable cause = e.getCause();
            if (cause instanceof SecurityPathTraversalException || cause instanceof MediaNotFoundException) {
                throw (RuntimeException) cause;
            }
            circuitBreaker.recordFailure();
            if (cause instanceof RuntimeException re) {
                throw re;
            }
            if (cause instanceof Error err) {
                throw err;
            }
            MediaUnavailableException ex = new MediaUnavailableException("Lỗi IO khi truy xuất Google Drive: " + cause.getMessage());
            ex.initCause(cause);
            throw ex;
        }
    }

    private void claimAndCloseLateResult(Object result,
                                         DriveResourceReservation reservation,
                                         String opName,
                                         AtomicInteger disposalState) {
        if (result instanceof AutoCloseable ac) {
            claimAndCloseOnWorker(ac, reservation, opName, disposalState);
        } else if (reservation != null && reservation.isActive()) {
            reservation.release();
        }
    }

    /**
     * Executes a resource opening task with strict ownership handshake, finite deadline,
     * and guaranteed exactly-once disposal on timeout/abandonment.
     */
    public <T extends AutoCloseable> T executeOpen(Callable<T> openTask, long timeoutMs, String opName) throws IOException {
        return executeOpen(openTask, timeoutMs, opName, null, null, null);
    }

    public <T extends AutoCloseable> T executeOpen(Callable<T> openTask, long timeoutMs, String opName, DriveResourceReservation reservation) throws IOException {
        return executeOpen(openTask, timeoutMs, opName, null, null, reservation);
    }

    public <T extends AutoCloseable> T executeOpen(Callable<T> openTask,
                                                   long timeoutMs,
                                                   String opName,
                                                   AtomicReference<OpenState> externalStateRef,
                                                   AtomicReference<T> externalResourceRef) throws IOException {
        return executeOpen(openTask, timeoutMs, opName, externalStateRef, externalResourceRef, null);
    }

    public <T extends AutoCloseable> T executeOpen(Callable<T> openTask,
                                                   long timeoutMs,
                                                   String opName,
                                                   AtomicReference<OpenState> externalStateRef,
                                                   AtomicReference<T> externalResourceRef,
                                                   DriveResourceReservation reservation) throws IOException {
        // 1. Circuit breaker gate
        if (!circuitBreaker.allowExecution()) {
            if (reservation != null && reservation.isActive()) {
                reservation.release();
            }
            throw new MediaUnavailableException("Dịch vụ lưu trữ Google Drive tạm thời không khả dụng (Circuit Breaker OPEN)");
        }

        // 2. Strict lifecycle admission gate: every open operation (reserved or unreserved) MUST hold a pre-admitted permit!
        final boolean isInternalReservation = (reservation == null);
        final DriveResourceReservation effectiveReservation;
        try {
            effectiveReservation = isInternalReservation ? acquireReservation() : reservation;
        } catch (MediaUnavailableException mue) {
            // Capacity saturated or executor shut down: open is rejected fail-fast without creating untracked resources
            throw mue;
        }

        // 3. Strict worker capacity gate
        int current = actualOutstandingWorkers.incrementAndGet();
        if (current > maxWorkers) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            if (effectiveReservation != null && effectiveReservation.isActive()) {
                effectiveReservation.release();
            }
            throw new MediaUnavailableException("Số lượng tác vụ truy xuất Google Drive đồng thời đã đạt giới hạn tối đa (" + maxWorkers + ")");
        }

        // 4. Ownership handshake state
        final AtomicReference<OpenState> state = externalStateRef != null ? externalStateRef : new AtomicReference<>(OpenState.PENDING);
        if (state.get() == null) {
            state.set(OpenState.PENDING);
        }
        final AtomicReference<T> resourceRef = externalResourceRef != null ? externalResourceRef : new AtomicReference<>(null);
        final AtomicInteger disposalState = new AtomicInteger(DISPOSAL_UNCLAIMED);
        final AtomicBoolean workerCompleted = new AtomicBoolean(false);

        // 5. Submit open task to bounded worker pool
        Future<T> future;
        try {
            future = executor.submit(() -> {
                T resource = null;
                try {
                    resource = openTask.call();
                    resourceRef.set(resource);
                    // Worker checks if caller timed out / was interrupted
                    if (state.get() == OpenState.TIMED_OUT) {
                        claimAndCloseOnWorker(resource, effectiveReservation, opName, disposalState);
                    }
                    return resource;
                } finally {
                    try {
                        if (state.get() == OpenState.TIMED_OUT) {
                            T late = resourceRef.get();
                            if (late != null) {
                                claimAndCloseOnWorker(late, effectiveReservation, opName, disposalState);
                            } else if (effectiveReservation != null && effectiveReservation.isActive()) {
                                // openTask threw before producing a resource
                                effectiveReservation.release();
                            }
                        }
                    } finally {
                        workerCompleted.set(true);
                        if (disposalState.compareAndSet(DISPOSAL_DISPATCH_FAILED, DISPOSAL_WORKER_CLAIMED)) {
                            T late = resourceRef.get();
                            if (late != null) {
                                closeLateResourceOnWorker(late, effectiveReservation, opName);
                            }
                        }
                        actualOutstandingWorkers.decrementAndGet();
                    }
                }
            });
        } catch (RejectedExecutionException e) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            if (effectiveReservation != null && effectiveReservation.isActive()) {
                effectiveReservation.release();
            }
            throw new MediaUnavailableException("Hàng đợi tác vụ truy xuất Google Drive đã đầy");
        }

        // 6. Await with finite deadline and handshake resolution
        try {
            T result = future.get(timeoutMs, TimeUnit.MILLISECONDS);
            if (state.compareAndSet(OpenState.PENDING, OpenState.CALLER_ACQUIRED)) {
                circuitBreaker.recordSuccess();
                if (isInternalReservation && effectiveReservation != null && effectiveReservation.isActive()) {
                    effectiveReservation.release();
                }
                return result;
            } else {
                // If caller had already timed out or abandoned ownership:
                T late = resourceRef.get() != null ? resourceRef.get() : result;
                if (late != null) {
                    dispatchLateDisposal(late, effectiveReservation, isInternalReservation, opName, disposalState, workerCompleted);
                }
                throw new MediaUnavailableException("Thao tác truy xuất Google Drive (" + opName + ") đã bị quá hạn");
            }
        } catch (TimeoutException e) {
            future.cancel(true);
            circuitBreaker.recordFailure();
            state.compareAndSet(OpenState.PENDING, OpenState.TIMED_OUT);
            T late = resourceRef.get();
            if (late != null) {
                dispatchLateDisposal(late, effectiveReservation, isInternalReservation, opName, disposalState, workerCompleted);
            }
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive (" + opName + ") vượt quá thời gian chờ (" + timeoutMs + "ms)");
        } catch (InterruptedException e) {
            future.cancel(true);
            Thread.currentThread().interrupt();
            circuitBreaker.recordFailure();
            state.compareAndSet(OpenState.PENDING, OpenState.TIMED_OUT);
            T late = resourceRef.get();
            if (late != null) {
                dispatchLateDisposal(late, effectiveReservation, isInternalReservation, opName, disposalState, workerCompleted);
            }
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive bị gián đoạn");
        } catch (ExecutionException e) {
            state.compareAndSet(OpenState.PENDING, OpenState.TIMED_OUT);
            if (effectiveReservation != null && effectiveReservation.isActive()) {
                effectiveReservation.release();
            }
            Throwable cause = e.getCause();
            if (cause instanceof SecurityPathTraversalException || cause instanceof MediaNotFoundException) {
                throw (RuntimeException) cause;
            }
            circuitBreaker.recordFailure();
            if (cause instanceof IOException ioe) {
                throw ioe;
            }
            if (cause instanceof RuntimeException re) {
                throw re;
            }
            if (cause instanceof Error err) {
                throw err;
            }
            throw new IOException("Lỗi IO khi mở tài nguyên Google Drive: " + cause.getMessage(), cause);
        }
    }

    public <T extends AutoCloseable> T executeOpen(Callable<T> openTask) throws IOException {
        return executeOpen(openTask, metadataTimeoutMs, "open");
    }

    public <T extends AutoCloseable> T executeOpen(Callable<T> openTask, String opName) throws IOException {
        return executeOpen(openTask, metadataTimeoutMs, opName);
    }

    private <T extends AutoCloseable> void claimAndCloseOnWorker(
            T resource,
            DriveResourceReservation reservation,
            String opName,
            AtomicInteger disposalState) {
        if (disposalState.compareAndSet(DISPOSAL_UNCLAIMED, DISPOSAL_WORKER_CLAIMED)) {
            closeLateResourceOnWorker(resource, reservation, opName);
            return;
        }
        // If caller is currently dispatching, spin-wait briefly for caller's dispatch to finish (<1ms)
        while (disposalState.get() == DISPOSAL_CALLER_DISPATCHING) {
            Thread.onSpinWait();
        }
        // If caller dispatch failed (rejected by cleanup executor/budget), worker claims and closes
        if (disposalState.compareAndSet(DISPOSAL_DISPATCH_FAILED, DISPOSAL_WORKER_CLAIMED)) {
            closeLateResourceOnWorker(resource, reservation, opName);
        }
    }

    /**
     * Dispatches late disposal of an open resource when the caller timed out or was interrupted.
     * Guarantees:
     * 1. Multi-state disposal machine eliminates TOCTOU races:
     *    - If worker is running and caller dispatch is rejected, transitions to DISPATCH_FAILED so worker claims and closes.
     *    - If worker already completed, caller retains failed obligation without resetting gates.
     * 2. Unreserved cleanups only charge pending budget if total < cleanupQueueCapacity, strictly
     *    preserving admission bounds and preventing subsequent negative pending underflow on retry.
     * 3. Absolutely NEVER blocks the caller thread or executes synchronous close on caller thread.
     */
    private void dispatchLateDisposal(AutoCloseable resource,
                                      DriveResourceReservation reservation,
                                      boolean isInternalReservation,
                                      String opName,
                                      AtomicInteger disposalState,
                                      AtomicBoolean workerCompleted) {
        if (resource == null) {
            return;
        }
        if (!disposalState.compareAndSet(DISPOSAL_UNCLAIMED, DISPOSAL_CALLER_DISPATCHING)) {
            return;
        }

        boolean accepted = false;
        if (reservation != null && !isInternalReservation) {
            accepted = reservation.closeAsync(resource, opName);
            if (accepted) {
                disposalState.set(DISPOSAL_DISPATCH_ACCEPTED);
            } else {
                if (!workerCompleted.get()) {
                    disposalState.set(DISPOSAL_DISPATCH_FAILED);
                    if (workerCompleted.get() && disposalState.compareAndSet(DISPOSAL_DISPATCH_FAILED, DISPOSAL_RETAINED)) {
                        reservation.transferToFailed(resource, opName, new RejectedExecutionException("Cleanup submission rejected"));
                    }
                } else {
                    disposalState.set(DISPOSAL_RETAINED);
                    reservation.transferToFailed(resource, opName, new RejectedExecutionException("Cleanup submission rejected"));
                }
            }
        } else {
            accepted = executeCleanupAsync(resource, opName);
            if (accepted) {
                disposalState.set(DISPOSAL_DISPATCH_ACCEPTED);
                if (reservation != null && reservation.isActive()) {
                    reservation.release();
                }
            } else {
                if (!workerCompleted.get()) {
                    // Worker is still actively running on background thread; signal DISPATCH_FAILED so worker claims and closes
                    disposalState.set(DISPOSAL_DISPATCH_FAILED);
                    // If worker completed before claiming DISPOSAL_WORKER_CLAIMED, caller retains obligation
                    if (workerCompleted.get() && disposalState.compareAndSet(DISPOSAL_DISPATCH_FAILED, DISPOSAL_RETAINED)) {
                        if (reservation != null && reservation.isActive()) {
                            reservation.transferToFailed(resource, opName, new RejectedExecutionException("Cleanup submission rejected"));
                        }
                    }
                } else {
                    // Worker already exited; unreserved cleanup rejected.
                    disposalState.set(DISPOSAL_RETAINED);
                    if (reservation != null && reservation.isActive()) {
                        reservation.transferToFailed(resource, opName, new RejectedExecutionException("Cleanup submission rejected"));
                    }
                }
            }
        }
    }

    /**
     * Closes a late-opened resource on the worker thread when the caller timed out or was interrupted.
     * Guaranteed atomic: initiates close exactly once, charges physical worker and reservation metrics,
     * releases reservation upon success, or transfers to a retained pending failed obligation if close throws.
     */
    private void closeLateResourceOnWorker(AutoCloseable resource,
                                           DriveResourceReservation reservation,
                                           String opName) {
        if (resource == null) {
            if (reservation != null && reservation.isActive()) {
                reservation.release();
            }
            return;
        }

        try {
            resource.close();
            // Physical close succeeded: release the reservation permit
            if (reservation != null && reservation.isActive()) {
                reservation.release();
            }
        } catch (Throwable closeEx) {
            // Physical close threw: retain ownership as pending failed obligation without double decrement!
            if (reservation != null && reservation.isActive()) {
                if (!reservation.transferToFailed(resource, opName, closeEx)) {
                    recordFailedCleanup(resource, opName, closeEx, reservation);
                }
            }
        }
    }

    /**
     * Acquires an admission reservation permit for Google Drive resource lifecycle.
     * Prevents unbounded resource open operations by enforcing strict capacity limits
     * against total pending cleanup obligations and active reservations.
     *
     * @return an active DriveResourceReservation permit
     * @throws MediaUnavailableException if executor is shut down or admission capacity is reached
     */
    public DriveResourceReservation acquireReservation() throws MediaUnavailableException {
        while (true) {
            LifecycleState current = lifecycle.get();
            if (current.isShutdown()) {
                throw new MediaUnavailableException("Dịch vụ lưu trữ Google Drive đã ngừng hoạt động (shutdown)");
            }
            if (current.getTotal() >= cleanupQueueCapacity) {
                circuitBreaker.recordFailure();
                throw new MediaUnavailableException(
                        "Dung lượng tài nguyên Google Drive đồng thời đã đạt giới hạn tối đa (" + cleanupQueueCapacity + ")"
                );
            }
            LifecycleState next = new LifecycleState(current.getActive() + 1, current.getPending(), false);
            if (lifecycle.compareAndSet(current, next)) {
                break;
            }
        }

        return new DriveResourceReservation() {
            private final AtomicBoolean active = new AtomicBoolean(true);
            private final AtomicReference<AutoCloseable> delegateRef = new AtomicReference<>(null);
            private final AtomicBoolean closeFailed = new AtomicBoolean(false);

            @Override
            public boolean closeAsync(AutoCloseable delegate, String opName) {
                if (!active.compareAndSet(true, false)) {
                    return false;
                }
                if (delegate == null) {
                    decrementActiveAndCheckShutdown();
                    return true;
                }

                delegateRef.set(delegate);

                // Atomic transfer from active to pending: total budget remains constant
                while (true) {
                    LifecycleState cur = lifecycle.get();
                    LifecycleState next = new LifecycleState(cur.getActive() - 1, cur.getPending() + 1, cur.isShutdown());
                    if (lifecycle.compareAndSet(cur, next)) {
                        break;
                    }
                }

                try {
                    cleanupExecutor.execute(() -> {
                        activeCleanupWorkers.incrementAndGet();
                        try {
                            delegate.close();
                            // Physical disposal success: clear obligation from pending lane
                            decrementPendingAndCheckShutdown();
                            closeFailed.set(false);
                            clearRetainedFailedCleanup(delegate);
                        } catch (Throwable t) {
                            closeFailed.set(true);
                            recordFailedCleanup(delegate, opName, t, this);
                        } finally {
                            activeCleanupWorkers.decrementAndGet();
                        }
                    });
                    return true;
                } catch (RejectedExecutionException ree) {
                    // Revert permit transfer on rejection; caller retains ownership without blocking
                    while (true) {
                        LifecycleState cur = lifecycle.get();
                        LifecycleState next = new LifecycleState(cur.getActive() + 1, cur.getPending() - 1, cur.isShutdown());
                        if (lifecycle.compareAndSet(cur, next)) {
                            break;
                        }
                    }
                    active.set(true);
                    delegateRef.set(null);
                    return false;
                }
            }

            @Override
            public boolean transferToFailed(AutoCloseable delegate, String opName, Throwable cause) {
                if (!active.compareAndSet(true, false)) {
                    return false;
                }
                delegateRef.set(delegate);
                closeFailed.set(true);
                // Atomically transfer from active to pending exactly once
                while (true) {
                    LifecycleState cur = lifecycle.get();
                    LifecycleState next = new LifecycleState(cur.getActive() - 1, cur.getPending() + 1, cur.isShutdown());
                    if (lifecycle.compareAndSet(cur, next)) {
                        break;
                    }
                }
                recordFailedCleanup(delegate, opName, cause, this);
                return true;
            }

            @Override
            public boolean retryCleanup() {
                if (!closeFailed.get()) {
                    return false;
                }
                AutoCloseable del = delegateRef.get();
                if (del == null) {
                    return false;
                }
                return retryFailedCleanup(del);
            }

            @Override
            public void clearFailedCleanup() {
                closeFailed.set(false);
            }

            @Override
            public boolean hasFailedCleanup() {
                return closeFailed.get();
            }

            @Override
            public void release() {
                if (active.compareAndSet(true, false)) {
                    decrementActiveAndCheckShutdown();
                }
            }

            @Override
            public boolean isActive() {
                return active.get();
            }
        };
    }

    /**
     * Executes non-blocking asynchronous resource cleanup in the bounded worker pool or cleanup queue.
     * Prevents caller thread from blocking on kernel WinFsp close while accurately
     * accounting for physical kernel worker occupancy without falling back to synchronous close.
     *
     * @param resource the resource to close asynchronously
     * @param opName operation name for diagnostic tracking
     * @return true if accepted into cleanup lane, false if rejected or shut down
     */
    public boolean executeCleanupAsync(AutoCloseable resource, String opName) {
        if (resource == null) {
            return true;
        }

        if (cleanupExecutor.isShutdown()) {
            return false;
        }

        // Reserve 1 unit of common lifecycle budget BEFORE accepting unreserved cleanup
        while (true) {
            LifecycleState cur = lifecycle.get();
            if (cleanupExecutor.isShutdown()) {
                return false;
            }
            if (cur.getTotal() >= cleanupQueueCapacity) {
                return false;
            }
            LifecycleState next = new LifecycleState(cur.getActive(), cur.getPending() + 1, cur.isShutdown());
            if (lifecycle.compareAndSet(cur, next)) {
                break;
            }
        }

        // Try main worker pool first if available
        boolean submittedToMain = false;
        int current = actualOutstandingWorkers.incrementAndGet();
        if (current <= maxWorkers) {
            try {
                executor.execute(() -> {
                    try {
                        resource.close();
                        // Physical close succeeded: release the reserved pending slot
                        decrementPendingAndCheckShutdown();
                    } catch (Throwable t) {
                        // Failed: pending remains charged!
                        recordFailedCleanup(resource, opName, t, null);
                    } finally {
                        actualOutstandingWorkers.decrementAndGet();
                    }
                });
                submittedToMain = true;
            } catch (RejectedExecutionException e) {
                actualOutstandingWorkers.decrementAndGet();
            }
        } else {
            actualOutstandingWorkers.decrementAndGet();
        }

        if (!submittedToMain) {
            // Main pool saturated or rejected. Route to dedicated cleanupExecutor tier
            try {
                cleanupExecutor.execute(() -> {
                    activeCleanupWorkers.incrementAndGet();
                    try {
                        resource.close();
                        // Physical close succeeded: release the reserved pending slot
                        decrementPendingAndCheckShutdown();
                    } catch (Throwable t) {
                        // Failed: pending remains charged!
                        recordFailedCleanup(resource, opName, t, null);
                    } finally {
                        activeCleanupWorkers.decrementAndGet();
                    }
                });
            } catch (Throwable t) {
                // Both tiers rejected: release the reserved pending budget
                decrementPendingAndCheckShutdown();
                return false;
            }
        }
        return true;
    }

    public boolean executeCleanupAsync(AutoCloseable resource) {
        return executeCleanupAsync(resource, "cleanup");
    }

    private void recordFailedCleanup(AutoCloseable resource, String opName, Throwable cause, DriveResourceReservation reservation) {
        recordFailedCleanup(resource, opName, cause, reservation, true);
    }

    private void recordFailedCleanup(AutoCloseable resource, String opName, Throwable cause, DriveResourceReservation reservation, boolean chargesPending) {
        if (resource != null) {
            RetainedFailedCleanup existing = retainedFailedCleanups.get(resource);
            if (existing != null) {
                existing.updateFailure(cause);
            } else {
                if (retainedFailedCleanups.size() >= cleanupQueueCapacity) {
                    if (chargesPending) {
                        decrementPendingAndCheckShutdown();
                    }
                    circuitBreaker.recordFailure();
                    return;
                }
                retainedFailedCleanups.put(resource, new RetainedFailedCleanup(resource, opName, cause, reservation, chargesPending));
                failedCleanupObligations.incrementAndGet();
                circuitBreaker.recordFailure();
            }
        }
    }

    private void clearRetainedFailedCleanup(AutoCloseable resource) {
        if (resource != null) {
            RetainedFailedCleanup removed = retainedFailedCleanups.remove(resource);
            if (removed != null) {
                failedCleanupObligations.decrementAndGet();
                if (removed.chargesPending()) {
                    decrementPendingAndCheckShutdown();
                }
                DriveResourceReservation res = removed.getReservation();
                if (res != null) {
                    res.clearFailedCleanup();
                }
            }
        }
    }

    public boolean hasFailedCleanup(AutoCloseable resource) {
        return resource != null && retainedFailedCleanups.containsKey(resource);
    }

    /**
     * Retries asynchronous cleanup for a specific failed resource.
     * Non-blocking: submits retry task to cleanup executor and returns immediately (<1ms).
     *
     * @param resource the failed resource to retry
     * @return true if accepted into cleanup lane for retry, false if not found or rejected
     */
    public boolean retryFailedCleanup(AutoCloseable resource) {
        if (resource == null) {
            return false;
        }
        RetainedFailedCleanup record = retainedFailedCleanups.get(resource);
        if (record == null) {
            return false;
        }
        return submitRetryTask(record);
    }

    /**
     * Retries asynchronous cleanup for all currently retained failed resources.
     * Non-blocking: submits retry tasks to cleanup executor and returns count of submitted tasks.
     *
     * @return number of failed resources successfully submitted for retry
     */
    public int retryFailedCleanups() {
        int submitted = 0;
        for (RetainedFailedCleanup record : retainedFailedCleanups.values()) {
            if (submitRetryTask(record)) {
                submitted++;
            }
        }
        return submitted;
    }

    private boolean submitRetryTask(RetainedFailedCleanup record) {
        if (!record.markInFlight()) {
            return false;
        }

        AutoCloseable resource = record.getResource();
        try {
            cleanupExecutor.execute(() -> {
                activeCleanupWorkers.incrementAndGet();
                try {
                    resource.close();
                    clearRetainedFailedCleanup(resource);
                } catch (Throwable t) {
                    circuitBreaker.recordFailure();
                    record.updateFailure(t);
                } finally {
                    activeCleanupWorkers.decrementAndGet();
                }
            });
            return true;
        } catch (RejectedExecutionException ree) {
            record.clearInFlight();
            return false;
        }
    }

    public List<AutoCloseable> getRetainedFailedResources() {
        return List.copyOf(retainedFailedCleanups.keySet());
    }

    public List<RetainedFailedCleanup> getRetainedFailedRecords() {
        return List.copyOf(retainedFailedCleanups.values());
    }

    public int getActualOutstandingWorkers() {
        return actualOutstandingWorkers.get();
    }

    public int getActiveCleanupWorkers() {
        return activeCleanupWorkers.get();
    }

    public int getPendingCleanupObligations() {
        return lifecycle.get().getPending();
    }

    public int getActiveResourceReservations() {
        return lifecycle.get().getActive();
    }

    public int getFailedCleanupObligations() {
        return failedCleanupObligations.get();
    }

    public int getCleanupQueueCapacity() {
        return cleanupQueueCapacity;
    }

    public int getMaxWorkers() {
        return maxWorkers;
    }

    public DriveCircuitBreaker getCircuitBreaker() {
        return circuitBreaker;
    }

    public long getMetadataTimeoutMs() {
        return metadataTimeoutMs;
    }

    public long getReadTimeoutMs() {
        return readTimeoutMs;
    }

    private void decrementActiveAndCheckShutdown() {
        while (true) {
            LifecycleState cur = lifecycle.get();
            int newActive = Math.max(0, cur.getActive() - 1);
            LifecycleState next = new LifecycleState(newActive, cur.getPending(), cur.isShutdown());
            if (lifecycle.compareAndSet(cur, next)) {
                if (next.isShutdown() && next.getTotal() == 0 && retainedFailedCleanups.isEmpty()) {
                    cleanupExecutor.shutdown();
                }
                break;
            }
        }
    }

    private void decrementPendingAndCheckShutdown() {
        while (true) {
            LifecycleState cur = lifecycle.get();
            int newPending = Math.max(0, cur.getPending() - 1);
            LifecycleState next = new LifecycleState(cur.getActive(), newPending, cur.isShutdown());
            if (lifecycle.compareAndSet(cur, next)) {
                if (next.isShutdown() && next.getTotal() == 0 && retainedFailedCleanups.isEmpty()) {
                    cleanupExecutor.shutdown();
                }
                break;
            }
        }
    }

    public boolean isShutdown() {
        return lifecycle.get().isShutdown() || executor.isShutdown();
    }

    public void shutdown() {
        while (true) {
            LifecycleState cur = lifecycle.get();
            LifecycleState next = new LifecycleState(cur.getActive(), cur.getPending(), true);
            if (lifecycle.compareAndSet(cur, next)) {
                executor.shutdownNow();
                if (next.getTotal() == 0 && retainedFailedCleanups.isEmpty()) {
                    cleanupExecutor.shutdown();
                }
                break;
            }
        }
    }
}
