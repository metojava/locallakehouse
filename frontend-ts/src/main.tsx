import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import { EditorPrefsProvider } from "@/lib/editor-prefs";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <EditorPrefsProvider>
      <App />
    </EditorPrefsProvider>
  </React.StrictMode>,
);
