import { FileCode, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { EditorBuffer } from "@/lib/editor-buffers";
import { cn } from "@/lib/utils";

interface BufferTabsProps {
  buffers: EditorBuffer[];
  activeId: string;
  onSelect: (id: string) => void;
  onAdd: () => void;
  onClose: (id: string) => void;
}

export function BufferTabs({
  buffers,
  activeId,
  onSelect,
  onAdd,
  onClose,
}: BufferTabsProps) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto border-b border-border/60 bg-muted/20 px-2 py-1.5">
      {buffers.map((buffer) => {
        const active = buffer.id === activeId;
        return (
          <div
            key={buffer.id}
            className={cn(
              "flex h-7 shrink-0 items-center rounded-md border text-[11px] transition-colors",
              active
                ? "border-primary/40 bg-background text-foreground shadow-sm"
                : "border-transparent text-muted-foreground hover:bg-accent/60 hover:text-foreground",
            )}
          >
            <button
              type="button"
              onClick={() => onSelect(buffer.id)}
              className="flex h-full items-center gap-1.5 px-2.5"
            >
              <FileCode className="size-3" />
              {buffer.name}
            </button>
            {buffers.length > 1 ? (
              <button
                type="button"
                aria-label={`Close ${buffer.name}`}
                title="Close editor"
                onClick={() => onClose(buffer.id)}
                className="mr-1 grid size-4 place-items-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="size-3" />
              </button>
            ) : null}
          </div>
        );
      })}
      <Button
        variant="ghost"
        size="sm"
        className="h-7 shrink-0 px-2 text-[11px]"
        onClick={onAdd}
        title="New code editor"
      >
        <Plus />
        New
      </Button>
    </div>
  );
}
