import { Layers } from "lucide-react";

import {
  EDITOR_THEMES,
  FONT_SIZES,
  type EditorTheme,
  useEditorPrefs,
} from "@/lib/editor-prefs";

const selectClass =
  "h-7 rounded border border-input bg-background/60 px-1.5 text-[11px] text-foreground outline-none focus-visible:ring-1 focus-visible:ring-ring";

const labelClass =
  "text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground";

export function TopBar() {
  const { fontSize, setFontSize, theme, setTheme } = useEditorPrefs();

  return (
    <header className="flex h-[1cm] shrink-0 items-center gap-3 border-b border-border/80 bg-card/90 px-4 backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <Layers className="size-4 text-primary" />
        <span className="text-xs font-semibold tracking-tight">
          Open Lakehouse
        </span>
      </div>

      <div className="ml-auto flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          <span className={labelClass}>Font</span>
          <select
            value={fontSize}
            onChange={(event) => setFontSize(Number(event.target.value))}
            className={selectClass}
            title="Notebook code font size"
          >
            {FONT_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}px
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={labelClass}>Theme</span>
          <select
            value={theme}
            onChange={(event) => setTheme(event.target.value as EditorTheme)}
            className={selectClass}
            title="Notebook code theme"
          >
            {(Object.keys(EDITOR_THEMES) as EditorTheme[]).map((key) => (
              <option key={key} value={key}>
                {EDITOR_THEMES[key].label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </header>
  );
}
