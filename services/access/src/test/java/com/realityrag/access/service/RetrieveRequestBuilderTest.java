package com.realityrag.access.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.security.AccessRequestContext;
import com.realityrag.access.support.AccessException;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class RetrieveRequestBuilderTest {
    private final RetrieveRequestBuilder builder = new RetrieveRequestBuilder();

    @Test
    void builderMapsAndNormalizesRequest() {
        var external = new ExternalRetrieveRequest(
            " query text ",
            List.of("c1", "c2", "c1"),
            Map.of("tag", "finance"),
            "en",
            List.of("zh", "ja"),
            true,
            Map.of("mode", "manual"),
            "ret_default",
            null,
            2048,
            "basic"
        );
        var context = new AccessRequestContext(
            "api_key_a",
            "tnt_default",
            "kb_assistant",
            "agent_instance_1",
            List.of("c1", "c2"),
            List.of("admin"),
            Map.of("region", "cn"),
            true,
            "rest",
            4096
        );

        var internal = builder.build(external, context, "ret_default", "basic", "qry_1", "trc_1");

        assertEquals("qry_1", internal.queryId());
        assertEquals("trc_1", internal.traceId());
        assertEquals("kb_assistant:agent_instance_1", internal.principal().principalId());
        assertEquals(List.of("c1", "c2"), internal.collectionScope());
        assertEquals("query text", internal.queryText());
        assertEquals("en", internal.language());
        assertEquals(List.of("zh", "ja"), internal.crossLanguages());
        assertEquals(true, internal.keyword());
        assertEquals(Map.of("mode", "manual"), internal.metaDataFilter());
        assertEquals("ret_default", internal.retrievalProfileId());
        assertEquals(Map.of("tag", "finance"), internal.filters());
        assertFalse(internal.includeDeprecated());
        assertEquals(2048, internal.maxContextTokens());
        assertEquals("basic", internal.debugLevel());
    }

    @Test
    void builderRejectsCollectionOutsideApiKeyScope() {
        var external = new ExternalRetrieveRequest(
            "query text",
            List.of("c1", "c3"),
            Map.of(),
            "en",
            List.of(),
            false,
            Map.of(),
            "ret_default",
            null,
            null,
            "none"
        );
        var context = new AccessRequestContext(
            "api_key_a",
            "tnt_default",
            "kb_assistant",
            "agent_instance_1",
            List.of("c1", "c2"),
            List.of("agent"),
            Map.of(),
            false,
            "rest",
            4096
        );

        assertThrows(
            AccessException.Forbidden.class,
            () -> builder.build(external, context, "ret_default", "none", "qry_1", "trc_1")
        );
    }
}
