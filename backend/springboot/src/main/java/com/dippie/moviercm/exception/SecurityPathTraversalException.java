package com.dippie.moviercm.exception;

public class SecurityPathTraversalException extends RuntimeException {
    public SecurityPathTraversalException(String message) {
        super(message);
    }
}
