package com.realityrag.retrieval.toc;

import java.util.List;

public record DocumentTocNode(
    String collectionId,
    String finalDocId,
    String tocNodeId,
    String parentTocNodeId,
    String level,
    String title,
    List<String> tocPath,
    List<String> linkedChunkIds
) {
    public DocumentTocNode {
        tocPath = tocPath == null ? List.of() : List.copyOf(tocPath);
        linkedChunkIds = linkedChunkIds == null ? List.of() : List.copyOf(linkedChunkIds);
    }
}
