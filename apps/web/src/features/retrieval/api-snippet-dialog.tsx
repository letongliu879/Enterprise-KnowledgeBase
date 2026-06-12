"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Copy, Check } from "lucide-react";

interface ApiSnippetDialogProps {
  open: boolean;
  onClose: () => void;
  query: string;
  collectionId: string;
  retrievalProfileId: string;
  tokenBudget: number;
}

function curlSnippet(query: string, collectionId: string, retrievalProfileId: string, tokenBudget: number): string {
  return `curl -X POST "https://api.enterprise-knowledgebase.ai/workbench/retrieve" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
  "query": "${query.replace(/"/g, '\\"')}",
  "collection_id": "${collectionId}",
  "retrieval_profile_id": "${retrievalProfileId}",
  "token_budget": ${tokenBudget}
}'`;
}

function pythonSnippet(query: string, collectionId: string, retrievalProfileId: string, tokenBudget: number): string {
  return `import httpx

response = httpx.post(
    "https://api.enterprise-knowledgebase.ai/workbench/retrieve",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={
        "query": "${query.replace(/"/g, '\\"')}",
        "collection_id": "${collectionId}",
        "retrieval_profile_id": "${retrievalProfileId}",
        "token_budget": ${tokenBudget},
    },
)
data = response.json()
print(f"Found {len(data['evidence_items'])} evidence items")`;
}

const SNIPPETS: Record<string, (query: string, collectionId: string, retrievalProfileId: string, tokenBudget: number) => string> = {
  cURL: curlSnippet,
  Python: pythonSnippet,
};

export function ApiSnippetDialog({ open, onClose, query, collectionId, retrievalProfileId, tokenBudget }: ApiSnippetDialogProps) {
  const [tab, setTab] = useState("cURL");
  const [copied, setCopied] = useState(false);

  const snippet = SNIPPETS[tab](query, collectionId, retrievalProfileId, tokenBudget);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(snippet);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[640px]">
        <DialogHeader>
          <DialogTitle>API 代码片段</DialogTitle>
        </DialogHeader>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="cURL">cURL</TabsTrigger>
            <TabsTrigger value="Python">Python SDK</TabsTrigger>
          </TabsList>
          <TabsContent value={tab} className="space-y-3">
            <pre className="max-h-80 overflow-auto rounded-lg border bg-muted/10 p-4 text-xs leading-6 font-mono whitespace-pre">
              {snippet}
            </pre>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={handleCopy}>
                {copied ? <Check className="mr-1.5 h-3.5 w-3.5" /> : <Copy className="mr-1.5 h-3.5 w-3.5" />}
                {copied ? "已复制" : "复制"}
              </Button>
              <Button variant="outline" size="sm" onClick={onClose}>关闭</Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
