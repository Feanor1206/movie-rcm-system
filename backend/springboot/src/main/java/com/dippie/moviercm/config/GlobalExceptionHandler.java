package com.dippie.moviercm.config;

import com.dippie.moviercm.dto.ApiResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ApiResponse<Void>> handleIllegalArgument(IllegalArgumentException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.error(ex.getMessage()));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<ApiResponse<Void>> handleIllegalState(IllegalStateException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(ApiResponse.error(ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidationException(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldError() != null
                ? ex.getBindingResult().getFieldError().getDefaultMessage()
                : "Dữ liệu yêu cầu không hợp lệ";
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.error(message));
    }

    @ExceptionHandler(com.dippie.moviercm.exception.MediaNotFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleMediaNotFound(com.dippie.moviercm.exception.MediaNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.error(ex.getMessage()));
    }

    @ExceptionHandler(com.dippie.moviercm.exception.MediaUnavailableException.class)
    public ResponseEntity<ApiResponse<Void>> handleMediaUnavailable(com.dippie.moviercm.exception.MediaUnavailableException ex) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(ApiResponse.error(ex.getMessage()));
    }

    @ExceptionHandler(com.dippie.moviercm.exception.SecurityPathTraversalException.class)
    public ResponseEntity<ApiResponse<Void>> handlePathTraversal(com.dippie.moviercm.exception.SecurityPathTraversalException ex) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST)
                .body(ApiResponse.error(ex.getMessage()));
    }

    @ExceptionHandler(com.dippie.moviercm.exception.InvalidMediaRangeException.class)
    public ResponseEntity<Void> handleInvalidRange(com.dippie.moviercm.exception.InvalidMediaRangeException ex) {
        return ResponseEntity.status(HttpStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                .header(org.springframework.http.HttpHeaders.CONTENT_RANGE, "bytes */" + ex.getTotalBytes())
                .build();
    }
}

