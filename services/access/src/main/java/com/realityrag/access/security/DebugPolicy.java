package com.realityrag.access.security;

import com.realityrag.access.support.AccessException;
import org.springframework.stereotype.Component;

@Component
public class DebugPolicy {
    public String resolve(String requestedLevel, AccessRequestContext context) {
        String normalized = requestedLevel == null || requestedLevel.isBlank() ? "none" : requestedLevel;
        if (!normalized.equals("none") && !normalized.equals("basic") && !normalized.equals("full")) {
            throw new AccessException.InvalidRequest("Unsupported debug level: " + normalized);
        }
        if (normalized.equals("none")) {
            return "none";
        }
        if (normalized.equals("basic")) {
            return context.debugPermission() ? "basic" : "none";
        }
        if (!context.debugPermission()) {
            throw new AccessException.Forbidden("Full debug is not allowed for this agent integration");
        }
        return "full";
    }
}
