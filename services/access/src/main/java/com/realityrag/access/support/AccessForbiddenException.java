package com.realityrag.access.support;

import org.springframework.http.HttpStatus;

public class AccessForbiddenException extends AccessException {
    public AccessForbiddenException(String message) {
        super("ACC_FORBIDDEN", HttpStatus.FORBIDDEN, message);
    }
}
