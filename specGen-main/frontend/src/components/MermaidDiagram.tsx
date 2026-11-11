import { useEffect, useId, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";
import { readLabel, renameLabel, type LabelTarget } from "../lib/mermaidLabels";

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

/** What was clicked in a drawn diagram: a node, an edge label or a subgraph title. */
function clickedLabel(svgRoot: HTMLElement, element: Element, renderId: string): { target: LabelTarget; box: Element } | null {
  const node = element.closest("g.node");
  if (node?.id.startsWith(`${renderId}-flowchart-`)) {
    return { target: { kind: "node", id: node.id.slice(renderId.length + "-flowchart-".length).replace(/-\d+$/, "") }, box: node };
  }
  const edge = element.closest("g.edgeLabel");
  if (edge) {
    const text = edge.textContent?.trim() ?? "";
    if (!text) return null;
    const same = [...svgRoot.querySelectorAll("g.edgeLabel")].filter((label) => label.textContent?.trim() === text);
    return { target: { kind: "edge", text, occurrence: same.indexOf(edge) }, box: edge };
  }
  const title = element.closest(".cluster-label");
  const cluster = title?.closest("g.cluster");
  if (title && cluster?.id.startsWith(`${renderId}-`)) {
    return { target: { kind: "subgraph", id: cluster.id.slice(renderId.length + 1) }, box: title };
  }
  return null;
}

interface LabelEditor {
  target: LabelTarget;
  value: string;
  left: number;
  top: number;
  error?: string;
}

/**
 * A drawn Mermaid diagram. With `onCodeChange`, clicking a box, an edge label or a group
 * title opens a field to rename it; the code is updated only if it still draws.
 */
export function MermaidDiagram({ code, onCodeChange }: { code: string; onCodeChange?: (code: string) => void }) {
  const id = `mermaid-${useId().replace(/:/g, "")}`;
  const [svg, setSvg] = useState("");
  const [error, setError] = useState("");
  const [editor, setEditor] = useState<LabelEditor | null>(null);
  const frame = useRef<HTMLDivElement>(null);
  const drawing = useRef<HTMLDivElement>(null);

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

  useEffect(() => setEditor(null), [code]);

  const openEditor = (event: MouseEvent) => {
    if (!onCodeChange || !drawing.current || !frame.current || !(event.target instanceof Element)) return;
    const clicked = clickedLabel(drawing.current, event.target, id);
    const value = clicked && readLabel(code, clicked.target);
    if (!clicked || value === null) return;
    const box = clicked.box.getBoundingClientRect();
    const origin = frame.current.getBoundingClientRect();
    setEditor({ target: clicked.target, value, left: box.left + box.width / 2 - origin.left, top: box.top + box.height / 2 - origin.top });
  };

  const applyEditor = async () => {
    if (!editor || !onCodeChange) return;
    const next = renameLabel(code, editor.target, editor.value);
    if (next === null || next === code) {
      setEditor(null);
      return;
    }
    const problem = await mermaidError(next);
    if (problem) setEditor({ ...editor, error: "Ce libellé empêche le schéma de s’afficher. Modifiez-le ou appuyez sur Échap." });
    else onCodeChange(next);
  };

  const onEditorKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      setEditor(null);
    } else if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void applyEditor();
    }
  };

  if (error) {
    return (
      <div className="rounded-lg border border-danger-soft bg-danger-soft p-3 text-sm text-danger-text">
        Diagramme Mermaid invalide : {error}
      </div>
    );
  }
  const clickable = onCodeChange
    ? " [&_.cluster-label]:cursor-pointer [&_.edgeLabel]:cursor-pointer [&_.node]:cursor-pointer [&_.cluster-label:hover]:opacity-60 [&_.edgeLabel:hover]:opacity-60 [&_.node:hover]:opacity-60"
    : "";
  // Fond papier blanc dans les deux thèmes : le diagramme garde le rendu de ses exports Word et HTML.
  return (
    <div ref={frame} className="relative">
      <div
        ref={drawing}
        onClick={openEditor}
        className={`overflow-auto rounded-lg border border-line bg-[#FFFFFF] p-4 [&_svg]:mx-auto${clickable}`}
        dangerouslySetInnerHTML={{ __html: svg }}
      />
      {editor && (
        <div
          className="absolute z-[6] flex w-64 -translate-x-1/2 -translate-y-1/2 flex-col gap-1.5 rounded-lg border border-line-strong bg-surface p-2 shadow-lg"
          style={{ left: editor.left, top: editor.top }}
        >
          <textarea
            autoFocus
            value={editor.value}
            onChange={(event) => setEditor({ ...editor, value: event.target.value, error: undefined })}
            onKeyDown={onEditorKey}
            onBlur={() => void applyEditor()}
            onFocus={(event) => event.currentTarget.select()}
            rows={Math.max(2, editor.value.split("\n").length)}
            aria-label="Libellé du schéma"
            className="input-area min-h-0 text-sm"
          />
          {editor.error ? (
            <p className="text-xs text-danger-text">{editor.error}</p>
          ) : (
            <p className="text-xs text-ink-subtle">Entrée pour valider, Maj+Entrée nouvelle ligne, Échap pour annuler.</p>
          )}
        </div>
      )}
    </div>
  );
}
