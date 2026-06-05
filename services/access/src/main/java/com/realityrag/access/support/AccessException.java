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

    protected AccessException(String errorCode, HttpStatus status, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
        this.status = status;
    }

    public String getErrorCode() {
        return errorCode;
    }

    public HttpStatus getStatus() {
        return status;
    }

    public static final class Forbidden extends AccessException {
        public Forbidden(String message) {
            super("ACC_FORBIDDEN", HttpStatus.FORBIDDEN, message);
        }
    }

    public static final class InvalidRequest extends AccessException {
        public InvalidRequest(String message) {
            super("ACC_INVALID_REQUEST", HttpStatus.BAD_REQUEST, message);
        }
    }

    public static final class Unauthenticated extends AccessException {
        public Unauthenticated(String message) {
            super("ACC_UNAUTHENTICATED", HttpStatus.UNAUTHORIZED, message);
        }
    }

    public static final class RegistryUnavailable extends AccessException {
        public RegistryUnavailable(String message) {
            super("ACC_API_KEY_REGISTRY_UNAVAILABLE", HttpStatus.SERVICE_UNAVAILABLE, message);
        }

        public RegistryUnavailable(String message, Throwable cause) {
            super("ACC_API_KEY_REGISTRY_UNAVAILABLE", HttpStatus.SERVICE_UNAVAILABLE, message, cause);
        }
    }

    public static final class RetrievalTimeout extends AccessException {
        public RetrievalTimeout(String message, Throwable cause) {
            super("ACC_RETRIEVAL_TIMEOUT", HttpStatus.GATEWAY_TIMEOUT, message, cause);
        }
    }

    public static final class RetrievalUnavailable extends AccessException {
        public RetrievalUnavailable(String message, Throwable cause) {
            super("ACC_RETRIEVAL_UNAVAILABLE", HttpStatus.SERVICE_UNAVAILABLE, message, cause);
        }
    }
}
