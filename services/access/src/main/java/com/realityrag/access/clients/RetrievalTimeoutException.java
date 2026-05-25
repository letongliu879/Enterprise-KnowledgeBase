package com.realityrag.access.clients;

public class RetrievalTimeoutException extends RuntimeException {
    public RetrievalTimeoutException(String message, Throwable cause) {
        super(message, cause);
    }
}
