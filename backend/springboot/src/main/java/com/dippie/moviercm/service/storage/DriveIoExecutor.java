package com.dippie.moviercm.service.storage;

import com.dippie.moviercm.exception.MediaNotFoundException;
import com.dippie.moviercm.exception.MediaUnavailableException;
import com.dippie.moviercm.exception.SecurityPathTraversalException;

import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Executes Drive IO operations with finite deadlines, bounded worker pool,
 * accurate physical worker accounting, and circuit breaking.
 */
public class DriveIoExecutor {

    private final long metadataTimeoutMs;
    private final long readTimeoutMs;
    private final int maxWorkers;
    private final AtomicInteger actualOutstandingWorkers = new AtomicInteger(0);
    private final DriveCircuitBreaker circuitBreaker;
    private final ExecutorService executor;

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

        // 3. Submit task to bounded worker pool
        Future<T> future;
        try {
            future = executor.submit(() -> {
                try {
                    return task.call();
                } finally {
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
            future.cancel(true);
            circuitBreaker.recordFailure();
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
            throw new MediaUnavailableException("Lỗi IO khi truy xuất Google Drive: " + cause.getMessage());
        } catch (InterruptedException e) {
            future.cancel(true);
            Thread.currentThread().interrupt();
            throw new MediaUnavailableException("Thao tác truy xuất Google Drive bị gián đoạn");
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

    public void shutdown() {
        executor.shutdownNow();
    }
}
