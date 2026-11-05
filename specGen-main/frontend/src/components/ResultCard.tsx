import { useEffect, useState, type ReactNode } from "react";
import { Check, Download, Languages } from "lucide-react";
import { api, downloadExport } from "../lib/api";
import { formatDateTime, LANGUAGE_LABELS } from "../lib/files";
import type { DocKind, FeatureImage, Language } from "../lib/types";
import { useToast } from "./Toasts";
import { mermaidError, renderDiagramsForExport } from "./MermaidDiagram";

export interface ResultTab {
  id: string;
  label: string;
}

export function ResultCard({
  eyebrow,
  title,
  meta,
  cta,
  tabs,
  activeTab,
  onTabChange,
  actions,
  children,
}: {
  eyebrow?: string;
  title: string;
  meta: string;
  cta?: ReactNode;
  /** No tab bar when there is a single view. */
  tabs?: ResultTab[];
  activeTab?: string;
  onTabChange?: (id: string) => void;
  actions: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface shadow-[0_1px_3px_rgba(16,24,64,0.06)]">
      <div className="flex flex-col gap-5 px-6 pt-8 sm:px-10">
        <div className="flex flex-wrap items-start gap-4">
          <div className="min-w-0 flex-[1_1_320px]">
            {eyebrow && <p className="mb-1 text-[13px] font-medium uppercase tracking-[0.04em] text-ink-muted">{eyebrow}</p>}
            <h2 className="break-words text-[30px] font-bold leading-tight text-accent">{title}</h2>
            <p className="mt-1.5 text-sm text-ink-muted">{meta}</p>
          </div>
          {cta}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {tabs && tabs.length > 1 && (
            <div role="tablist" aria-label="Affichage" className="flex flex-wrap rounded-lg bg-surface-3 p-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  aria-selected={tab.id === activeTab}
                  onClick={() => onTabChange?.(tab.id)}
                  className={`min-h-[36px] rounded-md px-4 text-sm font-medium transition ${
                    tab.id === activeTab ? "bg-navy text-white" : "text-ink-body hover:text-ink"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          )}
          <div className="ml-auto flex flex-wrap gap-2">{actions}</div>
        </div>
      </div>
      <div className="mt-6 border-t border-line px-6 pb-10 pt-8 sm:px-10">{children}</div>
    </div>
  );
}

interface DocumentResult {
  markdown: string;
  warnings?: string[];
  language?: Language;
  generatedAt?: string;
  originalMarkdown?: string;
  editedAt?: string;
}

export function documentMeta(result: DocumentResult, language: Language): string {
  const edited = result.editedAt && result.originalMarkdown !== undefined && result.originalMarkdown !== result.markdown;
  return [`Généré le ${formatDateTime(result.generatedAt)}`, edited && `modifié le ${formatDateTime(result.editedAt)}`, LANGUAGE_LABELS[language]]
    .filter(Boolean)
    .join(" · ");
}

/** The result with the user's edit; the generated text is kept the first time. */
export function editedResult<T extends DocumentResult>(result: T, markdown: string): T {
  return { ...result, markdown, originalMarkdown: result.originalMarkdown ?? result.markdown, editedAt: new Date().toISOString() };
}

export function ExportButtons({
  kind,
  markdown,
  language,
  image,
}: {
  kind: DocKind;
  markdown: string;
  language: Language;
  image?: FeatureImage | null;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  const handleExport = async (format: "docx" | "md" | "html") => {
    setBusy(format);
    try {
      // Word and HTML get the Mermaid diagrams as images; the Markdown export keeps their code.
      const diagrams = format === "md" ? [] : await renderDiagramsForExport(markdown);
      await downloadExport(kind, format, { markdown, language, image_base64: image?.base64, image_mime: image?.mime, diagrams });
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <>
      <button type="button" className="btn-primary" disabled={busy !== null} onClick={() => handleExport("docx")}>
        <Download className="h-4 w-4" aria-hidden />
        {busy === "docx" ? "Export…" : "DOCX"}
      </button>
      <button type="button" className="btn-secondary" disabled={busy !== null} onClick={() => handleExport("md")}>
        {busy === "md" ? "Export…" : "Markdown"}
      </button>
      <button type="button" className="btn-secondary" disabled={busy !== null} onClick={() => handleExport("html")}>
        {busy === "html" ? "Export…" : "HTML"}
      </button>
    </>
  );
}

const MERMAID_BLOCK = /```mermaid\n[\s\S]*?\n```/g;

/** A translated diagram that no longer parses is replaced by the original one, at the same place. */
async function keepValidDiagrams(translated: string, source: string): Promise<string> {
  const originals = source.match(MERMAID_BLOCK) ?? [];
  const blocks = translated.match(MERMAID_BLOCK) ?? [];
  const fixed = await Promise.all(
    blocks.map(async (block, index) => {
      const code = block.slice("```mermaid\n".length, -"\n```".length);
      return (await mermaidError(code)) && originals[index] ? originals[index] : block;
    }),
  );
  let index = 0;
  return translated.replace(MERMAID_BLOCK, () => fixed[index++]);
}

/** Translates the document into the other language, after generation (edits included). */
export function TranslateButton<T extends DocumentResult>({
  kind,
  result,
  language,
  disabledReason,
  onTranslated,
}: {
  kind: DocKind;
  result: T;
  language: Language;
  disabledReason?: string | null;
  onTranslated: (result: T, language: Language) => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const target: Language = language === "fr" ? "en" : "fr";

  const handleTranslate = async () => {
    setBusy(true);
    try {
      const translated = await api.translate(result.markdown, kind, language, target);
      const markdown = await keepValidDiagrams(translated.markdown, result.markdown);
      // The translation becomes the reference version: "Version générée" goes back to it.
      onTranslated({ ...result, markdown, warnings: translated.warnings, language: target, originalMarkdown: undefined, editedAt: undefined }, target);
      toast("success", `Document traduit en ${target === "en" ? "anglais" : "français"} en ${translated.duration} s.`);
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      className="btn-secondary"
      disabled={busy || Boolean(disabledReason)}
      title={disabledReason ?? undefined}
      onClick={handleTranslate}
    >
      <Languages className="h-4 w-4" aria-hidden />
      {busy ? "Traduction…" : target === "en" ? "Traduire en anglais" : "Traduire en français"}
    </button>
  );
}

/** Problems the backend still found in the generated document after its correction pass. */
export function WarningsPanel({ warnings }: { warnings?: string[] }) {
  if (!warnings?.length) return null;
  return (
    <div className="mb-4 rounded-lg border border-warning-line bg-warning-soft p-3 text-sm text-warning-text">
      <p className="font-medium">Points à vérifier dans ce document</p>
      <ul className="mt-1 list-disc pl-5">
        {warnings.map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
    </div>
  );
}

export function MarkdownEditor({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <p className="hint">Les modifications sont prises en compte dans l’aperçu et dans les exports.</p>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck={false}
        aria-label="Contenu Markdown du document"
        className="input-area min-h-[60vh] resize-y font-mono text-[13px] leading-relaxed"
      />
    </div>
  );
}

export function EmptyPanel({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="flex min-h-[560px] flex-col items-center justify-center gap-4 rounded-xl border border-line bg-surface p-12 text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-[14px] bg-navy-soft text-accent">{icon}</span>
      <h2 className="text-[22px] font-bold text-ink">{title}</h2>
      {children}
    </div>
  );
}

export function ProgressPanel({ title, steps, note }: { title: string; steps: string[]; note?: string }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);

  // The backend does not stream progress: steps advance on elapsed time.
  const activeStep = Math.min(steps.length - 1, Math.floor(elapsed / 8));

  return (
    <div className="flex min-h-[620px] flex-col items-center justify-center gap-3 rounded-xl border border-line bg-surface p-12 text-center" aria-live="polite">
      <svg className="h-14 w-14 animate-spin" viewBox="0 0 48 48" fill="none" aria-hidden>
        <circle cx="24" cy="24" r="20" className="stroke-accent-soft" strokeWidth="5" />
        <path d="M24 4a20 20 0 0 1 20 20" className="stroke-accent" strokeWidth="5" strokeLinecap="round" />
      </svg>
      <h2 className="mt-3 text-[22px] font-bold text-ink">{title}</h2>
      <p className="text-[15px] text-ink-muted">
        {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} écoulées · de 30 s à quelques minutes selon la taille des sources
      </p>
      <ol className="mt-7 flex min-w-[300px] flex-col gap-3.5 text-left">
        {steps.map((step, index) => (
          <li
            key={step}
            className={`flex items-center gap-3 text-[15px] ${
              index < activeStep ? "text-ink" : index === activeStep ? "font-medium text-accent" : "text-ink-subtle"
            }`}
          >
            {index < activeStep ? (
              <span className="flex h-[22px] w-[22px] items-center justify-center rounded-full bg-success">
                <Check className="h-3 w-3 text-surface" strokeWidth={3.5} aria-hidden />
              </span>
            ) : index === activeStep ? (
              <span className="flex h-[22px] w-[22px] items-center justify-center rounded-full border-2 border-accent">
                <span className="h-2 w-2 rounded-full bg-navy" />
              </span>
            ) : (
              <span className="h-[22px] w-[22px] rounded-full border-2 border-line-strong" />
            )}
            {step}
          </li>
        ))}
      </ol>
      {note && <p className="mt-7 max-w-[420px] text-[13px] leading-normal text-ink-subtle">{note}</p>}
    </div>
  );
}
