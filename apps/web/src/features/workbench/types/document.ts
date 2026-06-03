// features/workbench/types/document.ts
// Re-export from canonical API types to avoid duplication

export type { DocumentProjectionItem } from "@/lib/api/types";
import type { DocumentProjectionItem } from "@/lib/api/types";

export interface DocumentListResponse {
  items: DocumentProjectionItem[];
  total: number;
}
