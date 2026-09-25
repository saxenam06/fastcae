import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import { Crash } from "./app/Crash";
import { SectionProvider } from "./stage/Section";
import "./styles/tokens.css";
import "./styles/shell.css";
import "./styles/simulate.css";
import "./styles/pipeline.css";
import "./styles/designs.css";
import "./styles/volumes.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Crash>
      <SectionProvider>
        <App />
      </SectionProvider>
    </Crash>
  </StrictMode>,
);
