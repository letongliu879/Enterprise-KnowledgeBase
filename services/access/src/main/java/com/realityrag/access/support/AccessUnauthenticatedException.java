package com.realityrag.access.support;

import org.springframework.http.HttpStatus;

public class AccessUnauthenticatedException extends AccessException {
    public AccessUnauthenticatedException(String message) {
        super("ACC_UNAUTHENTICATED", HttpStatus.UNAUTHORIZED, message);
    }
}
