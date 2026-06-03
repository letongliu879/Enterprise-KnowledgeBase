"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Copy,
  Download,
  FileText,
  Loader2,
  Search,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { toast } from "sonner";
import { workbenchApi } from "@/lib/api/client";
import type { ChunkView } from "@/lib/api/types";
import DOMPurify from "dompurify";
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

async function extractPptxText(bytes: ArrayBuffer): Promise<string> {
  const JSZip = (await import("jszip")).default;
  const zip = await JSZip.loadAsync(bytes);
  const parser = new DOMParser();
  const slides = Object.keys(zip.files)
    .filter((name) => /^ppt\/slides\/slide\d+\.xml$/i.test(name))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
  const sections: string[] = [];

  for (const slide of slides) {
    const xml = await zip.file(slide)?.async("text");
    if (!xml) continue;
    const doc = parser.parseFromString(xml, "application/xml");
    const texts = Array.from(doc.getElementsByTagName("a:t"))
      .map((node) => node.textContent?.trim() || "")
      .filter(Boolean);
    if (texts.length > 0) {
      sections.push(texts.join("\n"));
    }
  }

  return sections.join("\n\n");
}

function HighlightText({ text, highlight }: { text: string; highlight: string }) {
  if (!highlight.trim()) return <>{text}</>;

  const parts = text.split(new RegExp(`(${highlight.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi"));

  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === highlight.toLowerCase() ? (
          <mark key={i} className="bg-amber-200 text-amber-900 px-0.5 rounded">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </>
  );
}

function ZoomableHtml({
  html,
  zoom,
}: {
  html: string;
  zoom: number;
}) {
  const scale = zoom / 100;
  const sanitizedHtml = DOMPurify.sanitize(html);
  return (
    <div className="overflow-auto rounded-lg border bg-white p-4">
      <div
        className="origin-top-left"
        style={{
          transform: `scale(${scale})`,
          width: `${100 / scale}%`,
        }}
      >
        <div
          className="prose prose-sm max-w-none"
          dangerouslySetInnerHTML={{ __html: sanitizedHtml }}
        />
      </div>
    </div>
  );
}

export function DocumentViewer({
  parseSnapshotId,
  filename,
  previewText,
  parserId,
  parserBackend,
  warnings = [],
  chunks = [],
  searchText,
  onSearchComplete,
}: {
  parseSnapshotId?: string | null;
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
  const [objectUrl, setObjectUrl] = useState("");
  const [htmlPreview, setHtmlPreview] = useState("");
  const [textPreview, setTextPreview] = useState("");
  const [rendering, setRendering] = useState(false);
  const [searchHighlight, setSearchHighlight] = useState("");

  const pageCount = anchoredPages.length > 0 ? anchoredPages[anchoredPages.length - 1] : null;

  useEffect(() => {
    const firstPage = anchoredPages[0] || 1;
    setCurrentPage(firstPage);
    setPageInput(String(firstPage));
  }, [parseSnapshotId, anchoredPages]);

  const { data, error, isLoading } = useQuery({
    queryKey: ["document-viewer-source", parseSnapshotId],
    queryFn: () => workbenchApi.getParseSnapshotSourceBlob(parseSnapshotId as string),
    enabled: Boolean(parseSnapshotId),
    retry: 0,
  });

  const mode = useMemo(
    () => inferMode(extension, data?.contentType || ""),
    [data?.contentType, extension]
  );

  const effectiveWarnings = useMemo(
    () => warnings.filter((item) => String(item || "").trim().length > 0),
    [warnings]
  );

  useEffect(() => {
    if (!data?.blob) {
      setObjectUrl("");
      return;
    }
    const url = URL.createObjectURL(data.blob);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [data?.blob]);

  useEffect(() => {
    let active = true;
    async function render() {
      if (!data?.blob) {
        setHtmlPreview("");
        setTextPreview("");
        return;
      }

      setRendering(true);
      setHtmlPreview("");
      setTextPreview("");

      try {
        const bytes = await data.blob.arrayBuffer();

        if (extension === "docx") {
          const mammoth = await import("mammoth");
          const result = await mammoth.convertToHtml({ arrayBuffer: bytes });
          if (active) setHtmlPreview(result.value);
          return;
        }

        if (extension === "xlsx" || extension === "xls" || extension === "csv") {
          const XLSX = await import("xlsx");
          const workbook = XLSX.read(bytes, { type: "array" });
          const html = workbook.SheetNames.slice(0, 5)
            .map((sheetName) => {
              const sheet = workbook.Sheets[sheetName];
              return `<section><h3>${sheetName}</h3>${XLSX.utils.sheet_to_html(sheet)}</section>`;
            })
            .join("");
          if (active) setHtmlPreview(html);
          return;
        }

        if (extension === "pptx" || extension === "ppt") {
          const text = await extractPptxText(bytes);
          if (active) setTextPreview(text);
          return;
        }

        if (extension === "txt" || extension === "md" || extension === "markdown") {
          const text = new TextDecoder("utf-8").decode(bytes);
          if (active) setTextPreview(text);
          return;
        }

        if (!parseSnapshotId && previewText) {
          if (active) setTextPreview(previewText);
        }
      } finally {
        if (active) setRendering(false);
      }
    }

    void render();
    return () => {
      active = false;
    };
  }, [data?.blob, extension, parseSnapshotId, previewText]);

  // Handle external search requests
  useEffect(() => {
    if (!searchText?.trim()) {
      setSearchHighlight("");
      return;
    }

    setSearchHighlight(searchText);

    // For text/html modes, try to find and scroll to the text
    if (mode === "text" || mode === "html") {
      const container = document.querySelector("[data-document-viewer-content]");
      if (container) {
        const text = container.textContent || "";
        const index = text.toLowerCase().indexOf(searchText.toLowerCase());
        if (index >= 0) {
          // Try to find the element containing this text
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
          }

          onSearchComplete?.(true);
          return;
        }
      }
    }

    // For PDF, we can't programmatically search inside iframe easily.
    // For text/html, reaching here means the text was not found.
    onSearchComplete?.(false);
  }, [searchText, mode, textPreview, htmlPreview, onSearchComplete]);

  const pdfUrl = useMemo(() => {
    if (!objectUrl || mode !== "pdf") return "";
    return `${objectUrl}#page=${currentPage}&zoom=${zoom}`;
  }, [currentPage, mode, objectUrl, zoom]);

  const copyPreviewText = async () => {
    const text = textPreview || previewText || "";
    if (!text.trim()) return;
    await navigator.clipboard.writeText(text);
    toast.success("Preview text copied");
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
            {(textPreview || previewText) ? (
              <Button variant="outline" size="sm" onClick={() => void copyPreviewText()}>
                <Copy className="mr-1 h-3.5 w-3.5" />
                Copy text
              </Button>
            ) : null}
            {objectUrl ? (
              <a href={objectUrl} download={filename || "source-preview"}>
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
            <span className="text-xs text-muted-foreground">
              / {pageCount || "-"}
            </span>
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
          <TabsTrigger value="metadata">Metadata</TabsTrigger>
        </TabsList>

        <TabsContent value="source">
          {isLoading ? (
            <Skeleton className="h-[720px] rounded-lg" />
          ) : error ? (
            <Alert variant="destructive">
              <FileText className="h-4 w-4" />
              <AlertDescription>{isApiError(error) ? error.message : getErrorMessage(error)}</AlertDescription>
            </Alert>
          ) : !parseSnapshotId || !data?.blob ? (
            previewText ? (
              <div className="max-h-[720px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/10 p-4 text-sm leading-7">
                {previewText}
              </div>
            ) : (
              <EmptyState
                icon={FileText}
                title="Source preview is not available"
                description="This document does not currently expose a readable source file stream."
              />
            )
          ) : rendering ? (
            <div className="flex h-[720px] items-center justify-center rounded-lg border bg-muted/10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : mode === "pdf" && pdfUrl ? (
            <iframe
              title={filename || "preview"}
              src={pdfUrl}
              className="h-[780px] w-full rounded-lg border bg-white"
            />
          ) : mode === "image" && objectUrl ? (
            <div className="overflow-auto rounded-lg border bg-muted/10 p-4">
              <img
                src={objectUrl}
                alt={filename || "preview"}
                className="mx-auto max-w-full"
                style={{ maxWidth: `${zoom}%` }}
              />
            </div>
          ) : htmlPreview ? (
            <div data-document-viewer-content>
              <ZoomableHtml html={htmlPreview} zoom={zoom} />
            </div>
          ) : textPreview ? (
            <div
              data-document-viewer-content
              className="max-h-[780px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/10 p-4 leading-7"
              style={{ fontSize: `${Math.max(12, zoom / 6)}px` }}
            >
              {searchHighlight ? (
                <HighlightText text={textPreview} highlight={searchHighlight} />
              ) : (
                textPreview
              )}
            </div>
          ) : objectUrl && mode === "html" ? (
            <iframe
              title={filename || "preview"}
              src={objectUrl}
              className="h-[780px] w-full rounded-lg border bg-white"
            />
          ) : (
            <EmptyState
              icon={FileText}
              title="Preview format is not available yet"
              description="The source file is reachable, but the viewer adapter has not produced a readable in-app rendering for this format."
            />
          )}
        </TabsContent>

        <TabsContent value="parsed-text">
          {previewText ? (
            <div className="max-h-[720px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/10 p-4 text-sm leading-7">
              {previewText}
            </div>
          ) : textPreview ? (
            <div className="max-h-[720px] overflow-auto whitespace-pre-wrap rounded-lg border bg-muted/10 p-4 text-sm leading-7">
              {textPreview}
            </div>
          ) : (
            <EmptyState
              icon={FileText}
              title="No parsed preview text"
              description="This parse snapshot does not currently expose normalized preview text."
            />
          )}
        </TabsContent>

        <TabsContent value="metadata">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border bg-muted/15 p-4">
              <p className="text-xs text-muted-foreground">Filename</p>
              <p className="mt-1 break-all font-medium">{filename || "-"}</p>
            </div>
            <div className="rounded-xl border bg-muted/15 p-4">
              <p className="text-xs text-muted-foreground">Current page</p>
              <p className="mt-1 font-medium">{pageCount ? `${currentPage} / ${pageCount}` : "-"}</p>
            </div>
            <div className="rounded-xl border bg-muted/15 p-4">
              <p className="text-xs text-muted-foreground">Parser</p>
              <p className="mt-1 font-medium">{parserId || "-"}</p>
            </div>
            <div className="rounded-xl border bg-muted/15 p-4">
              <p className="text-xs text-muted-foreground">Backend</p>
              <p className="mt-1 font-medium">{parserBackend || "-"}</p>
            </div>
          </div>

          {effectiveWarnings.length > 0 ? (
            <Alert className="mt-4">
              <FileText className="h-4 w-4" />
              <AlertDescription>{effectiveWarnings.join("; ")}</AlertDescription>
            </Alert>
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}
