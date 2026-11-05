import type { FeatureImage, LoadedFile } from "./types";

export async function readTextFile(file: File): Promise<LoadedFile> {
  return { name: file.name, size: file.size, content: await file.text() };
}

export async function readJsonFile(file: File): Promise<LoadedFile> {
  const text = await file.text();
  try {
    return { name: file.name, size: file.size, content: JSON.parse(text) };
  } catch (error) {
    throw new Error(`${file.name} : JSON invalide (${(error as Error).message})`);
  }
}

export function readImageFile(file: File): Promise<FeatureImage> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = String(reader.result);
      resolve({ name: file.name, mime: file.type || "image/png", base64: dataUrl.split(",")[1] ?? "" });
    };
    reader.onerror = () => reject(new Error(`${file.name} : image illisible`));
    reader.readAsDataURL(file);
  });
}

export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / 1024 / 1024).toFixed(1)} Mo`;
}

export function documentTitle(markdown: string, fallback: string): string {
  return /^#\s+(.+)$/m.exec(markdown)?.[1]?.trim() || fallback;
}

export function stripTitle(markdown: string): string {
  return markdown.replace(/^#\s+.+$/m, "").trim();
}

export function formatDateTime(iso: string | undefined): string {
  const date = iso ? new Date(iso) : new Date();
  return `${date.toLocaleDateString("fr-FR")} à ${date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

export const LANGUAGE_LABELS = { fr: "Français", en: "English" } as const;

/** Models sometimes wrap the whole document in ```markdown … ```: keep only the document. */
export function unwrapMarkdownFence(markdown: string): string {
  const outer = /^\s*```(?:markdown|md)?[ \t]*\n([\s\S]*?)\n```\s*$/i.exec(markdown);
  return outer ? `${outer[1].trim()}\n` : markdown;
}

const HTML_BREAK = /(?:\s*<\s*br\s*\/?\s*>\s*)+/gi;
const CELL_BULLET = /^[-*•–]\s+/;

/**
 * Same rule as remove_html_breaks in the backend: `<br>` in a table cell becomes a semicolon,
 * elsewhere a line break. Code blocks (Mermaid labels use `<br/>`) are kept.
 */
export function removeHtmlBreaks(markdown: string, language: "fr" | "en" = "fr"): string {
  if (!/<\s*br/i.test(markdown)) return markdown;
  const separator = language === "fr" ? " ; " : "; ";
  const out: string[] = [];
  let fence: string | null = null;
  for (const line of markdown.split("\n")) {
    const marker = /^\s*(```|~~~)/.exec(line);
    if (fence) {
      out.push(line);
      if (marker && marker[1] === fence) fence = null;
      continue;
    }
    if (marker) {
      fence = marker[1];
      out.push(line);
      continue;
    }
    if (!/<\s*br\s*\/?\s*>/i.test(line)) {
      out.push(line);
    } else if (line.trimStart().startsWith("|")) {
      out.push(
        line
          .split("|")
          .map((cell) => {
            if (!/<\s*br\s*\/?\s*>/i.test(cell)) return cell;
            const parts = cell.split(HTML_BREAK).map((part) => part.trim().replace(CELL_BULLET, "")).filter(Boolean);
            return parts.length ? ` ${parts.join(separator)} ` : " ";
          })
          .join("|"),
      );
    } else {
      const indent = /^\s*/.exec(line)?.[0] ?? "";
      for (const part of line.trim().split(HTML_BREAK)) if (part.trim()) out.push(indent + part.trim());
    }
  }
  return out.join("\n");
}

/** Cleanup applied to every generated document: outer ```markdown fence, then `<br>` tags. */
export function cleanGeneratedMarkdown(markdown: string, language: "fr" | "en" = "fr"): string {
  return removeHtmlBreaks(unwrapMarkdownFence(markdown), language);
}
