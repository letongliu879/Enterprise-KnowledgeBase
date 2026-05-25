package com.realityrag.access.support;

import org.springframework.http.HttpStatus;

public abstract class AccessException extends RuntimeException {
    private final String errorCode;
    private final HttpStatus status;

    protected AccessException(String errorCode, HttpStatus status, String message) {
        super(message);
        this.errorCode = errorCode;
        this.status = status;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public HttpStatus getStatus() {
        return status;
    }
}
