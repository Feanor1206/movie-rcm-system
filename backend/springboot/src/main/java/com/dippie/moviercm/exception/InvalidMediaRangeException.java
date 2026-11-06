package com.dippie.moviercm.exception;

public class InvalidMediaRangeException extends RuntimeException {
    private final long totalBytes;

    public InvalidMediaRangeException(String message, long totalBytes) {
        super(message);
        this.totalBytes = totalBytes;
    }

    public long getTotalBytes() {
        return totalBytes;
    }
}
