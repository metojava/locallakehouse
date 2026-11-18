import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Settings2 } from "lucide-react";

import { EDITOR_THEMES, useEditorPrefs } from "@/lib/editor-prefs";
import { cn } from "@/lib/utils";

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  onRun: () => void;
  language?: "sql" | "python" | "java" | "scala";
}

const FONT_SIZES = [13, 15, 17, 19, 21, 24];

const EDITOR_LABELS: Record<NonNullable<CodeEditorProps["language"]>, string> = {
  sql: "SQL editor",
  python: "Python editor",
  java: "Java editor",
  scala: "Scala editor",
};

const EDITOR_PLACEHOLDERS: Record<NonNullable<CodeEditorProps["language"]>, string> = {
  sql: "SELECT * FROM local_iceberg.demo.sales LIMIT 100;",
  python: "df = spark.range(100)",
  java: "// Main.java: public class Main with a main method",
  scala: "// Main.scala: object Main with a main method",
};

function loadPreference<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`lakehouse-editor-${key}`);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function savePreference(key: string, value: unknown) {
  try {
    localStorage.setItem(`lakehouse-editor-${key}`, JSON.stringify(value));
  } catch {
    // ignore
  }
}

export function CodeEditor({
  value,
  onChange,
  onRun,
  language = "sql",
}: CodeEditorProps) {
  const gutterRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lineCount = Math.max(1, value.split("\n").length);

  const [fontSize, setFontSize] = useState(() =>
    loadPreference<number>("fontSize", 17),
  );
  useEffect(() => {
    savePreference("fontSize", fontSize);
  }, [fontSize]);

  // Background and text colors are stored per app theme, so the light theme
  // never inherits the dark theme's colors (and vice versa).
  const { theme } = useEditorPrefs();
  const palette = EDITOR_THEMES[theme];
  const [bgColor, setBgColorState] = useState(() =>
    loadPreference<string>(`bgColor-${theme}`, palette.background),
  );
  const [textColor, setTextColorState] = useState(() =>
    loadPreference<string>(`textColor-${theme}`, palette.color),
  );

  const lastTheme = useRef(theme);
  useEffect(() => {
    if (lastTheme.current === theme) return;
    lastTheme.current = theme;
    setBgColorState(loadPreference<string>(`bgColor-${theme}`, palette.background));
    setTextColorState(loadPreference<string>(`textColor-${theme}`, palette.color));
  }, [theme, palette.background, palette.color]);

  const setBgColor = (value: string) => {
    setBgColorState(value);
    savePreference(`bgColor-${theme}`, value);
  };

  const setTextColor = (value: string) => {
    setTextColorState(value);
    savePreference(`textColor-${theme}`, value);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      onRun();
      return;
    }

    if (event.key === "Tab") {
      event.preventDefault();
      const target = event.currentTarget;
      const start = target.selectionStart;
      const end = target.selectionEnd;
      const nextValue = `${value.slice(0, start)}  ${value.slice(end)}`;
      onChange(nextValue);
      window.requestAnimationFrame(() => {
        if (textareaRef.current) {
          textareaRef.current.selectionStart = start + 2;
          textareaRef.current.selectionEnd = start + 2;
        }
      });
    }
  };

  return (
    <div className="overflow-hidden rounded-b-md border border-t-0 border-border/60">
      <div className="flex flex-wrap items-center gap-3 border-b border-border/60 bg-muted/20 px-3 py-2">
        <div className="flex items-center gap-1.5">
          <Settings2 className="size-3.5 text-muted-foreground" />
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Editor
          </span>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[10px] text-muted-foreground">Size</label>
          <select
            value={fontSize}
            onChange={(e) => setFontSize(Number(e.target.value))}
            className="h-6 rounded border border-input bg-transparent px-1.5 text-[11px] text-foreground outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            {FONT_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}px
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[10px] text-muted-foreground">Background</label>
          <input
            type="color"
            value={bgColor}
            onChange={(e) => setBgColor(e.target.value)}
            className="size-6 cursor-pointer rounded border-0 bg-transparent p-0"
            title="Background color"
          />
        </div>

        <div className="flex items-center gap-2">
          <label className="text-[10px] text-muted-foreground">Text</label>
          <input
            type="color"
            value={textColor}
            onChange={(e) => setTextColor(e.target.value)}
            className="size-6 cursor-pointer rounded border-0 bg-transparent p-0"
            title="Text color"
          />
        </div>
      </div>

      <div
        className="flex h-[330px] w-full overflow-hidden"
        style={{ backgroundColor: bgColor }}
      >
        <div
          ref={gutterRef}
          aria-hidden="true"
          className={cn(
            "no-scrollbar h-full w-14 shrink-0 select-none overflow-hidden border-r border-border/60 bg-muted/15 py-4 text-right font-mono leading-6",
            theme === "dark" ? "text-white" : "text-muted-foreground/40",
          )}
          style={{ fontSize }}
        >
          {Array.from({ length: lineCount }, (_, index) => (
            <div key={index} className="pr-3">
              {index + 1}
            </div>
          ))}
        </div>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          onScroll={(event) => {
            if (gutterRef.current) {
              gutterRef.current.scrollTop = event.currentTarget.scrollTop;
            }
          }}
          spellCheck={false}
          autoCapitalize="off"
          autoCorrect="off"
          aria-label={EDITOR_LABELS[language]}
          placeholder={EDITOR_PLACEHOLDERS[language]}
          className="h-full w-full resize-none overflow-auto bg-transparent px-4 py-4 font-mono leading-6 caret-primary outline-none placeholder:text-muted-foreground/35"
          style={{
            fontSize,
            color: textColor,
            tabSize: 2,
          }}
        />
      </div>
    </div>
  );
}
