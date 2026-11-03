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
