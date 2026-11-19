import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Check, ChevronDown, Download, RotateCcw } from "lucide-react";
import { downloadExport } from "../lib/api";
import { formatDateTime, headingKey, LANGUAGE_LABELS } from "../lib/files";
import type { DocKind, FeatureImage, Language } from "../lib/types";
import { useToast } from "./Toasts";
import { renderDiagramsForExport } from "./MermaidDiagram";
import { ConfirmDialog } from "./ConfirmDialog";

export interface ResultTab {
  id: string;
  label: string;
}

export function ResultCard({
  eyebrow,
  title,
  meta,
  metaAction,
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
  /** Shown right after the meta line, e.g. a link to restore the previous version. */
  metaAction?: ReactNode;
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
            <h2 className="break-words text-[30px] font-bold leading-tight text-ink">{title}</h2>
            <p className="mt-1.5 text-sm text-ink-muted">
              {meta}
              {metaAction && <> · {metaAction}</>}
            </p>
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
      <div data-result-body className="mt-6 border-t border-line px-6 pb-10 pt-8 sm:px-10">
        {children}
      </div>
    </div>
  );
}

interface DocumentResult {
  markdown: string;
  translatedAt?: string;
  generatedAt?: string;
  originalMarkdown?: string;
  editedAt?: string;
}

/** True when the user changed the generated document: edited in place or translated. */
export function isReworked(result: DocumentResult | null): boolean {
  if (!result) return false;
  return Boolean(result.translatedAt || (result.editedAt && result.originalMarkdown !== undefined && result.originalMarkdown !== result.markdown));
}

/** Link that swaps the document with the one it replaced at the last generation. */
export function RestorePreviousButton({ onRestore }: { onRestore: () => void }) {
  return (
    <button type="button" className="inline-flex items-center gap-1 font-medium text-accent underline hover:text-accent-ink" onClick={onRestore}>
      <RotateCcw className="h-3.5 w-3.5" aria-hidden />
      Restaurer la version précédente
    </button>
  );
}

/** Asks before a new generation replaces a document the user edited or translated. */
export function RegenerateConfirm({ open, what, onConfirm, onCancel }: { open: boolean; what: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <ConfirmDialog open={open} title={`Remplacer ${what} ?`} confirmLabel="Régénérer" onConfirm={onConfirm} onCancel={onCancel}>
      <p>Vous avez modifié ou traduit ce document. La nouvelle génération le remplacera.</p>
      <p className="mt-2">Vous pourrez revenir à la version actuelle avec « Restaurer la version précédente », sous le titre du document.</p>
    </ConfirmDialog>
  );
}

export function documentMeta(result: DocumentResult, language: Language): string {
  const edited = result.editedAt && result.originalMarkdown !== undefined && result.originalMarkdown !== result.markdown;
  return [
    `Généré le ${formatDateTime(result.generatedAt)}`,
    result.translatedAt && `traduit le ${formatDateTime(result.translatedAt)}`,
    edited && `modifié le ${formatDateTime(result.editedAt)}`,
    LANGUAGE_LABELS[language],
  ]
    .filter(Boolean)
    .join(" · ");
}

/** The result with the user's edit; the generated text is kept the first time. */
export function editedResult<T extends DocumentResult>(result: T, markdown: string): T {
  return { ...result, markdown, originalMarkdown: result.originalMarkdown ?? result.markdown, editedAt: new Date().toISOString() };
}

const EXPORT_FORMATS: { format: "docx" | "md" | "html"; label: string; detail: string }[] = [
  { format: "docx", label: "Word (.docx)", detail: "Mise en forme du modèle Word, schémas en images" },
  { format: "md", label: "Markdown (.md)", detail: "Texte brut, schémas gardés en code Mermaid" },
  { format: "html", label: "Page web (.html)", detail: "Fichier autonome, schémas en images" },
];

/** One « Exporter » button with a menu of the formats. */
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
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const frame = useRef<HTMLDivElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    if (!open) return;
    items.current[0]?.focus();
    const onPointer = (event: PointerEvent) => {
      if (!frame.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  const handleExport = async (format: "docx" | "md" | "html") => {
    setOpen(false);
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

  const onMenuKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = items.current.findIndex((item) => item === document.activeElement);
    const move = (to: number) => {
      event.preventDefault();
      items.current[(to + EXPORT_FORMATS.length) % EXPORT_FORMATS.length]?.focus();
    };
    if (event.key === "ArrowDown") move(index + 1);
    else if (event.key === "ArrowUp") move(index - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(EXPORT_FORMATS.length - 1);
    else if (event.key === "Escape" || event.key === "Tab") {
      setOpen(false);
      if (event.key === "Escape") frame.current?.querySelector<HTMLButtonElement>("button")?.focus();
    }
  };

  return (
    <div ref={frame} className="relative">
      <button
        type="button"
        className="btn-primary"
        disabled={busy !== null}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen(!open)}
      >
        <Download className="h-4 w-4" aria-hidden />
        {busy ? "Export…" : "Exporter"}
        <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label="Format d’export"
          onKeyDown={onMenuKey}
          className="absolute right-0 top-full z-20 mt-1.5 w-72 rounded-lg border border-line bg-surface p-1 shadow-[0_8px_24px_rgba(16,24,64,0.16)]"
        >
          {EXPORT_FORMATS.map((item, index) => (
            <button
              key={item.format}
              ref={(element) => (items.current[index] = element)}
              type="button"
              role="menuitem"
              tabIndex={-1}
              onClick={() => handleExport(item.format)}
              className="flex w-full flex-col items-start rounded-md px-3 py-2 text-left hover:bg-surface-3 focus:bg-surface-3 focus:outline-none"
            >
              <span className="text-sm font-medium text-ink">{item.label}</span>
              <span className="text-xs text-ink-muted">{item.detail}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Title of the document section a warning is about, when the document has that section. */
function warningSection(warning: string, headings: Map<string, string>): string | null {
  for (const match of warning.matchAll(/«\s*([^»]+?)\s*»/g)) {
    const heading = headings.get(headingKey(match[1]));
    if (heading) return heading;
  }
  return null;
}

function scrollToSection(from: HTMLElement, title: string) {
  const body = from.closest("[data-result-body]");
  const target = [...(body?.querySelectorAll<HTMLElement>("h1, h2, h3, h4") ?? [])].find((element) => headingKey(element.textContent ?? "") === headingKey(title));
  if (!target) return;
  target.style.scrollMarginTop = "calc(var(--chrome-h) + 24px)";
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

/**
 * Problems the backend still found in the generated document after its correction pass.
 * Each one links to its section when it names one, and can be marked as handled.
 */
export function WarningsPanel({
  warnings,
  markdown,
  resolved = [],
  onResolvedChange,
}: {
  warnings?: string[];
  markdown: string;
  resolved?: string[];
  onResolvedChange: (resolved: string[]) => void;
}) {
  if (!warnings?.length) return null;
  const headings = new Map<string, string>();
  for (const match of markdown.matchAll(/^#{1,4}\s+(.+?)\s*#*$/gm)) headings.set(headingKey(match[1]), match[1]);
  const open = warnings.filter((warning) => !resolved.includes(warning));
  const handled = warnings.length - open.length;

  if (!open.length) {
    return (
      <p className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-line bg-surface-2 p-3 text-sm text-ink-muted">
        <Check className="h-4 w-4 text-success" aria-hidden />
        {handled > 1 ? `Les ${handled} points à vérifier sont marqués comme traités.` : "Le point à vérifier est marqué comme traité."}
        <button type="button" className="font-medium text-accent underline hover:text-accent-ink" onClick={() => onResolvedChange([])}>
          Les réafficher
        </button>
      </p>
    );
  }

  return (
    <div className="mb-4 rounded-lg border border-warning-line bg-warning-soft p-3 text-sm text-warning-text">
      <p className="font-medium">Points à vérifier dans ce document</p>
      <ul className="mt-2 flex flex-col gap-2">
        {open.map((warning) => {
          const section = warningSection(warning, headings);
          return (
            <li key={warning} className="flex flex-wrap items-start gap-x-3 gap-y-1">
              <span className="min-w-0 flex-[1_1_320px]">{warning}</span>
              <span className="flex shrink-0 items-center gap-3">
                {section && (
                  <button
                    type="button"
                    className="font-medium underline hover:no-underline"
                    onClick={(event) => scrollToSection(event.currentTarget, section)}
                    title={`Aller à la section « ${section} »`}
                  >
                    Voir la section
                  </button>
                )}
                <button type="button" className="inline-flex items-center gap-1 font-medium underline hover:no-underline" onClick={() => onResolvedChange([...resolved, warning])}>
                  <Check className="h-3.5 w-3.5" aria-hidden /> Traité
                </button>
              </span>
            </li>
          );
        })}
      </ul>
      {handled > 0 && (
        <p className="mt-2 text-[13px]">
          {handled} point{handled > 1 ? "s" : ""} déjà traité{handled > 1 ? "s" : ""} ·{" "}
          <button type="button" className="underline hover:no-underline" onClick={() => onResolvedChange([])}>
            Tout réafficher
          </button>
        </p>
      )}
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

export function ProgressPanel({ title, steps, note, keepsRunning }: { title: string; steps: string[]; note?: string; keepsRunning?: boolean }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, []);

  // The backend does not report its progress: the steps are listed without pretending to know which one is running.
  return (
    <div className="flex min-h-[620px] flex-col items-center justify-center gap-3 rounded-xl border border-line bg-surface p-12 text-center" aria-live="polite">
      <svg className="h-14 w-14 animate-spin" viewBox="0 0 48 48" fill="none" aria-hidden>
        <circle cx="24" cy="24" r="20" className="stroke-accent-soft" strokeWidth="5" />
        <path d="M24 4a20 20 0 0 1 20 20" className="stroke-accent" strokeWidth="5" strokeLinecap="round" />
      </svg>
      <h2 className="mt-3 text-[22px] font-bold text-ink">{title}</h2>
      <p className="text-[15px] text-ink-muted" aria-live="off">
        {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")} écoulées · de 30 s à quelques minutes selon la taille des sources
      </p>
      <div className="mt-6 min-w-[300px] rounded-lg bg-surface-2 px-5 py-4 text-left">
        <p className="text-[13px] font-medium text-ink-muted">Ce que fait SpecGen pendant ce temps</p>
        <ul className="mt-2.5 flex flex-col gap-2">
          {steps.map((step) => (
            <li key={step} className="flex items-center gap-2.5 text-[15px] text-ink-body">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-ink-subtle" aria-hidden />
              {step}
            </li>
          ))}
        </ul>
      </div>
      {(keepsRunning || note) && (
        <p className="mt-4 max-w-[420px] text-[13px] leading-normal text-ink-subtle">
          {keepsRunning && "Vous pouvez changer d’onglet : la génération continue et l’onglet affiche une roue tant qu’elle n’est pas terminée."}
          {keepsRunning && note && " "}
          {note}
        </p>
      )}
    </div>
  );
}
