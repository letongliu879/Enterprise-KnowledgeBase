package com.realityrag.access.api;

import com.realityrag.access.contracts.AccessErrorResponse;
import com.realityrag.access.support.AccessException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class AccessExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(AccessExceptionHandler.class);
    @ExceptionHandler(AccessException.class)
    public ResponseEntity<AccessErrorResponse> handleAccessException(AccessException error) {
        return ResponseEntity.status(error.getStatus())
            .body(new AccessErrorResponse(error.getErrorCode(), error.getMessage()));
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, HttpMessageNotReadableException.class})
    public ResponseEntity<AccessErrorResponse> handleInvalidRequest(Exception error) {
        String message;
        if (error instanceof MethodArgumentNotValidException m) {
            message = m.getBindingResult().getFieldErrors().stream()
                .findFirst()
                .map(FieldError::getDefaultMessage)
                .orElse("Request validation failed");
        } else {
            message = "Malformed request body";
        }
        return ResponseEntity.badRequest()
            .body(new AccessErrorResponse("ACC_INVALID_REQUEST", message));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<AccessErrorResponse> handleUnexpected(Exception error) {
        log.error("Unhandled exception", error);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new AccessErrorResponse("ACC_INTERNAL_ERROR", "Unexpected access service error"));
    }
}
