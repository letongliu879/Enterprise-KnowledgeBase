"use client";

import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Trash2, Save, Upload, Plus } from "lucide-react";
import { toast } from "sonner";

const PRESETS_KEY = "ekb-retrieval-presets";

interface RetrievalPreset {
  name: string;
  query: string;
  collectionId: string;
  retrievalProfileId: string;
  tokenBudget: number;
  debug: "none" | "basic" | "full";
}

interface RetrievalPresetsDialogProps {
  open: boolean;
  onClose: () => void;
  onLoadPreset: (preset: Omit<RetrievalPreset, "name"> & { query: string }) => void;
  currentQuery: string;
  currentCollectionId: string;
  currentRetrievalProfileId: string;
  currentTokenBudget: number;
}

export function RetrievalPresetsDialog({
  open, onClose, onLoadPreset,
  currentQuery, currentCollectionId, currentRetrievalProfileId, currentTokenBudget,
}: RetrievalPresetsDialogProps) {
  const [presets, setPresets] = useState<RetrievalPreset[]>([]);
  const [presetName, setPresetName] = useState("");

  useEffect(() => {
    if (!open) return;
    try {
      const raw = localStorage.getItem(PRESETS_KEY);
      setPresets(raw ? JSON.parse(raw) : []);
    } catch { setPresets([]); }
  }, [open]);

  const savePresets = (updated: RetrievalPreset[]) => {
    localStorage.setItem(PRESETS_KEY, JSON.stringify(updated));
    setPresets(updated);
  };

  const handleSave = () => {
    if (!presetName.trim()) {
      toast.error("请输入预设名称");
      return;
    }
    const newPreset: RetrievalPreset = {
      name: presetName.trim(),
      query: currentQuery,
      collectionId: currentCollectionId,
      retrievalProfileId: currentRetrievalProfileId,
      tokenBudget: currentTokenBudget,
      debug: "none",
    };
    savePresets([...presets, newPreset]);
    setPresetName("");
    toast.success("预设已保存");
  };

  const handleDelete = (index: number) => {
    const updated = presets.filter((_, i) => i !== index);
    savePresets(updated);
    toast.success("预设已删除");
  };

  const handleLoad = (preset: RetrievalPreset) => {
    onLoadPreset({
      query: preset.query,
      collectionId: preset.collectionId,
      retrievalProfileId: preset.retrievalProfileId,
      tokenBudget: preset.tokenBudget,
      debug: preset.debug,
    });
    onClose();
    toast.success(`已加载预设: ${preset.name}`);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>检索预设</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="flex gap-2 items-end">
            <div className="flex-1 space-y-1">
              <Label htmlFor="preset-name">保存当前参数为新预设</Label>
              <Input id="preset-name" placeholder="预设名称" value={presetName} onChange={(e) => setPresetName(e.target.value)} />
            </div>
            <Button size="sm" onClick={handleSave} disabled={!presetName.trim()}>
              <Save className="h-3.5 w-3.5 mr-1" /> 保存
            </Button>
          </div>

          <div className="space-y-2 max-h-64 overflow-auto">
            {presets.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">暂无保存的预设</p>
            ) : (
              presets.map((preset, i) => (
                <div key={i} className="flex items-center justify-between rounded-xl border bg-muted/10 p-3">
                  <div className="min-w-0 flex-1" onClick={() => handleLoad(preset)}>
                    <p className="text-sm font-medium truncate cursor-pointer hover:text-primary">{preset.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{preset.query}</p>
                  </div>
                  <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" aria-label="删除预设" onClick={() => handleDelete(i)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
