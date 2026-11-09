import { useCallback, useRef, useState } from "react";

export interface EditorBuffer {
  id: string;
  name: string;
  source: string;
}

export interface EditorBuffers {
  buffers: EditorBuffer[];
  activeId: string;
  source: string;
  setSource: (source: string) => void;
  add: () => void;
  select: (id: string) => void;
  close: (id: string) => void;
}

let bufferSeq = 0;
const nextBufferId = () => {
  bufferSeq += 1;
  return `buffer-${bufferSeq}`;
};

/**
 * Manages several named code buffers for one editor, like notebook cells.
 * `nameTemplate` uses `{n}` for the running number, e.g. "Query {n}".
 */
export function useEditorBuffers(
  nameTemplate: string,
  initialSource: string,
): EditorBuffers {
  const counter = useRef(1);
  const [state, setState] = useState<{ buffers: EditorBuffer[]; activeId: string }>(
    () => {
      const first: EditorBuffer = {
        id: nextBufferId(),
        name: nameTemplate.replace("{n}", "1"),
        source: initialSource,
      };
      return { buffers: [first], activeId: first.id };
    },
  );

  const active =
    state.buffers.find((buffer) => buffer.id === state.activeId) ??
    state.buffers[0];

  const setSource = useCallback((source: string) => {
    setState((prev) => ({
      ...prev,
      buffers: prev.buffers.map((buffer) =>
        buffer.id === prev.activeId ? { ...buffer, source } : buffer,
      ),
    }));
  }, []);

  const add = useCallback(() => {
    counter.current += 1;
    const created: EditorBuffer = {
      id: nextBufferId(),
      name: nameTemplate.replace("{n}", String(counter.current)),
      source: "",
    };
    setState((prev) => ({
      buffers: [...prev.buffers, created],
      activeId: created.id,
    }));
  }, [nameTemplate]);

  const select = useCallback((id: string) => {
    setState((prev) => ({ ...prev, activeId: id }));
  }, []);

  const close = useCallback((id: string) => {
    setState((prev) => {
      if (prev.buffers.length <= 1) return prev;
      const index = prev.buffers.findIndex((buffer) => buffer.id === id);
      if (index < 0) return prev;
      const remaining = prev.buffers.filter((buffer) => buffer.id !== id);
      const activeId =
        prev.activeId === id
          ? remaining[Math.max(0, index - 1)].id
          : prev.activeId;
      return { buffers: remaining, activeId };
    });
  }, []);

  return {
    buffers: state.buffers,
    activeId: active.id,
    source: active.source,
    setSource,
    add,
    select,
    close,
  };
}
