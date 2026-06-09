declare module "pdfjs-dist/webpack.mjs" {
  export interface PDFPageViewport {
    width: number;
    height: number;
  }

  export interface PDFRenderTask {
    promise: Promise<void>;
    cancel(): void;
  }

  export interface PDFPageProxy {
    getViewport(params: { scale: number }): PDFPageViewport;
    render(params: {
      canvasContext: CanvasRenderingContext2D;
      viewport: PDFPageViewport;
    }): PDFRenderTask;
  }

  export interface PDFDocumentProxy {
    numPages: number;
    getPage(pageNumber: number): Promise<PDFPageProxy>;
    destroy(): Promise<void>;
  }

  export interface PDFDocumentLoadingTask {
    promise: Promise<PDFDocumentProxy>;
    destroy(): Promise<void>;
  }

  export function getDocument(params: {
    url: string;
    withCredentials?: boolean;
  }): PDFDocumentLoadingTask;
}
