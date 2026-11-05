import { useRef, useState } from "react";
import { AlertCircle, ArrowRight, Check, Copy, Download, FileText, FileUp } from "lucide-react";
import { api, downloadMarkdownBundle, downloadText } from "../lib/api";
import { formatDateTime, formatSize } from "../lib/files";
import type { MarkdownDoc } from "../lib/types";
import { AddFileButton, Field, FileChip, LargeDropzone } from "./fields";
import { GenerateFooter, PageLayout } from "./Layout";
import { MarkdownPreview } from "./MarkdownPreview";
import { EmptyPanel, MarkdownEditor, ProgressPanel, ResultCard } from "./ResultCard";
import { useToast } from "./Toasts";

const ACCEPT = ".docx,.pdf,.pptx,.xlsx,.html,.htm,.txt,.drawio,.dio,.xml,.png,.svg";

export interface MarkdownState {
  docs: MarkdownDoc[];
  activeDocId: string | null;
}

interface SourceFile {
  id: string;
  file: File;
  status: "pending" | "converting" | "done" | "error";
  error?: string;
}

export function MarkdownPage({
  state,
  update,
  onUseInContext,
}: {
  state: MarkdownState;
  update: (patch: Partial<MarkdownState>) => void;
  onUseInContext: (docs: MarkdownDoc[]) => void;
}) {
  const toast = useToast();
  // Source files only live in memory: converted documents are what gets persisted.
  const [sources, setSources] = useState<SourceFile[]>([]);
  const [isConverting, setIsConverting] = useState(false);
  const [activeTab, setActiveTab] = useState("preview");
  const [copied, setCopied] = useState(false);
  const idCounter = useRef(0);

  const activeDoc = state.docs.find((doc) => doc.id === state.activeDocId) ?? state.docs[0] ?? null;
  const hasPending = sources.some((source) => source.status === "pending" || source.status === "error");
  const persistedOnly = state.docs.filter((doc) => !sources.some((source) => source.id === doc.id));

  const addFiles = (files: File[]) => {
    setSources((current) => [
      ...current,
      ...files.map((file) => ({ id: `src-${Date.now()}-${idCounter.current++}`, file, status: "pending" as const })),
    ]);
  };

  const removeSource = (id: string) => {
    setSources((current) => current.filter((source) => source.id !== id));
    removeDoc(id);
  };

  const removeDoc = (id: string) => {
    const docs = state.docs.filter((doc) => doc.id !== id);
    update({ docs, activeDocId: state.activeDocId === id ? (docs[0]?.id ?? null) : state.activeDocId });
  };

  const handleConvert = async () => {
    const targets = hasPending ? sources.filter((source) => source.status !== "done" && source.status !== "converting") : sources;
    if (!targets.length) return;
    setIsConverting(true);
    let docs = [...state.docs];
    let lastConverted: string | null = null;
    for (const target of targets) {
      setSources((current) => current.map((source) => (source.id === target.id ? { ...source, status: "converting" } : source)));
      try {
        const result = await api.convertDocument(target.file);
        const doc: MarkdownDoc = {
          id: target.id,
          name: result.name,
          sourceName: target.file.name,
          markdown: result.markdown,
          convertedAt: new Date().toISOString(),
        };
        docs = [...docs.filter((existing) => existing.id !== target.id), doc];
        lastConverted = target.id;
        setSources((current) => current.map((source) => (source.id === target.id ? { ...source, status: "done", error: undefined } : source)));
      } catch (error) {
        const message = (error as Error).message;
        setSources((current) => current.map((source) => (source.id === target.id ? { ...source, status: "error", error: message } : source)));
        toast("error", message);
      }
    }
    update({ docs, activeDocId: lastConverted ?? state.activeDocId });
    setIsConverting(false);
    if (lastConverted) toast("success", targets.length > 1 ? "Documents convertis en Markdown." : "Document converti en Markdown.");
  };

  const updateActiveMarkdown = (markdown: string) => {
    if (!activeDoc) return;
    update({ docs: state.docs.map((doc) => (doc.id === activeDoc.id ? { ...doc, markdown } : doc)) });
  };

  const handleCopy = async () => {
    if (!activeDoc) return;
    try {
      await navigator.clipboard.writeText(activeDoc.markdown);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast("error", "Copie impossible dans ce navigateur.");
    }
  };

  const handleDownloadAll = async () => {
    try {
      await downloadMarkdownBundle(state.docs);
    } catch (error) {
      toast("error", (error as Error).message);
    }
  };

  const hasAnything = sources.length > 0 || state.docs.length > 0;
  const footerLabel = hasPending || !state.docs.length ? "Convertir" : "Convertir à nouveau";
  const disabledReason = !sources.length ? (state.docs.length ? "Ajoutez un document pour lancer une nouvelle conversion." : "Ajoutez au moins un document pour lancer la conversion.") : null;

  return (
    <PageLayout
      title="Convertir en Markdown"
      description="Importez un document : il sera converti en Markdown, réutilisable comme source de contexte."
      fields={
        <Field
          label="Document(s) à convertir"
          hint={!hasAnything ? "Plusieurs fichiers ? Chacun est converti séparément. Les schémas draw.io (.drawio, ou PNG / SVG exportés avec le schéma inclus) gardent le sens de leurs flèches." : undefined}
        >
          {!hasAnything ? (
            <LargeDropzone accept={ACCEPT} multiple formats="DOCX, PDF, PPTX, XLSX, HTML, TXT, schémas draw.io · 200 Mo max par fichier" onFiles={addFiles} />
          ) : (
            <>
              {persistedOnly.map((doc) => (
                <FileChip
                  key={doc.id}
                  icon={<FileText className="h-[22px] w-[22px]" strokeWidth={1.8} />}
                  name={doc.sourceName}
                  detail={
                    <>
                      <Check className="h-3 w-3" strokeWidth={3} aria-hidden /> Converti
                    </>
                  }
                  detailTone="success"
                  onRemove={() => removeDoc(doc.id)}
                />
              ))}
              {sources.map((source) => (
                <FileChip
                  key={source.id}
                  icon={<FileText className="h-[22px] w-[22px]" strokeWidth={1.8} />}
                  name={source.file.name}
                  detailTone={source.status === "done" ? "success" : source.status === "error" ? "error" : "muted"}
                  detail={
                    source.status === "done" ? (
                      <>
                        <Check className="h-3 w-3" strokeWidth={3} aria-hidden /> Converti
                      </>
                    ) : source.status === "error" ? (
                      <>
                        <AlertCircle className="h-3 w-3" aria-hidden /> Échec de la conversion
                      </>
                    ) : source.status === "converting" ? (
                      "Conversion en cours…"
                    ) : (
                      `En attente · ${formatSize(source.file.size)}`
                    )
                  }
                  onRemove={source.status === "converting" ? undefined : () => removeSource(source.id)}
                />
              ))}
              <AddFileButton label="Ajouter un document" accept={ACCEPT} multiple onFiles={addFiles} />
            </>
          )}
        </Field>
      }
      footer={
        <GenerateFooter label={footerLabel} busyLabel="Conversion en cours…" isBusy={isConverting} disabledReason={disabledReason} onClick={handleConvert} />
      }
    >
      {isConverting && !activeDoc ? (
        <ProgressPanel title="Conversion en cours" steps={["Lecture du document", "Extraction du texte et de la structure", "Mise en forme Markdown"]} />
      ) : activeDoc ? (
        <ResultCard
          title={activeDoc.name}
          meta={`Converti le ${formatDateTime(activeDoc.convertedAt)} · depuis ${activeDoc.sourceName}`}
          cta={
            <button type="button" className="btn-soft" onClick={() => onUseInContext(state.docs)}>
              Utiliser pour créer un contexte <ArrowRight className="h-4 w-4" aria-hidden />
            </button>
          }
          tabs={[
            { id: "preview", label: "Aperçu" },
            { id: "raw", label: "Markdown brut" },
          ]}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          actions={
            <>
              <button type="button" className="btn-secondary" onClick={handleCopy}>
                {copied ? <Check className="h-4 w-4 text-success" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />}
                {copied ? "Copié" : "Copier"}
              </button>
              {state.docs.length > 1 && (
                <button type="button" className="btn-secondary" onClick={handleDownloadAll}>
                  Tout télécharger (.zip)
                </button>
              )}
              <button type="button" className="btn-primary" onClick={() => downloadText(activeDoc.markdown, activeDoc.name)}>
                <Download className="h-4 w-4" aria-hidden /> Télécharger le Markdown
              </button>
            </>
          }
        >
          {state.docs.length > 1 && (
            <div role="tablist" aria-label="Documents convertis" className="-mt-2 mb-6 flex flex-wrap gap-2">
              {state.docs.map((doc) => (
                <button
                  key={doc.id}
                  type="button"
                  role="tab"
                  aria-selected={doc.id === activeDoc.id}
                  onClick={() => update({ activeDocId: doc.id })}
                  className={`rounded-full border px-3 py-1.5 text-[13px] font-medium transition ${
                    doc.id === activeDoc.id ? "border-accent bg-navy-softer text-accent" : "border-line-strong text-ink-muted hover:border-ink-subtle"
                  }`}
                >
                  {doc.name}
                </button>
              ))}
            </div>
          )}
          {activeTab === "preview" ? <MarkdownPreview markdown={activeDoc.markdown} /> : <MarkdownEditor value={activeDoc.markdown} onChange={updateActiveMarkdown} />}
        </ResultCard>
      ) : (
        <EmptyPanel icon={<FileUp className="h-[30px] w-[30px]" strokeWidth={1.6} />} title="Aucun document converti">
          <p className="max-w-[460px] text-[15px] leading-relaxed text-ink-muted">
            Le résultat apparaîtra ici : un aperçu mis en forme et le Markdown brut, prêts à être téléchargés ou envoyés directement à l’étape « Créer un contexte ».
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-3">
            {["Importer", "Vérifier l’aperçu", "Télécharger ou réutiliser"].map((label, index) => (
              <span key={label} className="flex items-center gap-2 rounded-full bg-surface-3 px-3.5 py-2 text-[13px] text-ink-body">
                <span className="font-bold text-accent">{index + 1}</span>
                {label}
              </span>
            ))}
          </div>
        </EmptyPanel>
      )}
    </PageLayout>
  );
}
