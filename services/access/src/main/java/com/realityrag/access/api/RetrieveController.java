package com.realityrag.access.api;

import com.realityrag.access.contracts.ExternalRetrieveRequest;
import com.realityrag.access.contracts.KnowledgeContext;
import com.realityrag.access.service.AccessGatewayService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.io.FileWriter;
import java.io.IOException;
import java.time.Instant;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RetrieveController {
    private final AccessGatewayService accessGatewayService;

    public RetrieveController(AccessGatewayService accessGatewayService) {
        this.accessGatewayService = accessGatewayService;
    }

    private void dbg(String msg) {
        String path = System.getProperty("java.io.tmpdir") + "/access-ctrl-dbg.log";
        try (FileWriter fw = new FileWriter(path, true)) {
            fw.write(Instant.now() + " " + msg + "\n");
        } catch (IOException ignored) {}
    }

    @PostMapping("/v1/retrieve")
    public KnowledgeContext retrieve(
        @Valid @RequestBody ExternalRetrieveRequest request,
        HttpServletRequest httpRequest
    ) {
        dbg("[CTRL] /v1/retrieve called query=" + request.query() + " profile=" + request.retrievalProfileId());
        KnowledgeContext result = accessGatewayService.retrieve(request, httpRequest);
        dbg("[CTRL] /v1/retrieve returning evidence_count=" + result.resultChunks().size());
        return result;
    }
}
