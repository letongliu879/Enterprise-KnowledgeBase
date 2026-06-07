"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  FileText,
  Search,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { toast } from "sonner";
import { workbenchApi } from "@/lib/api/client";
import type { ChunkView } from "@/lib/api/types";
import { isApiError, getErrorMessage } from "@/lib/api/errors";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type PreviewMode = "pdf" | "image" | "html" | "text";

function extOf(name?: string | null) {
  const raw = String(name || "").trim().toLowerCase();
  const dot = raw.lastIndexOf(".");
  return dot >= 0 ? raw.slice(dot + 1) : raw;
}

function inferMode(ext: string, contentType: string): PreviewMode {
  if (contentType.startsWith("image/")) return "image";
  if (contentType.includes("pdf") || ext === "pdf") return "pdf";
  if (contentType.includes("html") || ext === "html") return "html";
  return "text";
}

function collectAnchoredPages(chunks?: ChunkView[]) {
  const pages = new Set<number>();
  for (const chunk of chunks ?? []) {
    for (const span of chunk.page_spans ?? []) {
      const start = Number(span.page_from || 0);
      const end = Number(span.page_to || 0);
      if (start > 0) {
        for (let page = start; page <= Math.max(end, start); page += 1) {
          pages.add(page);
        }
      }
    }
  }
  return Array.from(pages).sort((a, b) => a - b);
}

function HighlightText({ text, highlight }: { text: string; highlight: string }) {
  if (!highlight.trim()) return <>{text}</>;

  const parts = text.split(
    new RegExp(`(${highlight.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi")
  );

  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === highlight.toLowerCase() ? (
          <mark key={i} className="rounded bg-amber-200 px-0.5 text-amber-900">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

function PdfCanvasPreview({
  url,
  page,
  zoom,
  title,
}: {
  url: string;
  page: number;
  zoom: number;
  title: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const documentRef = useRef<any>(null);
  const renderTaskRef = useRef<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [documentEpoch, setDocumentEpoch] = useState(0);

  useEffect(() => {
    let active = true;
    let loadingTask: any = null;

    setLoading(true);
    setError("");

    void (async () => {
      try {
        const pdfjs = await import("pdfjs-dist/webpack.mjs");
        loadingTask = pdfjs.getDocument({ url, withCredentials: true });
        const pdfDocument = await loadingTask.promise;
        if (!active) {
          await pdfDocument.destroy();
          return;
        }
        documentRef.current = pdfDocument;
        setDocumentEpoch((value) => value + 1);
        setLoading(false);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load PDF preview");
        setLoading(false);
      }
    })();

    return () => {
      active = false;
      renderTaskRef.current?.cancel?.();
      renderTaskRef.current = null;
      void loadingTask?.destroy?.();
      void documentRef.current?.destroy?.();
      documentRef.current = null;
    };
  }, [url]);

  useEffect(() => {
    let active = true;

    void (async () => {
      const pdfDocument = documentRef.current;
      const canvas = canvasRef.current;
      if (!pdfDocument || !canvas) return;

      try {
        setError("");
        const safePage = Math.max(1, Math.min(page, pdfDocument.numPages));
        const pdfPage = await pdfDocument.getPage(safePage);
        const viewport = pdfPage.getViewport({ scale: zoom / 100 });
        const context = canvas.getContext("2d");
        if (!context) {
          setError("Canvas 2D context unavailable");
          return;
        }

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;

        renderTaskRef.current?.cancel?.();
        const renderTask = pdfPage.render({ canvasContext: context, viewport });
        renderTaskRef.current = renderTask;
        await renderTask.promise;
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to render PDF page");
      }
    })();

    return () => {
      active = false;
      renderTaskRef.current?.cancel?.();
      renderTaskRef.current = null;
    };
  }, [documentEpoch, page, zoom, url]);

  if (loading) {
    return <Skeleton className="h-[780px] rounded-lg" />;
  }

  if (error) {
    return (
      <EmptyState
        icon={FileText}
        title="PDF preview failed"
        description={error}
      />
    );
  }

  return (
    <div className="overflow-auto rounded-lg border bg-white p-4">
      <canvas
        ref={canvasRef}
        aria-label={title}
        className="mx-auto block max-w-full shadow-sm"
      />
    </div>
  );
}

export function DocumentViewer({
  sourceFileId,
  filename,
  previewText,
  parserId,
  parserBackend,
  warnings = [],
  chunks = [],
  searchText,
  onSearchComplete,
}: {
  sourceFileId?: string | null;
  filename?: string | null;
  previewText?: string | null;
  parserId?: string | null;
  parserBackend?: string | null;
  warnings?: string[];
  chunks?: ChunkView[];
  searchText?: string;
  onSearchComplete?: (found: boolean) => void;
}) {
  const extension = useMemo(() => extOf(filename), [filename]);
  const anchoredPages = useMemo(() => collectAnchoredPages(chunks), [chunks]);
  const [currentPage, setCurrentPage] = useState(anchoredPages[0] || 1);
  const [pageInput, setPageInput] = useState(String(anchoredPages[0] || 1));
  const [zoom, setZoom] = useState(100);
  const [sourceText, setSourceText] = useState("");
  const [searchHighlight, setSearchHighlight] = useState("");

  const pageCount = anchoredPages.length > 0 ? anchoredPages[anchoredPages.length - 1] : null;

  useEffect(() => {
    const firstPage = anchoredPages[0] || 1;
    setCurrentPage(firstPage);
    setPageInput(String(firstPage));
  }, [sourceFileId, anchoredPages]);

  const {
    data: sourcePreview,
    error: sourcePreviewError,
    isLoading: sourcePreviewLoading,
  } = useQuery({
    queryKey: ["document-viewer-source-preview", sourceFileId],
    queryFn: () => workbenchApi.getSourceFilePreview(sourceFileId as string),
    enabled: Boolean(sourceFileId),
    retry: 0,
  });

  const {
    data: sourceBlob,
    error: sourceBlobError,
    isLoading: sourceBlobLoading,
  } = useQuery({
    queryKey: ["document-viewer-source-preview-content", sourceFileId],
    queryFn: () => workbenchApi.getSourceFilePreviewBlob(sourceFileId as string),
    enabled: Boolean(
      sourceFileId &&
        sourcePreview?.preview_available &&
        (sourcePreview?.preview_kind === "text" ||
          sourcePreview?.preview_mime_type?.startsWith("text/"))
    ),
    retry: 0,
  });

  const sourceError = sourcePreviewError || sourceBlobError;
  const isLoading = sourcePreviewLoading || sourceBlobLoading;

  const mode = useMemo(
    () => inferMode(extension, sourcePreview?.preview_mime_type || sourceBlob?.contentType || ""),
    [extension, sourceBlob?.contentType, sourcePreview?.preview_mime_type]
  );

  const directPreviewUrl = useMemo(() => {
    if (!sourceFileId || !sourcePreview?.preview_available) return "";
    return workbenchApi.getSourceFilePreviewContentUrl(sourceFileId);
  }, [sourceFileId, sourcePreview?.preview_available]);

  const effectiveWarnings = useMemo(
    () => warnings.filter((item) => String(item || "").trim().length > 0),
    [warnings]
  );

  useEffect(() => {
    if (!sourceBlob?.blob || mode !== "text") {
      setSourceText("");
      return;
    }

    let active = true;
    void sourceBlob.blob.text().then((text) => {
      if (active) setSourceText(text);
    });

    return () => {
      active = false;
    };
  }, [sourceBlob?.blob, mode]);

  useEffect(() => {
    if (!searchText?.trim()) {
      setSearchHighlight("");
      return;
    }

    setSearchHighlight(searchText);
    if (!previewText?.trim()) {
      onSearchComplete?.(false);
      return;
    }

    const container = document.querySelector("[data-document-viewer-content]");
    if (!container) {
      onSearchComplete?.(false);
      return;
    }

    const text = container.textContent || "";
    const index = text.toLowerCase().indexOf(searchText.toLowerCase());
    if (index < 0) {
      onSearchComplete?.(false);
      return;
    }

    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    let currentIndex = 0;
    let foundNode: Text | null = null;
    let foundOffset = 0;

    while (walker.nextNode()) {
      const node = walker.currentNode as Text;
      const nodeText = node.textContent || "";
      if (currentIndex <= index && currentIndex + nodeText.length > index) {
        foundNode = node;
        foundOffset = index - currentIndex;
        break;
      }
      currentIndex += nodeText.length;
    }

    if (foundNode) {
      const range = document.createRange();
      range.setStart(foundNode, foundOffset);
      range.setEnd(foundNode, Math.min(foundOffset + searchText.length, foundNode.length));
      const selection = window.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
      foundNode.parentElement?.scrollIntoView({ behavior: "smooth", block: "center" });
      onSearchComplete?.(true);
      return;
    }

    onSearchComplete?.(false);
  }, [searchText, previewText, onSearchComplete]);

  const copyParsedText = async () => {
    if (!previewText?.trim()) return;
    await navigator.clipboard.writeText(previewText);
    toast.success("Parsed text copied");
  };

  const jumpToPage = (next: number) => {
    const maxPage = pageCount || next;
    const safe = Math.max(1, Math.min(next, maxPage));
    setCurrentPage(safe);
    setPageInput(String(safe));
  };

  const zoomOut = () => setZoom((prev) => Math.max(50, prev - 10));
  const zoomIn = () => setZoom((prev) => Math.min(200, prev + 10));
  const resetZoom = () => setZoom(100);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-card/80 p-4 shadow-sm">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-sm font-semibold">{filename || "Source preview"}</p>
              <Badge variant="outline">{extension ? extension.toUpperCase() : "FILE"}</Badge>
              {parserId ? <Badge variant="secondary">Parser: {parserId}</Badge> : null}
              {parserBackend ? <Badge variant="outline">Backend: {parserBackend}</Badge> : null}
            </div>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span>{pageCount ? `Anchored pages: ${pageCount}` : "No page anchors"}</span>
              <span>{chunks.length} parsed chunk{chunks.length === 1 ? "" : "s"}</span>
              {effectiveWarnings.length > 0 ? <span>{effectiveWarnings.length} warning(s)</span> : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="sm" onClick={zoomOut}>
              <ZoomOut className="mr-1 h-3.5 w-3.5" />
              Zoom out
            </Button>
            <Button variant="outline" size="sm" onClick={resetZoom}>
              {zoom}%
            </Button>
            <Button variant="outline" size="sm" onClick={zoomIn}>
              <ZoomIn className="mr-1 h-3.5 w-3.5" />
              Zoom in
            </Button>
            {previewText ? (
              <Button variant="outline" size="sm" onClick={() => void copyParsedText()}>
                <Copy className="mr-1 h-3.5 w-3.5" />
                Copy text
              </Button>
            ) : null}
            {directPreviewUrl ? (
              <a href={directPreviewUrl} download={filename || "source-preview"}>
                <Button variant="outline" size="sm">
                  <Download className="mr-1 h-3.5 w-3.5" />
                  Download
                </Button>
              </a>
            ) : null}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t pt-4">
          <Button
            variant="outline"
            size="sm"
            disabled={!pageCount || currentPage <= 1}
            onClick={() => jumpToPage(currentPage - 1)}
          >
            <ChevronLeft className="mr-1 h-3.5 w-3.5" />
            Prev
          </Button>
          <div className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={pageInput}
              onChange={(event) => setPageInput(event.target.value)}
              onBlur={() => jumpToPage(Number(pageInput || currentPage))}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  jumpToPage(Number(pageInput || currentPage));
                }
              }}
              className="h-8 w-20 bg-background"
            />
            <span className="text-xs text-muted-foreground">/ {pageCount || "-"}</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            disabled={!pageCount || currentPage >= pageCount}
            onClick={() => jumpToPage(currentPage + 1)}
          >
            Next
            <ChevronRight className="ml-1 h-3.5 w-3.5" />
          </Button>
          {anchoredPages.length > 0 ? (
            <div className="flex flex-wrap gap-1">
              {anchoredPages.slice(0, 10).map((page) => (
                <Button
                  key={page}
                  variant={page === currentPage ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => jumpToPage(page)}
                >
                  P{page}
                </Button>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      <Tabs defaultValue="source" className="space-y-4">
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="source">Source</TabsTrigger>
          <TabsTrigger value="parsed-text">Parsed text</TabsTrigger>
        </TabsList>

        <TabsContent value="source">
          {isLoading ? (
            <Skeleton className="h-[720px] rounded-lg" />
          ) : sourceError ? (
            <Alert variant="destructive">
              <FileText className="h-4 w-4" />
              <AlertDescription>
                {isApiError(sourceError) ? sourceError.message : getErrorMessage(sourceError)}
              </AlertDescription>
            </Alert>
          ) : !sourceFileId ? (
            <EmptyState
              icon={FileText}
              title="Source preview is not available"
              description="This document does not currently link to a source file."
            />
          ) : !sourcePreview?.preview_available ? (
            <EmptyState
              icon={FileText}
              title="Original preview is not available for this format"
              description="This file type does not currently expose a source preview asset. Use Download to open the source file."
            />
          ) : mode === "pdf" && directPreviewUrl ? (
            <PdfCanvasPreview
              title={filename || "preview"}
              url={directPreviewUrl}
              page={currentPage}
              zoom={zoom}
            />
          ) : mode === "image" && directPreviewUrl ? (
            <div className="overflow-auto rounded-lg border bg-muted/10 p-4">
              <img
                src={directPreviewUrl}
                alt={filename || "preview"}
                className="mx-auto max-w-full"
                style={{ maxWidth: `${zoom}%` }}
              />
            </div>
          ) : mode === "html" && directPreviewUrl ? (
            <iframe
              title={filename || "preview"}
              src={directPreviewUrl}
              className="h-[780px] w-full rounded-lg border bg-white"
            />
          ) : mode === "text" ? (
            <div className="max-h-[780px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/10 p-4 leading-7">
              {sourceText || "Source preview text is empty."}
            </div>
          ) : (
            <EmptyState
              icon={FileText}
              title="Original preview is not available"
              description="This format does not currently support an in-app original-file preview. Use Download to open the source file."
            />
          )}
        </TabsContent>

        <TabsContent value="parsed-text">
          {previewText ? (
            <div
              data-document-viewer-content
              className="max-h-[780px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/10 p-4 text-sm leading-7"
            >
              {searchHighlight ? (
                <HighlightText text={previewText} highlight={searchHighlight} />
              ) : (
                previewText
              )}
            </div>
          ) : (
            <EmptyState
              icon={FileText}
              title="No parsed preview text"
              description="This parse snapshot does not currently expose normalized preview text."
            />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
