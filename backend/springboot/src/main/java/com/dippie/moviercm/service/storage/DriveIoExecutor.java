package com.dippie.moviercm.service.storage;

import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.exception.SecurityPathTraversalException;

import java.io.IOException;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Executes Drive IO operations with finite deadlines, bounded worker pool,
 * accurate physical worker accounting, circuit breaking, and resource ownership handshakes.
 */
public class DriveIoExecutor {

    public enum OpenState {
        PENDING,
        CALLER_ACQUIRED,
        TIMED_OUT
    }

    private final long metadataTimeoutMs;
    private final long readTimeoutMs;
    private final int maxWorkers;
    private final AtomicInteger actualOutstandingWorkers = new AtomicInteger(0);
    private final DriveCircuitBreaker circuitBreaker;
    private final ExecutorService executor;
    private final ThreadPoolExecutor cleanupExecutor;

    public DriveIoExecutor(long metadataTimeoutMs,
                           long readTimeoutMs,
                           int maxWorkers,
                           DriveCircuitBreaker circuitBreaker) {
        this.metadataTimeoutMs = metadataTimeoutMs > 0 ? metadataTimeoutMs : 3000;
        this.readTimeoutMs = readTimeoutMs > 0 ? readTimeoutMs : 5000;
        this.maxWorkers = maxWorkers > 0 ? maxWorkers : 10;
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
                0,
                cleanupMaxThreads,
                60L,
                TimeUnit.SECONDS,
                new LinkedBlockingQueue<>(256),
                cleanupThreadFactory,
                new ThreadPoolExecutor.DiscardOldestPolicy()
        );
    }

    public DriveIoExecutor() {
        this(3000, 5000, 10, new DriveCircuitBreaker());
    }

    public <T> T executeMetadata(Callable<T> task) {
        return executeWithTimeout(task, metadataTimeoutMs, "metadata");
    }

    public <T> T executeRead(Callable<T> task) {
        return executeWithTimeout(task, readTimeoutMs, "read");
    }

    public <T> T executeWithTimeout(Callable<T> task, long timeoutMs, String operationDescription) {
        // 1. Circuit breaker gate
        if (!circuitBreaker.allowExecution()) {
            throw new MediaUnavailableException("Dịch vụ lưu trữ Google Drive tạm thời không khả dụng (Circuit Breaker OPEN)");
        }

        // 2. Strict worker capacity gate
        int current = actualOutstandingWorkers.incrementAndGet();
        if (current > maxWorkers) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            throw new MediaUnavailableException("Số lượng tác vụ truy xuất Google Drive đồng thời đã đạt giới hạn tối đa (" + maxWorkers + ")");
        }

        final AtomicBoolean callerTimedOut = new AtomicBoolean(false);
        final AtomicReference<T> resultRef = new AtomicReference<>(null);
        final AtomicBoolean closedDueToTimeout = new AtomicBoolean(false);

        // 3. Submit task to bounded worker pool
        Future<T> future;
        try {
            future = executor.submit(() -> {
                T result = null;
                try {
                    result = task.call();
                    resultRef.set(result);
                    if (callerTimedOut.get() && result instanceof AutoCloseable ac) {
                        closeResourceOnce(ac, closedDueToTimeout);
                    }
                    return result;
                } finally {
                    if (callerTimedOut.get()) {
                        T late = resultRef.get();
                        if (late instanceof AutoCloseable ac) {
                            closeResourceOnce(ac, closedDueToTimeout);
                        }
                    }
                    // Physical worker accounting: ONLY decrements when background thread actually finishes
                    actualOutstandingWorkers.decrementAndGet();
                }
            });
        } catch (RejectedExecutionException e) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            throw new MediaUnavailableException("Hàng đợi tác vụ truy xuất Google Drive đã đầy");
        }

        // 4. Await with finite deadline
        try {
            T result = future.get(timeoutMs, TimeUnit.MILLISECONDS);
            circuitBreaker.recordSuccess();
            return result;
        } catch (TimeoutException e) {
            callerTimedOut.set(true);
            future.cancel(true);
            circuitBreaker.recordFailure();
            T lateResult = resultRef.get();
            if (lateResult instanceof AutoCloseable ac) {
                executeCleanupAsync(() -> closeResourceOnce(ac, closedDueToTimeout), operationDescription);
            }
            // actualOutstandingWorkers is deliberately NOT decremented here because the kernel IO is still stuck
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive (" + operationDescription + ") vượt quá thời gian chờ (" + timeoutMs + "ms)");
        } catch (ExecutionException e) {
            Throwable cause = e.getCause();
            if (cause instanceof SecurityPathTraversalException || cause instanceof MediaNotFoundException) {
                // Client input errors do not trip the circuit breaker
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
            callerTimedOut.set(true);
            future.cancel(true);
            circuitBreaker.recordFailure();
            T lateResult = resultRef.get();
            if (lateResult instanceof AutoCloseable ac) {
                executeCleanupAsync(() -> closeResourceOnce(ac, closedDueToTimeout), operationDescription);
            }
            Thread.currentThread().interrupt();
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive bị gián đoạn");
        }
    }

    /**
     * Executes a resource opening task with strict ownership handshake, finite deadline,
     * and guaranteed exactly-once disposal on timeout/abandonment.
     */
    public <T extends AutoCloseable> T executeOpen(Callable<T> openTask, long timeoutMs, String opName) throws IOException {
        return executeOpen(openTask, timeoutMs, opName, null, null);
    }

    public <T extends AutoCloseable> T executeOpen(Callable<T> openTask,
                                                   long timeoutMs,
                                                   String opName,
                                                   AtomicReference<OpenState> externalStateRef,
                                                   AtomicReference<T> externalResourceRef) throws IOException {
        // 1. Circuit breaker gate
        if (!circuitBreaker.allowExecution()) {
            throw new MediaUnavailableException("Dịch vụ lưu trữ Google Drive tạm thời không khả dụng (Circuit Breaker OPEN)");
        }

        // 2. Strict worker capacity gate
        int current = actualOutstandingWorkers.incrementAndGet();
        if (current > maxWorkers) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            throw new MediaUnavailableException("Số lượng tác vụ truy xuất Google Drive đồng thời đã đạt giới hạn tối đa (" + maxWorkers + ")");
        }

        // 3. Ownership handshake state
        final AtomicReference<OpenState> state = externalStateRef != null ? externalStateRef : new AtomicReference<>(OpenState.PENDING);
        if (state.get() == null) {
            state.set(OpenState.PENDING);
        }
        final AtomicReference<T> resourceRef = externalResourceRef != null ? externalResourceRef : new AtomicReference<>(null);
        final AtomicBoolean closedDueToTimeout = new AtomicBoolean(false);

        // 4. Submit open task to bounded worker pool
        Future<T> future;
        try {
            future = executor.submit(() -> {
                T resource = null;
                try {
                    resource = openTask.call();
                    resourceRef.set(resource);
                    // Worker checks if caller timed out
                    if (state.get() == OpenState.TIMED_OUT) {
                        closeResourceOnce(resource, closedDueToTimeout);
                    }
                    return resource;
                } finally {
                    if (state.get() == OpenState.TIMED_OUT) {
                        T res = resourceRef.get();
                        if (res != null) {
                            closeResourceOnce(res, closedDueToTimeout);
                        }
                    }
                    // Physical worker accounting: ONLY decrements when open & late close physically finish
                    actualOutstandingWorkers.decrementAndGet();
                }
            });
        } catch (RejectedExecutionException e) {
            actualOutstandingWorkers.decrementAndGet();
            circuitBreaker.recordFailure();
            throw new MediaUnavailableException("Hàng đợi tác vụ truy xuất Google Drive đã đầy");
        }

        // 5. Await with finite deadline and handshake resolution
        try {
            T result = future.get(timeoutMs, TimeUnit.MILLISECONDS);
            if (state.compareAndSet(OpenState.PENDING, OpenState.CALLER_ACQUIRED)) {
                circuitBreaker.recordSuccess();
                return result;
            } else {
                // If caller had already timed out or abandoned ownership
                T res = resourceRef.get() != null ? resourceRef.get() : result;
                if (res != null) {
                    executeCleanupAsync(() -> closeResourceOnce(res, closedDueToTimeout), opName);
                }
                throw new MediaUnavailableException("Thao tác truy xuất Google Drive (" + opName + ") đã bị quá hạn");
            }
        } catch (TimeoutException e) {
            future.cancel(true);
            circuitBreaker.recordFailure();
            state.compareAndSet(OpenState.PENDING, OpenState.TIMED_OUT);
            T res = resourceRef.get();
            if (res != null) {
                executeCleanupAsync(() -> closeResourceOnce(res, closedDueToTimeout), opName);
            }
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive (" + opName + ") vượt quá thời gian chờ (" + timeoutMs + "ms)");
        } catch (InterruptedException e) {
            future.cancel(true);
            Thread.currentThread().interrupt();
            circuitBreaker.recordFailure();
            state.compareAndSet(OpenState.PENDING, OpenState.TIMED_OUT);
            T res = resourceRef.get();
            if (res != null) {
                executeCleanupAsync(() -> closeResourceOnce(res, closedDueToTimeout), opName);
            }
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive bị gián đoạn");
        } catch (ExecutionException e) {
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

    /**
     * Executes non-blocking asynchronous resource cleanup in the bounded worker pool or cleanup queue.
     * Prevents caller thread from blocking on kernel WinFsp close while accurately
     * accounting for physical kernel worker occupancy without falling back to synchronous close.
     */
    public void executeCleanupAsync(AutoCloseable resource, String opName) {
        if (resource == null) {
            return;
        }

        if (executor.isShutdown() || cleanupExecutor.isShutdown()) {
            return;
        }

        // 1. Try using main worker pool if capacity is available without saturation
        int current = actualOutstandingWorkers.incrementAndGet();
        if (current <= maxWorkers) {
            try {
                executor.submit(() -> {
                    try {
                        resource.close();
                    } catch (Throwable ignored) {
                    } finally {
                        actualOutstandingWorkers.decrementAndGet();
                    }
                });
                return;
            } catch (RejectedExecutionException e) {
                actualOutstandingWorkers.decrementAndGet();
            }
        } else {
            actualOutstandingWorkers.decrementAndGet();
        }

        // 2. Worker pool is saturated (at maxWorkers) or rejected. Route to bounded cleanup queue.
        // ABSOLUTELY NEVER throw exception and NEVER block caller!
        try {
            cleanupExecutor.submit(() -> {
                try {
                    resource.close();
                } catch (Throwable ignored) {
                }
            });
        } catch (Throwable ignored) {
            // Safe discard under total shutdown/queue full without blocking caller
        }
    }

    public void executeCleanupAsync(AutoCloseable resource) {
        executeCleanupAsync(resource, "cleanup");
    }

    private static <T extends AutoCloseable> void closeResourceOnce(T resource, AtomicBoolean closedGate) {
        if (resource != null && closedGate.compareAndSet(false, true)) {
            try {
                resource.close();
            } catch (Throwable ignored) {
            }
        }
    }

    public int getActualOutstandingWorkers() {
        return actualOutstandingWorkers.get();
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

    public boolean isShutdown() {
        return executor.isShutdown() || cleanupExecutor.isShutdown();
    }

    public void shutdown() {
        executor.shutdownNow();
        cleanupExecutor.shutdownNow();
    }
}
