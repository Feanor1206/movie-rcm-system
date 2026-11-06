package com.dippie.moviercm.service.storage;

import java.io.Closeable;

/**
 * Represents an admission reservation permit for Google Drive resources.
 * Ensures strict bounds on total active open resources and pending cleanup obligations
 * to guarantee no resource is abandoned under cleanup queue pressure.
 */
public interface DriveResourceReservation extends AutoCloseable, Closeable {

    /**
     * Atomically transfers this reservation permit into a pending cleanup obligation
     * and submits delegate closure to the cleanup lane.
     *
     * @param delegate the resource to close asynchronously
     * @param opName operation name for diagnostic tracking
     * @return true if accepted and transferred to cleanup obligation, false if reservation was already inactive or executor shut down
     */
    boolean closeAsync(AutoCloseable delegate, String opName);

    /**
     * Convenience overload for closeAsync with default "cleanup" operation name.
     *
     * @param delegate the resource to close asynchronously
     * @return true if accepted and transferred, false otherwise
     */
    default boolean closeAsync(AutoCloseable delegate) {
        return closeAsync(delegate, "cleanup");
    }

    /**
     * Retries asynchronous cleanup of the delegate associated with this reservation
     * if a previous close attempt failed.
     * Guaranteed non-blocking: submits retry task to cleanup lane and returns immediately (<1ms).
     *
     * @return true if accepted into cleanup lane for retry; false if not in failed state or executor shut down
     */
    default boolean retryCleanup() {
        return false;
    }

    /**
     * Alias for retryCleanup().
     *
     * @return true if accepted into cleanup lane for retry; false if not in failed state or executor shut down
     */
    default boolean retryFailedClose() {
        return retryCleanup();
    }

    /**
     * Returns true if this reservation has a failed close obligation awaiting retry.
     *
     * @return true if a close attempt on this reservation failed and is retained for retry
     */
    default boolean hasFailedCleanup() {
        return false;
    }

    /**
     * Clears any retained failure state for this reservation after successful disposal.
     */
    default void clearFailedCleanup() {
    }

    /**
     * Atomically transfers this active reservation into a pending failed obligation
     * upon native close failure without double-decrementing active capacity.
     *
     * @param delegate the resource that failed to close
     * @param opName operation name
     * @param cause failure cause
     * @return true if transferred, false if already inactive
     */
    default boolean transferToFailed(AutoCloseable delegate, String opName, Throwable cause) {
        return false;
    }

    /**
     * Releases this reservation permit without queuing a close task.
     * Decrements the active resource reservations counter if still active.
     */
    void release();

    /**
     * Returns true if this reservation is still active (not yet closed or released).
     *
     * @return true if active
     */
    boolean isActive();

    /**
     * AutoCloseable and Closeable support: releases the reservation permit if not already closed or released.
     */
    @Override
    default void close() {
        release();
    }
}
