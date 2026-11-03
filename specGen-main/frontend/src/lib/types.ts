export type Language = "fr" | "en";
export type DocKind = "context" | "spec";
export type Page = "home" | "markdown" | "context" | "spec" | "settings";

export interface LoadedFile {
  name: string;
  size: number;
  content: unknown;
  /** Set when the file was produced by another step (e.g. the Markdown conversion). */
  origin?: "conversion";
}

export interface FeatureImage {
  name: string;
  mime: string;
  base64: string;
}

export interface MarkdownDoc {
  id: string;
  name: string;
  sourceName: string;
  markdown: string;
  convertedAt: string;
}

export interface Health {
  configured: boolean;
  missing: string[];
  model: string;
}

export type SettingsField = "api_base" | "api_key" | "ca_bundle" | "model" | "timeout";

export interface ConnectionTest {
  ok: boolean;
  field: "api_base" | "api_key" | "certificate" | null;
  title: string;
  message: string;
  at: string;
  model?: string;
}

export interface ConnectionSettings {
  configured: boolean;
  missing: string[];
  env_fields: SettingsField[];
  env_file: string | null;
  storage_dir: string;
  api_base: string;
  has_api_key: boolean;
  api_key_hint: string;
  certificate: { name: string; imported_at?: string; expires_at?: string } | null;
  model: string;
  timeout: number;
  last_test: ConnectionTest | null;
}

export interface SettingsForm {
  api_base: string;
  api_key: string | null;
  model: string;
  timeout: number;
}

export interface ComponentScope {
  scope: string;
  label: string;
  rationale: string;
}

export interface ContextResult {
  markdown: string;
  journey_markdown: string;
  journey_mermaid: string;
  retried_light: boolean;
  /** Problems still found after the correction pass (missing headings, tables…). */
  warnings?: string[];
  corrected?: boolean;
  timings: { analysis: number; llm: number; total: number };
  generatedAt?: string;
}

export interface SpecResult {
  markdown: string;
  /** Problems still found after the correction pass (missing headings, components absent from the JSON…). */
  warnings?: string[];
  corrected?: boolean;
  inventory?: boolean;
  scope: ComponentScope;
  timings: { total: number };
  generatedAt?: string;
}
