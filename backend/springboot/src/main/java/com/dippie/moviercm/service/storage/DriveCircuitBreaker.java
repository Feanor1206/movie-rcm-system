package com.dippie.moviercm.service.storage;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Circuit breaker for Google Drive storage operations to prevent cascade failures
 * and resource starvation when the underlying mount or network stalls.
 */
public class DriveCircuitBreaker {

    public enum State {
        CLOSED,
        OPEN,
        HALF_OPEN
    }

    private final int failureThreshold;
    private final long cooldownMs;

    private volatile State state = State.CLOSED;
    private final AtomicInteger consecutiveFailures = new AtomicInteger(0);
    private final AtomicLong lastOpenedTimestamp = new AtomicLong(0);

    public DriveCircuitBreaker(int failureThreshold, long cooldownMs) {
        this.failureThreshold = failureThreshold > 0 ? failureThreshold : 5;
        this.cooldownMs = cooldownMs > 0 ? cooldownMs : 10000;
    }

    public DriveCircuitBreaker() {
        this(5, 10000);
    }

    public synchronized boolean allowExecution() {
        if (state == State.CLOSED) {
            return true;
        }

        if (state == State.OPEN) {
            long elapsed = System.currentTimeMillis() - lastOpenedTimestamp.get();
            if (elapsed >= cooldownMs) {
                state = State.HALF_OPEN;
                return true;
            }
            return false;
        }

        // HALF_OPEN: allow trial request
        return true;
    }

    public synchronized void recordSuccess() {
        consecutiveFailures.set(0);
        state = State.CLOSED;
    }

    public synchronized void recordFailure() {
        int failures = consecutiveFailures.incrementAndGet();
        if (failures >= failureThreshold || state == State.HALF_OPEN) {
            state = State.OPEN;
            lastOpenedTimestamp.set(System.currentTimeMillis());
        }
    }

    public State getState() {
        if (state == State.OPEN) {
            long elapsed = System.currentTimeMillis() - lastOpenedTimestamp.get();
            if (elapsed >= cooldownMs) {
                return State.HALF_OPEN;
            }
        }
        return state;
    }

    public boolean isOpen() {
        return getState() == State.OPEN;
    }

    public int getConsecutiveFailures() {
        return consecutiveFailures.get();
    }

    public int getFailureThreshold() {
        return failureThreshold;
    }

    public long getCooldownMs() {
        return cooldownMs;
    }

    public synchronized void reset() {
        consecutiveFailures.set(0);
        lastOpenedTimestamp.set(0);
        state = State.CLOSED;
    }

    public synchronized void trip() {
        consecutiveFailures.set(failureThreshold);
        lastOpenedTimestamp.set(System.currentTimeMillis());
        state = State.OPEN;
    }
}
