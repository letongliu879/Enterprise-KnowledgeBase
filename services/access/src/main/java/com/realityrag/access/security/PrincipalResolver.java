package com.realityrag.access.security;

import com.realityrag.access.support.AccessUnauthenticatedException;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Arrays;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public class PrincipalResolver {
    public String resolvePrincipalId(HttpServletRequest request) {
        String principalId = request.getHeader("X-Principal-Id");
        if (principalId == null || principalId.isBlank()) {
            throw new AccessUnauthenticatedException("Missing X-Principal-Id");
        }
        return principalId.trim();
    }

    public List<String> resolveRoles(HttpServletRequest request) {
        return splitHeader(request.getHeader("X-Principal-Roles"));
    }

    public List<String> resolveGroups(HttpServletRequest request) {
        return splitHeader(request.getHeader("X-Principal-Groups"));
    }

    private List<String> splitHeader(String value) {
        if (value == null || value.isBlank()) {
            return List.of();
        }
        return Arrays.stream(value.split(","))
            .map(String::trim)
            .filter(item -> !item.isBlank())
            .distinct()
            .toList();
    }
}
