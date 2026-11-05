import { useEffect, useId, useState } from "react";

// Mermaid is heavy: load it only when a diagram is actually displayed.
let mermaidLoader: Promise<typeof import("mermaid").default> | null = null;
function loadMermaid() {
  mermaidLoader ??= import("mermaid").then(({ default: mermaid }) => {
    // SVG text labels (no HTML labels): the diagrams can then be turned into images for the exports.
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "neutral",
      fontFamily: "Inter, sans-serif",
      htmlLabels: false,
      flowchart: { htmlLabels: false },
    });
    return mermaid;
  });
  return mermaidLoader;
}

/** The parser's error message, or null when the code is valid Mermaid. */
export async function mermaidError(code: string): Promise<string | null> {
  try {
    const mermaid = await loadMermaid();
    await mermaid.parse(code);
    return null;
  } catch (error) {
    return error instanceof Error ? error.message : String(error);
  }
}

let exportCount = 0;

/** A Mermaid diagram as a PNG (base64, no data: prefix), drawn at twice its size for print. */
export async function mermaidToPng(code: string): Promise<string> {
  const mermaid = await loadMermaid();
  const { svg } = await mermaid.render(`mermaid-export-${exportCount++}`, code);
  const parsed = new DOMParser().parseFromString(svg, "image/svg+xml").documentElement;
  const [, , width, height] = (parsed.getAttribute("viewBox") ?? "0 0 800 600").split(/[\s,]+/).map(Number);
  parsed.setAttribute("width", String(width));
  parsed.setAttribute("height", String(height));
  parsed.removeAttribute("style");
  const source = new XMLSerializer().serializeToString(parsed);

  const image = new Image();
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(source)}`;
  await image.decode();
  const scale = 2;
  const canvas = document.createElement("canvas");
  canvas.width = Math.ceil(width * scale);
  canvas.height = Math.ceil(height * scale);
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas indisponible");
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/png").split(",")[1];
}

/** The ```mermaid blocks of a document drawn as images, for the Word and HTML exports. */
export async function renderDiagramsForExport(markdown: string): Promise<{ code: string; png_base64: string }[]> {
  const diagrams: { code: string; png_base64: string }[] = [];
  for (const match of markdown.matchAll(/^```mermaid[ \t]*\n([\s\S]*?)\n```[ \t]*$/gm)) {
    const code = match[1].trim();
    if (!code || diagrams.some((diagram) => diagram.code === code)) continue;
    try {
      diagrams.push({ code, png_base64: await mermaidToPng(code) });
    } catch {
      // An invalid diagram stays as code in the export.
    }
  }
  return diagrams;
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
      <div className="rounded-lg border border-danger-soft bg-danger-soft p-3 text-sm text-danger-text">
        Diagramme Mermaid invalide : {error}
      </div>
    );
  }
  // Fond papier blanc dans les deux thèmes : le diagramme garde le rendu de ses exports Word et HTML.
  return <div className="overflow-auto rounded-lg border border-line bg-[#FFFFFF] p-4 [&_svg]:mx-auto" dangerouslySetInnerHTML={{ __html: svg }} />;
}
