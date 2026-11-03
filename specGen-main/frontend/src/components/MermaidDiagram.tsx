import { useEffect, useId, useState } from "react";

// Mermaid is heavy: load it only when a diagram is actually displayed.
let mermaidLoader: Promise<typeof import("mermaid").default> | null = null;
function loadMermaid() {
  mermaidLoader ??= import("mermaid").then(({ default: mermaid }) => {
    mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "neutral", fontFamily: "Inter, sans-serif" });
    return mermaid;
  });
  return mermaidLoader;
}

export function MermaidDiagram({ code }: { code: string }) {
  const id = `mermaid-${useId().replace(/:/g, "")}`;
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!code.trim()) {
      setSvg("");
      setError("");
      return;
    }
    loadMermaid()
      .then((mermaid) => mermaid.render(id, code))
      .then((result) => {
        if (cancelled) return;
        setSvg(result.svg);
        setError("");
      })
      .catch((renderError: unknown) => {
        if (cancelled) return;
        setSvg("");
        setError(renderError instanceof Error ? renderError.message : String(renderError));
      });
    return () => {
      cancelled = true;
    };
  }, [code, id]);

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
        Diagramme Mermaid invalide : {error}
      </div>
    );
  }
  return <div className="overflow-auto rounded-lg border border-slate-200 bg-white p-4 [&_svg]:mx-auto" dangerouslySetInnerHTML={{ __html: svg }} />;
}
