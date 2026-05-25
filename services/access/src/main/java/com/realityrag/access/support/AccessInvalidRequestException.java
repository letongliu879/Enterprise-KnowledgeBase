package com.realityrag.access.support;

import org.springframework.http.HttpStatus;

public class AccessInvalidRequestException extends AccessException {
    public AccessInvalidRequestException(String message) {
        super("ACC_INVALID_REQUEST", HttpStatus.BAD_REQUEST, message);
    }
}
