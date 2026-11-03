import { useState } from "react";
import { ArrowRight, Download, FileText, Layers, Wand2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, downloadText } from "../lib/api";
import { documentTitle, formatDateTime, formatSize, LANGUAGE_LABELS, readJsonFile, readTextFile, stripTitle } from "../lib/files";
import type { ContextResult, Language, LoadedFile } from "../lib/types";
import { AddFileButton, Field, FileChip, LanguageField, LargeDropzone } from "./fields";
import { GenerateFooter, PageLayout } from "./Layout";
import { MarkdownPreview } from "./MarkdownPreview";
import { MermaidDiagram, mermaidError } from "./MermaidDiagram";
import { EmptyPanel, ExportButtons, ProgressPanel, ResultCard } from "./ResultCard";
import { ComponentLibraryField, JsonIcon } from "./shared";
import { useToast } from "./Toasts";

export interface ContextState {
  markdownFiles: LoadedFile[];
  jsonFiles: LoadedFile[];
  language: Language;
  result: ContextResult | null;
  flowMermaid: string;
}

export function ContextPage({
  state,
  update,
  componentLibrary,
  onComponentLibraryChange,
  llmReady,
  onUseInSpec,
}: {
  state: ContextState;
  update: (patch: Partial<ContextState>) => void;
  componentLibrary: LoadedFile | null;
  onComponentLibraryChange: (file: LoadedFile | null) => void;
  llmReady: boolean;
  onUseInSpec: () => void;
}) {
  const toast = useToast();
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingFlow, setIsGeneratingFlow] = useState(false);
  const [activeTab, setActiveTab] = useState("preview");
  const result = state.result;
  const hasSource = state.markdownFiles.length > 0 || state.jsonFiles.length > 0;

  const addFiles = async (files: File[], reader: (file: File) => Promise<LoadedFile>, key: "markdownFiles" | "jsonFiles") => {
    const loaded: LoadedFile[] = [];
    for (const file of files) {
      try {
        loaded.push(await reader(file));
      } catch (error) {
        toast("error", (error as Error).message);
      }
    }
    if (loaded.length) update({ [key]: [...state[key], ...loaded] });
  };

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const generated = await api.generateContext({
        markdown_sources: state.markdownFiles,
        json_sources: state.jsonFiles,
        component_library: componentLibrary?.content ?? null,
        language: state.language,
      });
      update({ result: { ...generated, generatedAt: new Date().toISOString() }, flowMermaid: "" });
      setActiveTab("preview");
      toast(
        generated.retried_light ? "info" : "success",
        generated.retried_light
          ? "Contexte généré après une nouvelle tentative en mode allégé (délai dépassé)."
          : `Document de contexte généré en ${generated.timings.total} s.`,
      );
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleGenerateFlow = async () => {
    if (!result) return;
    setIsGeneratingFlow(true);
    try {
      let { mermaid } = await api.generateMermaid(result.markdown, state.language);
      const error = await mermaidError(mermaid);
      if (error) {
        // One correction round with the parser's message; keep the first version if it is no better.
        const fixed = await api.generateMermaid(result.markdown, state.language, { previous_code: mermaid, error });
        if (!(await mermaidError(fixed.mermaid))) mermaid = fixed.mermaid;
      }
      update({ flowMermaid: mermaid });
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setIsGeneratingFlow(false);
    }
  };

  const fileChips = (key: "markdownFiles" | "jsonFiles", icon: JSX.Element) =>
    state[key].map((file, index) => (
      <FileChip
        key={`${file.name}-${index}`}
        icon={icon}
        name={file.name}
        detail={file.origin === "conversion" ? `Issu de la conversion · ${formatSize(file.size)}` : formatSize(file.size)}
        onRemove={() => update({ [key]: state[key].filter((_, i) => i !== index) })}
      />
    ));

  const markdownIcon = <FileText className="h-[22px] w-[22px]" strokeWidth={1.8} />;

  return (
    <PageLayout
      title="Créer un contexte"
      description="Sélectionnez les sources. Au moins un Markdown ou un JSON est requis."
      fields={
        <>
          <Field label="Markdown(s) de contexte projet" hint={state.markdownFiles.length ? "Plusieurs fichiers .md sont agrégés automatiquement." : undefined}>
            {state.markdownFiles.length ? (
              <>
                {fileChips("markdownFiles", markdownIcon)}
                <AddFileButton label="Ajouter un fichier .md" accept=".md,.markdown" multiple onFiles={(files) => addFiles(files, readTextFile, "markdownFiles")} />
              </>
            ) : (
              <LargeDropzone accept=".md,.markdown" multiple formats="MD, MARKDOWN · 200 Mo max par fichier" onFiles={(files) => addFiles(files, readTextFile, "markdownFiles")} />
            )}
          </Field>

          <Field label="JSON global de l’application">
            {state.jsonFiles.length ? (
              <>
                {fileChips("jsonFiles", <JsonIcon />)}
                <AddFileButton label="Ajouter un fichier .json" accept=".json" multiple onFiles={(files) => addFiles(files, readJsonFile, "jsonFiles")} />
              </>
            ) : (
              <LargeDropzone accept=".json" multiple formats="JSON · 200 Mo max par fichier" onFiles={(files) => addFiles(files, readJsonFile, "jsonFiles")} />
            )}
          </Field>

          <ComponentLibraryField file={componentLibrary} onChange={onComponentLibraryChange} sharedWith="Générer une spécification" />

          <LanguageField value={state.language} onChange={(language) => update({ language })} />
        </>
      }
      footer={
        <GenerateFooter
          label={result ? "Régénérer le contexte" : "Générer le contexte"}
          busyLabel="Génération en cours…"
          isBusy={isGenerating}
          disabledReason={!llmReady ? "Configuration LLM incomplète : génération désactivée." : !hasSource ? "Ajoutez au moins un Markdown ou un JSON pour continuer." : null}
          onClick={handleGenerate}
        />
      }
    >
      {isGenerating ? (
        <ProgressPanel
          title="Génération du document de contexte"
          steps={["Lecture et agrégation des sources", "Analyse de la structure et des parcours", "Rédaction par l’IA", "Mise en forme du document"]}
          note="En cas de délai dépassé, une nouvelle tentative en mode allégé est lancée automatiquement."
        />
      ) : result ? (
        <ResultCard
          eyebrow={state.language === "en" ? "UX Architecture · Global application context" : "Architecture UX · Contexte global application"}
          title={documentTitle(result.markdown, state.language === "en" ? "UX Architecture / Project overview" : "Architecture UX / Project overview")}
          meta={`Généré le ${formatDateTime(result.generatedAt)} · ${LANGUAGE_LABELS[state.language]}`}
          cta={
            <button type="button" className="btn-soft" onClick={onUseInSpec}>
              Utiliser pour la spécification <ArrowRight className="h-4 w-4" aria-hidden />
            </button>
          }
          tabs={[
            { id: "preview", label: "Aperçu" },
            { id: "journeys", label: "Parcours utilisateur" },
          ]}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          actions={<ExportButtons kind="context" markdown={result.markdown} language={state.language} />}
        >
          {activeTab === "preview" && <MarkdownPreview markdown={stripTitle(result.markdown)} />}
          {activeTab === "journeys" && (
            <div className="flex flex-col gap-10">
              <section>
                <div className="mb-4 flex flex-wrap items-center gap-3">
                  <div className="flex-1">
                    <h3 className="text-lg font-bold text-ink">Schéma du parcours</h3>
                    <p className="text-sm text-ink-muted">Diagramme généré par l’IA à partir du document de contexte.</p>
                  </div>
                  {state.flowMermaid && (
                    <button type="button" className="btn-secondary" onClick={() => downloadText(state.flowMermaid, "parcours.mmd")}>
                      <Download className="h-4 w-4" aria-hidden /> .mmd
                    </button>
                  )}
                  <button type="button" className="btn-primary" onClick={handleGenerateFlow} disabled={!llmReady || isGeneratingFlow}>
                    <Wand2 className="h-4 w-4" aria-hidden />
                    {isGeneratingFlow ? "Génération…" : state.flowMermaid ? "Régénérer le schéma" : "Générer le schéma"}
                  </button>
                </div>
                {state.flowMermaid ? (
                  <>
                    <MermaidDiagram code={state.flowMermaid} />
                    <details className="mt-3">
                      <summary className="cursor-pointer text-sm font-medium text-ink-muted hover:text-ink">Modifier le code Mermaid</summary>
                      <textarea
                        value={state.flowMermaid}
                        onChange={(event) => update({ flowMermaid: event.target.value })}
                        spellCheck={false}
                        aria-label="Code Mermaid du parcours"
                        className="input-area mt-2 h-56 font-mono text-[13px]"
                      />
                    </details>
                  </>
                ) : (
                  <p className="rounded-lg border border-dashed border-line-dashed p-6 text-center text-sm text-ink-subtle">Aucun schéma pour le moment.</p>
                )}
              </section>
              {result.journey_mermaid && (
                <section>
                  <h3 className="text-lg font-bold text-ink">Parcours détectés dans les JSON</h3>
                  <p className="mb-4 text-sm text-ink-muted">Analyse automatique des écrans, sans IA.</p>
                  <MermaidDiagram code={result.journey_mermaid} />
                  {result.journey_markdown && (
                    <div className="prose prose-sm prose-slate mt-4 max-w-none prose-h1:text-lg prose-h2:text-base">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.journey_markdown}</ReactMarkdown>
                    </div>
                  )}
                </section>
              )}
            </div>
          )}
        </ResultCard>
      ) : (
        <EmptyPanel icon={<Layers className="h-[30px] w-[30px]" strokeWidth={1.6} />} title="Aucun document de contexte">
          <p className="max-w-[460px] text-[15px] leading-relaxed text-ink-muted">
            Ajoutez vos Markdown et/ou le JSON global de l’application, puis lancez la génération. Le document obtenu (architecture UX, parcours, layout)
            servira de référence pour vos spécifications.
          </p>
        </EmptyPanel>
      )}
    </PageLayout>
  );
}
