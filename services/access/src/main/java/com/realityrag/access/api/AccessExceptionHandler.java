package com.realityrag.access.api;

import com.realityrag.access.clients.RetrievalTimeoutException;
import com.realityrag.access.clients.RetrievalUnavailableException;
import com.realityrag.access.contracts.AccessErrorResponse;
import com.realityrag.access.support.AccessException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class AccessExceptionHandler {
    @ExceptionHandler(AccessException.class)
    public ResponseEntity<AccessErrorResponse> handleAccessException(AccessException error) {
        return ResponseEntity.status(error.getStatus())
            .body(new AccessErrorResponse(error.getErrorCode(), error.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<AccessErrorResponse> handleValidation(MethodArgumentNotValidException error) {
        String message = error.getBindingResult().getFieldErrors().stream()
            .findFirst()
            .map(FieldError::getDefaultMessage)
            .orElse("Request validation failed");
        return ResponseEntity.badRequest()
            .body(new AccessErrorResponse("ACC_INVALID_REQUEST", message));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<AccessErrorResponse> handleUnreadableBody(HttpMessageNotReadableException error) {
        return ResponseEntity.badRequest()
            .body(new AccessErrorResponse("ACC_INVALID_REQUEST", "Malformed request body"));
    }

    @ExceptionHandler(RetrievalTimeoutException.class)
    public ResponseEntity<AccessErrorResponse> handleRetrievalTimeout(RetrievalTimeoutException error) {
        return ResponseEntity.status(HttpStatus.GATEWAY_TIMEOUT)
            .body(new AccessErrorResponse("ACC_RETRIEVAL_TIMEOUT", error.getMessage()));
    }

    @ExceptionHandler(RetrievalUnavailableException.class)
    public ResponseEntity<AccessErrorResponse> handleRetrievalUnavailable(RetrievalUnavailableException error) {
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
            .body(new AccessErrorResponse("ACC_RETRIEVAL_UNAVAILABLE", error.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<AccessErrorResponse> handleUnexpected(Exception error) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new AccessErrorResponse("ACC_INTERNAL_ERROR", "Unexpected access service error"));
    }
}
