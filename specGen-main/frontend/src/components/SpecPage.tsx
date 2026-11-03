import { useState } from "react";
import { FileText, Layers, Monitor } from "lucide-react";
import { api } from "../lib/api";
import { documentTitle, formatDateTime, formatSize, LANGUAGE_LABELS, readImageFile, readJsonFile, readTextFile, stripTitle } from "../lib/files";
import type { DetailLevel, FeatureImage, Language, LoadedFile, SpecResult } from "../lib/types";
import { AddFileButton, DetailLevelField, Field, FileChip, FileLink, LanguageField, LargeDropzone } from "./fields";
import { GenerateFooter, PageLayout } from "./Layout";
import { MarkdownPreview } from "./MarkdownPreview";
import { EmptyPanel, ExportButtons, ProgressPanel, ResultCard } from "./ResultCard";
import { ComponentLibraryField, JsonIcon } from "./shared";
import { useToast } from "./Toasts";

export interface SpecState {
  /** A Markdown context imported on this page; when null, the generated context is used. */
  importedContext: LoadedFile | null;
  specJson: LoadedFile | null;
  image: FeatureImage | null;
  language: Language;
  /** Missing in states saved before the field existed. */
  detailLevel?: DetailLevel;
  result: SpecResult | null;
}

export function SpecPage({
  state,
  update,
  generatedContext,
  componentLibrary,
  onComponentLibraryChange,
  llmReady,
  onGoToContext,
}: {
  state: SpecState;
  update: (patch: Partial<SpecState>) => void;
  generatedContext: string;
  componentLibrary: LoadedFile | null;
  onComponentLibraryChange: (file: LoadedFile | null) => void;
  llmReady: boolean;
  onGoToContext: () => void;
}) {
  const toast = useToast();
  const [isGenerating, setIsGenerating] = useState(false);
  const result = state.result;
  const usesGeneratedContext = !state.importedContext && Boolean(generatedContext);
  const businessContext = state.importedContext ? String(state.importedContext.content) : generatedContext;

  const importContext = async ([file]: File[]) => update({ importedContext: await readTextFile(file) });

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const generated = await api.generateSpec({
        business_context: businessContext,
        spec_json: state.specJson?.content,
        component_library: componentLibrary?.content ?? null,
        language: state.language,
        detail_level: state.detailLevel ?? "standard",
      });
      update({ result: { ...generated, generatedAt: new Date().toISOString() } });
      const warningCount = generated.warnings?.length ?? 0;
      toast(
        warningCount ? "info" : "success",
        warningCount
          ? `Spécification générée en ${generated.timings.total} s, avec ${warningCount} point${warningCount > 1 ? "s" : ""} à vérifier.`
          : `Spécification générée en ${generated.timings.total} s.`,
      );
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <PageLayout
      title="Générer une spécification"
      description="Sélectionnez les sources. Le JSON écran / composant est requis."
      fields={
        <>
          <Field label="Contexte projet">
            {usesGeneratedContext ? (
              <>
                <FileChip
                  highlighted
                  icon={<Layers className="h-[22px] w-[22px]" strokeWidth={1.8} />}
                  name={documentTitle(generatedContext, "Document de contexte")}
                  detail="Contexte généré à l’étape « Créer un contexte » · utilisé automatiquement"
                  action={
                    <button type="button" className="text-[13px] font-medium text-navy hover:text-navy-dark" onClick={onGoToContext}>
                      Voir
                    </button>
                  }
                />
                <span className="text-[13px] text-ink-muted">
                  Ou{" "}
                  <FileLink accept=".md,.markdown" onFiles={importContext}>
                    importer un autre contexte (.md)
                  </FileLink>
                </span>
              </>
            ) : state.importedContext ? (
              <>
                <FileChip
                  icon={<FileText className="h-[22px] w-[22px]" strokeWidth={1.8} />}
                  name={state.importedContext.name}
                  detail={`Contexte importé · ${formatSize(state.importedContext.size)}`}
                  onRemove={() => update({ importedContext: null })}
                />
                {generatedContext && (
                  <button type="button" className="self-start text-[13px] font-medium text-navy underline" onClick={() => update({ importedContext: null })}>
                    Revenir au contexte généré
                  </button>
                )}
              </>
            ) : (
              <>
                <AddFileButton label="Importer un contexte (.md)" accept=".md,.markdown" onFiles={importContext} />
                <p className="hint">
                  Ou{" "}
                  <button type="button" className="font-medium text-navy underline" onClick={onGoToContext}>
                    générez-le
                  </button>{" "}
                  à l’étape « Créer un contexte ».
                </p>
              </>
            )}
          </Field>

          <Field label="JSON écran / composant">
            {state.specJson ? (
              <FileChip icon={<JsonIcon />} name={state.specJson.name} detail={formatSize(state.specJson.size)} onRemove={() => update({ specJson: null })} />
            ) : (
              <LargeDropzone
                accept=".json"
                formats="JSON · 200 Mo max"
                onFiles={async ([file]) => {
                  try {
                    update({ specJson: await readJsonFile(file) });
                  } catch (error) {
                    toast("error", (error as Error).message);
                  }
                }}
              />
            )}
          </Field>

          <Field label="Image de la feature" optional>
            {state.image ? (
              <div className="relative flex h-[150px] items-center justify-center overflow-hidden rounded-lg border border-line-strong bg-[#EEF0F5]">
                <img src={`data:${state.image.mime};base64,${state.image.base64}`} alt={state.image.name} className="h-full w-full object-contain" />
                <span className="absolute bottom-2 left-2.5 max-w-[70%] truncate rounded bg-white/90 px-1.5 text-xs text-ink-muted">{state.image.name}</span>
                <button
                  type="button"
                  onClick={() => update({ image: null })}
                  className="absolute right-2 top-2 min-h-[32px] rounded-md border border-line-strong bg-white px-2.5 text-xs font-medium text-ink hover:bg-[#F2F3F8]"
                >
                  Retirer
                </button>
              </div>
            ) : (
              <AddFileButton
                label="Ajouter une image (PNG, JPEG, WEBP)"
                accept=".png,.jpg,.jpeg,.webp"
                onFiles={async ([file]) => {
                  try {
                    update({ image: await readImageFile(file) });
                  } catch (error) {
                    toast("error", (error as Error).message);
                  }
                }}
              />
            )}
          </Field>

          <ComponentLibraryField file={componentLibrary} onChange={onComponentLibraryChange} sharedWith="Créer un contexte" />

          <LanguageField value={state.language} onChange={(language) => update({ language })} />

          <DetailLevelField value={state.detailLevel ?? "standard"} onChange={(detailLevel) => update({ detailLevel })} />
        </>
      }
      footer={
        <GenerateFooter
          label={result ? "Régénérer la spécification" : "Générer la spécification"}
          busyLabel="Génération en cours…"
          isBusy={isGenerating}
          disabledReason={!llmReady ? "Configuration LLM incomplète : génération désactivée." : !state.specJson ? "Ajoutez le JSON écran / composant pour continuer." : null}
          onClick={handleGenerate}
        />
      }
    >
      {isGenerating ? (
        <ProgressPanel title="Génération de la spécification" steps={["Lecture des sources", "Analyse de la structure JSON", "Rédaction par l’IA", "Mise en forme du document"]} />
      ) : result ? (
        <ResultCard
          eyebrow={state.language === "en" ? "Detailed UX / HMI specification" : "Spécification UX / HMI détaillée"}
          title={documentTitle(result.markdown, state.language === "en" ? "UX / HMI Specification" : "Spécification UX / HMI")}
          meta={`Généré le ${formatDateTime(result.generatedAt)} · ${LANGUAGE_LABELS[state.language]}`}
          actions={<ExportButtons kind="spec" markdown={result.markdown} language={state.language} image={state.image} />}
        >
          {result.warnings && result.warnings.length > 0 && (
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <p className="font-medium">Points à vérifier dans ce document</p>
              <ul className="mt-1 list-disc pl-5">
                {result.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
          <MarkdownPreview markdown={stripTitle(result.markdown)} image={state.image} imageAlt={documentTitle(result.markdown, "Feature")} />
        </ResultCard>
      ) : (
        <EmptyPanel icon={<Monitor className="h-[30px] w-[30px]" strokeWidth={1.6} />} title="Aucune spécification pour le moment">
          <p className="max-w-[480px] text-[15px] leading-relaxed text-ink-muted">
            Importez le JSON de l’écran ou du composant à documenter.
            {usesGeneratedContext ? " Le contexte généré à l’étape précédente est déjà pris en compte." : ""}
          </p>
          <p className="mt-2 max-w-[480px] text-[13px] leading-normal text-ink-subtle">
            La spécification contiendra : vue d’ensemble, variantes, détail des composants, erreurs possibles, hypothèses et questions ouvertes.
          </p>
        </EmptyPanel>
      )}
    </PageLayout>
  );
}
