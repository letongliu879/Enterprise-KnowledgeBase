package com.realityrag.access.security;

import org.springframework.stereotype.Component;

@Component
public class RateLimitGuard {
    public void check(AccessRequestContext context) {
        // Placeholder seam for future tenant / api_key / agent_instance rate limiting.
    }
}
