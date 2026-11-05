import type { ConnectionSettings, ConnectionTest, ContextResult, DocKind, Health, Language, MarkdownDoc, SettingsForm, SpecResult } from "./types";

async function parseError(response: Response): Promise<Error> {
  let detail = `Erreur ${response.status}`;
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") detail = payload.detail;
  } catch {
    // Non-JSON error body: keep the status message.
  }
  return new Error(detail);
}

async function request<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const response = await fetch(path, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export const api = {
  health: () => request<Health>("/api/health"),
  generateContext: (body: unknown) => request<ContextResult>("/api/context/generate", body),
  /** With `fix`, asks the model to correct a diagram that did not parse. */
  generateMermaid: (markdown: string, language: Language, fix?: { previous_code: string; error: string }) =>
    request<{ mermaid: string }>("/api/context/mermaid", { markdown, language, ...fix }),
  generateSpec: (body: unknown) => request<SpecResult>("/api/spec/generate", body),
  /** Translates a generated document (edits included) into the other language. */
  translate: (kind: DocKind, markdown: string, target_language: Language) =>
    request<{ markdown: string; warnings: string[]; language: Language; timings: { total: number } }>(`/api/translate/${kind}`, {
      markdown,
      target_language,
    }),
  settings: () => request<ConnectionSettings>("/api/settings"),
  saveSettings: (form: SettingsForm) => request<ConnectionSettings>("/api/settings", form, "PUT"),
  clearSettings: () => request<ConnectionSettings>("/api/settings", undefined, "DELETE"),
  testSettings: (form: SettingsForm) => request<ConnectionTest>("/api/settings/test", form),
  async uploadCertificate(file: File): Promise<ConnectionSettings> {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/api/settings/certificate", { method: "POST", body: form });
    if (!response.ok) throw await parseError(response);
    return response.json();
  },
  async convertDocument(file: File): Promise<{ name: string; markdown: string }> {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/api/markdown/convert", { method: "POST", body: form });
    if (!response.ok) throw await parseError(response);
    return response.json();
  },
};

export async function downloadExport(
  kind: DocKind,
  format: "md" | "html" | "docx",
  body: {
    markdown: string;
    language: Language;
    image_base64?: string;
    image_mime?: string;
    diagrams?: { code: string; png_base64: string }[];
  },
): Promise<void> {
  const response = await fetch(`/api/export/${kind}/${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`Export impossible (${response.status})`);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  saveBlob(await response.blob(), /filename="([^"]+)"/.exec(disposition)?.[1] ?? `${kind}.${format}`);
}

export async function downloadMarkdownBundle(documents: MarkdownDoc[]): Promise<void> {
  const response = await fetch("/api/markdown/bundle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ documents: documents.map(({ name, markdown }) => ({ name, markdown })) }),
  });
  if (!response.ok) throw new Error(`Export impossible (${response.status})`);
  saveBlob(await response.blob(), "markdown.zip");
}

export function downloadText(content: string, filename: string): void {
  saveBlob(new Blob([content], { type: "text/plain;charset=utf-8" }), filename);
}
