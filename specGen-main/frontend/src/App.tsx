import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Check, Settings, Trash2 } from "lucide-react";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { ContextPage, type ContextState } from "./components/ContextPage";
import { HomePage } from "./components/HomePage";
import { MarkdownPage, type MarkdownState } from "./components/MarkdownPage";
import { SettingsPage } from "./components/SettingsPage";
import { SpecPage, type SpecState } from "./components/SpecPage";
import { ThemeToggle } from "./components/ThemeToggle";
import { ToastProvider, useToast } from "./components/Toasts";
import { api } from "./lib/api";
import type { Health, LoadedFile, MarkdownDoc, Page } from "./lib/types";
import { cleanGeneratedMarkdown } from "./lib/files";
import { usePersistentState } from "./lib/usePersistentState";
import logoApp from "./assets/specgen.svg";

const INITIAL_MARKDOWN: MarkdownState = { docs: [], activeDocId: null };
const INITIAL_CONTEXT: ContextState = { markdownFiles: [], jsonFiles: [], language: "fr", result: null };
const INITIAL_SPEC: SpecState = { importedContext: null, specJson: null, image: null, language: "fr", result: null };

export default function App() {
  return (
    <ToastProvider>
      <Workspace />
    </ToastProvider>
  );
}

function Workspace() {
  const toast = useToast();
  const [page, setPage] = usePersistentState<Page>("page", "home");
  const [markdown, setMarkdown] = usePersistentState<MarkdownState>("markdown", INITIAL_MARKDOWN);
  const [context, setContext] = usePersistentState<ContextState>("context", INITIAL_CONTEXT);
  const [spec, setSpec] = usePersistentState<SpecState>("spec", INITIAL_SPEC);
  const [componentLibrary, setComponentLibrary] = usePersistentState<LoadedFile | null>("componentLibrary", null);
  const [settingsDismissed, setSettingsDismissed] = usePersistentState("settingsDismissed", false);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  // Changing the key remounts the pages, which drops their in-memory state (e.g. files waiting for conversion).
  const [resetKey, setResetKey] = useState(0);

  const refreshHealth = useCallback(async () => {
    const loaded = await api.health();
    setHealth(loaded);
    return loaded;
  }, []);

  useEffect(() => {
    refreshHealth()
      .then((loaded) => {
        // First launch: open the settings screen until it is configured or postponed.
        if (!loaded.configured && !settingsDismissed) setPage("settings");
      })
      .catch(() => setHealthError(true));
    // Only on startup.
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [page]);

  // Documents saved before the backend cleanup may still be wrapped in ```markdown or contain <br> tags.
  useEffect(() => {
    setContext((current) =>
      current.result && cleanGeneratedMarkdown(current.result.markdown, current.language) !== current.result.markdown
        ? { ...current, result: { ...current.result, markdown: cleanGeneratedMarkdown(current.result.markdown, current.language) } }
        : current,
    );
    setSpec((current) =>
      current.result && cleanGeneratedMarkdown(current.result.markdown, current.language) !== current.result.markdown
        ? { ...current, result: { ...current.result, markdown: cleanGeneratedMarkdown(current.result.markdown, current.language) } }
        : current,
    );
  }, [setContext, setSpec]);

  const updateMarkdown = useCallback((patch: Partial<MarkdownState>) => setMarkdown((current) => ({ ...current, ...patch })), [setMarkdown]);
  const updateContext = useCallback((patch: Partial<ContextState>) => setContext((current) => ({ ...current, ...patch })), [setContext]);
  const updateSpec = useCallback((patch: Partial<SpecState>) => setSpec((current) => ({ ...current, ...patch })), [setSpec]);

  const llmReady = Boolean(health?.configured);
  const generatedContext = context.result?.markdown ?? "";

  const tabs: { id: Page; label: string; done?: boolean }[] = [
    { id: "home", label: "Accueil" },
    { id: "markdown", label: "Convertir en Markdown", done: markdown.docs.length > 0 },
    { id: "context", label: "Créer un contexte", done: Boolean(generatedContext) },
    { id: "spec", label: "Générer une spécification", done: Boolean(spec.result) },
  ];

  const hasWork =
    markdown.docs.length > 0 ||
    context.markdownFiles.length > 0 ||
    context.jsonFiles.length > 0 ||
    Boolean(context.result) ||
    Boolean(spec.importedContext || spec.specJson || spec.image || spec.result) ||
    Boolean(componentLibrary);

  const resetWorkspace = () => {
    setMarkdown(INITIAL_MARKDOWN);
    setContext(INITIAL_CONTEXT);
    setSpec(INITIAL_SPEC);
    setComponentLibrary(null);
    setResetKey((current) => current + 1);
    setConfirmReset(false);
    if (page !== "settings") setPage("home");
    toast("success", "Tout a été effacé.");
  };

  const useDocsInContext = (docs: MarkdownDoc[]) => {
    const existing = new Set(context.markdownFiles.map((file) => file.name));
    const added: LoadedFile[] = docs
      .filter((doc) => !existing.has(doc.name))
      .map((doc) => ({ name: doc.name, size: new Blob([doc.markdown]).size, content: doc.markdown, origin: "conversion" }));
    updateContext({ markdownFiles: [...context.markdownFiles, ...added] });
    setPage("context");
    toast("success", added.length ? `${added.length} document(s) ajouté(s) aux sources du contexte.` : "Ces documents sont déjà dans les sources du contexte.");
  };

  return (
    <div className="min-h-screen">
      <header className="z-40 flex min-h-16 flex-wrap items-stretch lg:sticky lg:top-0 bg-surface px-4 shadow-[0_1px_0_var(--nn-line)] sm:px-7">
        <button type="button" onClick={() => setPage("home")} className="mr-9 flex items-center gap-2.5 text-[15px] font-bold text-ink">
          <img src={logoApp} alt="" width={30} height={30} className="block shrink-0" />
          SpecGenerator
        </button>
        <nav aria-label="Navigation principale" className="order-last -mx-4 flex w-[calc(100%+2rem)] items-stretch overflow-x-auto border-t border-line sm:-mx-7 sm:w-[calc(100%+3.5rem)] lg:order-none lg:mx-0 lg:w-auto lg:border-t-0">
          {tabs.map((tab) => {
            const active = page === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setPage(tab.id)}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-12 shrink-0 items-center gap-2 whitespace-nowrap border-b-[3px] px-4 text-[15px] lg:min-h-16 transition hover:bg-surface-3 ${
                  active ? "border-accent font-medium text-accent" : "border-transparent text-ink-body"
                }`}
              >
                {tab.done && (
                  <span className="flex h-[18px] w-[18px] items-center justify-center rounded-full bg-success" aria-label="Terminé">
                    <Check className="h-[11px] w-[11px] text-surface" strokeWidth={3.5} aria-hidden />
                  </span>
                )}
                {tab.label}
              </button>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2 py-3">
          <button
            type="button"
            onClick={() => setConfirmReset(true)}
            disabled={!hasWork}
            title={hasWork ? "Effacer les fichiers et documents de ce poste" : "Rien à effacer"}
            className="flex min-h-[36px] items-center gap-2 rounded-full px-3 text-[13px] font-medium text-ink-muted transition hover:bg-surface-3 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <Trash2 className="h-[15px] w-[15px]" aria-hidden />
            <span className="hidden sm:inline">Tout effacer</span>
            <span className="sr-only sm:hidden">Tout effacer</span>
          </button>
          {health && (
            <button
              type="button"
              onClick={() => setPage("settings")}
              aria-current={page === "settings" ? "page" : undefined}
              aria-label={`${llmReady ? "LLM connecté" : "Mode aperçu"} : paramètres de connexion`}
              title={llmReady ? `Modèle : ${health.model}` : "Configurer la connexion"}
              className={`flex min-h-[36px] items-center gap-2 rounded-full px-3 text-[13px] font-medium transition ${
                llmReady ? "bg-success-soft text-success-text hover:opacity-90" : "bg-warning-soft text-warning-text hover:opacity-90"
              } ${page === "settings" ? (llmReady ? "ring-2 ring-success" : "ring-2 ring-warning") : ""}`}
            >
              <span className={`h-2 w-2 rounded-full ${llmReady ? "bg-success" : "bg-warning"}`} />
              {llmReady ? "LLM connecté" : "Mode aperçu"}
              <Settings className="h-[15px] w-[15px]" aria-hidden />
            </button>
          )}
          <ThemeToggle />
        </div>
      </header>

      {(healthError || (health && !llmReady)) && page !== "settings" && (
        <div className="border-b border-warning-line bg-warning-soft">
          <p className="flex items-center gap-2 px-4 py-2 text-sm text-warning-text sm:px-7">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
            {healthError
              ? "Le serveur Python est injoignable. Vérifiez qu’il est bien démarré."
              : "Génération désactivée : la connexion au service IA n’est pas configurée. La conversion Markdown reste disponible."}
            {!healthError && (
              <button type="button" className="ml-1 font-medium underline" onClick={() => setPage("settings")}>
                Configurer
              </button>
            )}
          </p>
        </div>
      )}

      <ConfirmDialog
        open={confirmReset}
        title="Tout effacer ?"
        confirmLabel="Tout effacer"
        onConfirm={resetWorkspace}
        onCancel={() => setConfirmReset(false)}
      >
        <p>
          Les fichiers importés, les Markdown convertis, le contexte, la spécification et leurs modifications seront supprimés de ce poste. Cette action est
          irréversible : téléchargez d’abord ce que vous voulez garder.
        </p>
        <p className="mt-2">Les paramètres de connexion au service IA sont conservés.</p>
      </ConfirmDialog>

      <div key={resetKey}>
      {page === "home" && <HomePage onNavigate={setPage} />}
      {page === "settings" && (
        <SettingsPage
          onSaved={(_settings, firstSetup) => {
            refreshHealth().catch(() => setHealthError(true));
            if (firstSetup) {
              toast("success", "Connexion configurée : la génération est activée.");
              setPage("home");
            }
          }}
          onLater={() => {
            setSettingsDismissed(true);
            setPage("home");
          }}
        />
      )}
      {page === "markdown" && <MarkdownPage state={markdown} update={updateMarkdown} onUseInContext={useDocsInContext} />}
      {page === "context" && (
        <ContextPage
          state={context}
          update={updateContext}
          componentLibrary={componentLibrary}
          onComponentLibraryChange={setComponentLibrary}
          llmReady={llmReady}
          onUseInSpec={() => {
            updateSpec({ importedContext: null });
            setPage("spec");
          }}
        />
      )}
      {page === "spec" && (
        <SpecPage
          state={spec}
          update={updateSpec}
          generatedContext={generatedContext}
          componentLibrary={componentLibrary}
          onComponentLibraryChange={setComponentLibrary}
          llmReady={llmReady}
          onGoToContext={() => setPage("context")}
        />
      )}
      </div>
    </div>
  );
}
