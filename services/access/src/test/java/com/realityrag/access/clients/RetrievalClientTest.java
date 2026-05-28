package com.realityrag.access.clients;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;

import com.realityrag.access.contracts.InternalPrincipal;
import com.realityrag.access.contracts.InternalRetrieveRequest;
import com.realityrag.access.support.AccessException;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class RetrievalClientTest {
    @Test
    void retrieveReturnsKnowledgeContext() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.baseUrl("http://retrieval").build();
        RetrievalClient client = new RetrievalClient(restClient);

        server.expect(requestTo("http://retrieval/internal/retrieve"))
            .andExpect(method(HttpMethod.POST))
            .andExpect(header("X-Trace-Id", "trc_1"))
            .andExpect(header("X-Query-Id", "qry_1"))
            .andRespond(withSuccess("""
                {
                  "query_id":"qry_1",
                  "principal_context":{"tenant_id":"t1"},
                  "index_version_used":["idx_v1"],
                  "collection_plans_used":[],
                  "evidence_items":[
                    {
                      "collection_id":"c1",
                      "doc_id":"doc_1",
                      "evidence_id":"chunk_1",
                      "document_index_revision_id":"rev_1",
                      "content":"test content",
                      "section_path":["Section A"],
                      "page_spans":[{"page_from":1,"page_to":2}],
                      "score":0.95,
                      "source_stage":"hybrid",
                      "why_selected":"bm25+vector"
                    }
                  ],
                  "grouped_sources":[],
                  "citations":[],
                  "token_budget_used":128,
                  "retrieval_debug":{}
                }
                """, MediaType.APPLICATION_JSON));

        var response = client.retrieve(request());
        assertEquals("qry_1", response.queryId());
        assertEquals(1, response.resultChunks().size());
        var chunk = response.resultChunks().get(0);
        assertEquals("doc_1", chunk.finalDocId());
        assertEquals("chunk_1", chunk.chunkId());
        assertEquals("test content", chunk.displayText());
        assertEquals(0.95, chunk.score());
        server.verify();
    }

    @Test
    void retrieveMapsDownstreamFailure() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.baseUrl("http://retrieval").build();
        RetrievalClient client = new RetrievalClient(restClient);

        server.expect(requestTo("http://retrieval/internal/retrieve"))
            .andRespond(withStatus(HttpStatus.INTERNAL_SERVER_ERROR));

        assertThrows(AccessException.RetrievalUnavailable.class, () -> client.retrieve(request()));
        server.verify();
    }

    @Test
    void healthStatusReflectsDownstreamResponse() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.baseUrl("http://retrieval").build();
        RetrievalClient client = new RetrievalClient(restClient);

        server.expect(requestTo("http://retrieval/health"))
            .andExpect(method(HttpMethod.GET))
            .andRespond(withSuccess("""
                {"service":"retrieval","status":"ok"}
                """, MediaType.APPLICATION_JSON));

        assertEquals("ok", client.healthStatus());
        server.verify();
    }

    @Test
    void retrievalProfileExistsUsesInternalEndpoint() {
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.baseUrl("http://retrieval").build();
        RetrievalClient client = new RetrievalClient(restClient);

        server.expect(requestTo("http://retrieval/internal/retrieval-profiles/ret_default"))
            .andExpect(method(HttpMethod.GET))
            .andRespond(withSuccess("""
                {
                  "profile_id":"ret_default",
                  "collection_id":"c1",
                  "profile_version":1,
                  "profile_hash":"hash1",
                  "bm25_weight":1.0,
                  "vector_weight":1.0,
                  "candidate_top_k":20,
                  "similarity_threshold":0.2,
                  "rerank_enabled":true,
                  "rerank_model":"reranker-v1",
                  "fail_policy":"closed",
                  "expansion_policy":{},
                  "pack_budget":4096,
                  "updated_at":"2026-05-24T00:00:00Z",
                  "updated_by":"system"
                }
                """, MediaType.APPLICATION_JSON));

        assertEquals(true, client.retrievalProfileExists("ret_default"));
        server.verify();
    }

    private InternalRetrieveRequest request() {
        return new InternalRetrieveRequest(
            "qry_1",
            "trc_1",
            new InternalPrincipal("principal_a", java.util.List.of("admin"), java.util.List.of(), java.util.Map.of()),
            java.util.List.of("c1"),
            "query",
            "en",
            java.util.List.of("zh"),
            true,
            java.util.Map.of("mode", "manual"),
            "ret_default",
            java.util.Map.of(),
            false,
            128,
            "none"
        );
    }
}
