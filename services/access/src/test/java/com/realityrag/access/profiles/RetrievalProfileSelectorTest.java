package com.realityrag.access.profiles;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.BDDMockito.given;

import com.realityrag.access.clients.RetrievalClient;
import com.realityrag.access.config.AccessProperties;
import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.support.AccessInvalidRequestException;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;

class RetrievalProfileSelectorTest {
    private final AccessProperties properties = new AccessProperties();
    private final RetrievalClient retrievalClient = Mockito.mock(RetrievalClient.class);
    private final RetrievalProfileSelector selector = new RetrievalProfileSelector(properties, retrievalClient);

    @Test
    void explicitProfileWins() {
        given(retrievalClient.retrievalProfileExists("ret_custom")).willReturn(true);
        var request = new ExternalRetrieveRequest(
            "q",
            List.of("c1"),
            Map.of(),
            null,
            List.of(),
            false,
            Map.of(),
            "ret_custom",
            null,
            1000,
            "none"
        );
        assertEquals("ret_custom", selector.select(request));
    }

    @Test
    void deprecatedAliasFallbackWorks() {
        given(retrievalClient.retrievalProfileExists("ret_alias")).willReturn(true);
        var request = new ExternalRetrieveRequest(
            "q",
            List.of("c1"),
            Map.of(),
            null,
            List.of(),
            false,
            Map.of(),
            null,
            "ret_alias",
            1000,
            "none"
        );
        assertEquals("ret_alias", selector.select(request));
    }

    @Test
    void conflictingProfilesFail() {
        var request = new ExternalRetrieveRequest(
            "q",
            List.of("c1"),
            Map.of(),
            null,
            List.of(),
            false,
            Map.of(),
            "ret_a",
            "ret_b",
            1000,
            "none"
        );
        assertThrows(AccessInvalidRequestException.class, () -> selector.select(request));
    }

    @Test
    void defaultProfileIsUsedWhenMissing() {
        given(retrievalClient.retrievalProfileExists("ret_default")).willReturn(true);
        var request = new ExternalRetrieveRequest(
            "q",
            List.of("c1"),
            Map.of(),
            null,
            List.of(),
            false,
            Map.of(),
            null,
            null,
            1000,
            "none"
        );
        assertEquals("ret_default", selector.select(request));
    }

    @Test
    void unknownProfileFails() {
        given(retrievalClient.retrievalProfileExists("ret_missing")).willReturn(false);
        var request = new ExternalRetrieveRequest(
            "q",
            List.of("c1"),
            Map.of(),
            null,
            List.of(),
            false,
            Map.of(),
            "ret_missing",
            null,
            1000,
            "none"
        );
        assertThrows(AccessInvalidRequestException.class, () -> selector.select(request));
    }
}
