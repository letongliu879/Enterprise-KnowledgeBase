package com.realityrag.access.support;

import java.util.LinkedHashMap;
import java.util.Map;

public final class TestAgentAuthFactory {
    public static final String API_KEY = "rr-agent-platform-dev";
    public static final String TENANT_ID = "tnt_default";
    public static final String PLATFORM_ID = "enterprise_platform";
    public static final String AGENT_INSTANCE_ID = "agent-instance-001";

    private TestAgentAuthFactory() {}

    public static Map<String, String> headers(String method, String path, String query) {
        return headers(method, path, query, AGENT_INSTANCE_ID);
    }

    public static Map<String, String> headers(String method, String path, String query, String agentInstanceId) {
        LinkedHashMap<String, String> headers = new LinkedHashMap<>();
        headers.put("X-API-Key", API_KEY);
        headers.put("X-Agent-Instance-Id", agentInstanceId);
        return headers;
    }
}
