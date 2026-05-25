package com.realityrag.access.translate;

import com.realityrag.access.contracts.KnowledgeContext;
import org.springframework.stereotype.Component;

@Component
public class AccessResponseMapper {
    public KnowledgeContext map(KnowledgeContext response) {
        return response;
    }
}
