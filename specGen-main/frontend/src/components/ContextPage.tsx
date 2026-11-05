import { useState } from "react";
import { ArrowRight, FileText, Layers } from "lucide-react";
import { api } from "../lib/api";
import { hasMermaidBlock, insertFlowDiagram } from "../lib/flow";
import { documentTitle, formatSize, readJsonFile, readTextFile } from "../lib/files";
import type { ContextResult, Language, LoadedFile } from "../lib/types";
import { AddFileButton, Field, FileChip, LanguageField, LargeDropzone } from "./fields";
import { GenerateFooter, PageLayout } from "./Layout";
import { DocumentView, EditToggle } from "./DocumentEditor";
import { mermaidError } from "./MermaidDiagram";
import { documentMeta, editedResult, EmptyPanel, ExportButtons, ProgressPanel, ResultCard, WarningsPanel } from "./ResultCard";
import { ComponentLibraryField, JsonIcon } from "./shared";
import { TranslateButton } from "./TranslateButton";
import { useToast } from "./Toasts";

export interface ContextState {
  markdownFiles: LoadedFile[];
  jsonFiles: LoadedFile[];
  language: Language;
  result: ContextResult | null;
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
  const [editing, setEditing] = useState(false);
  const [translating, setTranslating] = useState(false);
  const result = state.result;
  // The document keeps its own language once translated; the form field is for the next generation.
  const docLanguage = result?.language ?? state.language;
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
      const markdown = await withFlowDiagram(generated.markdown);
      update({ result: { ...generated, markdown, generatedAt: new Date().toISOString(), language: state.language } });
      setEditing(false);
      toast(
        generated.retried_light || generated.warnings?.length ? "info" : "success",
        generated.retried_light
          ? "Contexte généré après une nouvelle tentative en mode allégé (délai dépassé)."
          : generated.warnings?.length
            ? `Document de contexte généré en ${generated.timings.total} s, avec des points à vérifier.`
            : `Document de contexte généré en ${generated.timings.total} s.`,
      );
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setIsGenerating(false);
    }
  };

  /** The user flow diagram goes into the document itself, so that the preview and the exports show it. */
  const withFlowDiagram = async (markdown: string): Promise<string> => {
    if (hasMermaidBlock(markdown)) return markdown;
    try {
      let { mermaid } = await api.generateMermaid(markdown, state.language);
      const error = await mermaidError(mermaid);
      if (error) {
        // One correction round with the parser's message; keep the first version if it is no better.
        const fixed = await api.generateMermaid(markdown, state.language, { previous_code: mermaid, error });
        if (!(await mermaidError(fixed.mermaid))) mermaid = fixed.mermaid;
        else return markdown;
      }
      return insertFlowDiagram(markdown, mermaid, state.language);
    } catch {
      toast("info", "Le schéma du parcours n’a pas pu être généré : le document est livré sans.");
      return markdown;
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
          steps={["Lecture et agrégation des sources", "Analyse de la structure et des parcours", "Rédaction par l’IA", "Schéma du parcours utilisateur", "Mise en forme du document"]}
          note="En cas de délai dépassé, une nouvelle tentative en mode allégé est lancée automatiquement."
        />
      ) : result ? (
        <ResultCard
          eyebrow={docLanguage === "en" ? "UX Architecture · Global application context" : "Architecture UX · Contexte global application"}
          title={documentTitle(result.markdown, docLanguage === "en" ? "UX Architecture / Project overview" : "Architecture UX / Project overview")}
          meta={documentMeta(result, docLanguage)}
          cta={
            <button type="button" className="btn-soft" onClick={onUseInSpec}>
              Utiliser pour la spécification <ArrowRight className="h-4 w-4" aria-hidden />
            </button>
          }
          actions={
            <>
              <EditToggle editing={editing} disabled={translating} onToggle={() => setEditing(!editing)} />
              <TranslateButton
                kind="context"
                result={result}
                language={docLanguage}
                disabled={editing}
                disabledReason={!llmReady ? "Configuration LLM incomplète : traduction désactivée." : null}
                onBusyChange={setTranslating}
                onTranslated={(translated) => update({ result: translated })}
              />
              <ExportButtons kind="context" markdown={result.markdown} language={docLanguage} />
            </>
          }
        >
          <WarningsPanel warnings={result.warnings} />
          {translating && (
            <p className="mb-4 rounded-lg border border-line bg-surface-2 p-3 text-sm text-ink-muted" aria-live="polite">
              Traduction en cours, section par section : de 30 s à quelques minutes selon la longueur du document.
            </p>
          )}
          <DocumentView
            markdown={result.markdown}
            originalMarkdown={result.originalMarkdown}
            editing={editing}
            onChange={(markdown) => update({ result: editedResult(result, markdown) })}
          />
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
