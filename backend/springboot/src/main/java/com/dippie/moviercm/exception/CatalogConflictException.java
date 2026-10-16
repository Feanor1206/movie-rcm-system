package com.dippie.moviercm.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.CONFLICT)
public class CatalogConflictException extends RuntimeException {
    public CatalogConflictException(String message) {
        super(message);
    }
}
