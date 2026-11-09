import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export const FONT_SIZES = [12, 13, 14, 15, 16, 17, 18, 20, 22];

export type EditorTheme = "dark" | "light";

export const EDITOR_THEMES: Record<
  EditorTheme,
  { label: string; background: string; color: string; placeholder: string }
> = {
  dark: {
    label: "Dark",
    background: "#070c16",
    color: "#e2e8f0",
    placeholder: "placeholder:text-muted-foreground/40",
  },
  light: {
    label: "Light",
    background: "#ffffff",
    color: "#111827",
    placeholder: "placeholder:text-slate-400",
  },
};

const FONT_KEY = "lakehouse-notebook-fontSize";
const THEME_KEY = "lakehouse-notebook-theme";
const DEFAULT_FONT_SIZE = 15;

function loadFontSize(): number {
  try {
    const parsed = Number(localStorage.getItem(FONT_KEY));
    return FONT_SIZES.includes(parsed) ? parsed : DEFAULT_FONT_SIZE;
  } catch {
    return DEFAULT_FONT_SIZE;
  }
}

function loadTheme(): EditorTheme {
  try {
    return localStorage.getItem(THEME_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

interface EditorPrefsValue {
  fontSize: number;
  setFontSize: (size: number) => void;
  theme: EditorTheme;
  setTheme: (theme: EditorTheme) => void;
}

const EditorPrefsContext = createContext<EditorPrefsValue | null>(null);

export function EditorPrefsProvider({ children }: { children: ReactNode }) {
  const [fontSize, setFontSizeState] = useState(loadFontSize);
  const [theme, setThemeState] = useState<EditorTheme>(loadTheme);

  useEffect(() => {
    try {
      localStorage.setItem(FONT_KEY, String(fontSize));
    } catch {
      // ignore storage errors
    }
  }, [fontSize]);

  useEffect(() => {
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // ignore storage errors
    }
    // The app palette (index.css) switches on the "dark" class of <html>.
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const setFontSize = useCallback((size: number) => {
    if (FONT_SIZES.includes(size)) setFontSizeState(size);
  }, []);

  const setTheme = useCallback((next: EditorTheme) => {
    setThemeState(next);
  }, []);

  const value = useMemo(
    () => ({ fontSize, setFontSize, theme, setTheme }),
    [fontSize, setFontSize, theme, setTheme],
  );

  return (
    <EditorPrefsContext.Provider value={value}>
      {children}
    </EditorPrefsContext.Provider>
  );
}

export function useEditorPrefs(): EditorPrefsValue {
  const value = useContext(EditorPrefsContext);
  if (!value) {
    throw new Error("useEditorPrefs must be used inside EditorPrefsProvider");
  }
  return value;
}
