import { useState } from "react";
import { Languages } from "lucide-react";
import { api } from "../lib/api";
import type { DocKind, DocumentVersion, Language } from "../lib/types";
import { mermaidError } from "./MermaidDiagram";
import { useToast } from "./Toasts";

const MERMAID_BLOCK = /^```mermaid[ \t]*\n[\s\S]*?\n```[ \t]*$/gm;

interface TranslatableResult {
  markdown: string;
  warnings?: string[];
  resolvedWarnings?: string[];
  alternates?: Partial<Record<Language, DocumentVersion>>;
  language?: Language;
  generatedAt?: string;
  originalMarkdown?: string;
  editedAt?: string;
  translatedAt?: string;
}

/** A translated diagram that no longer parses is replaced by the diagram of the source document. */
async function keepValidDiagrams(source: string, translated: string): Promise<string> {
  const originals = source.match(MERMAID_BLOCK) ?? [];
  let index = 0;
  const blocks = translated.match(MERMAID_BLOCK) ?? [];
  const replacements: string[] = [];
  for (const block of blocks) {
    const code = block.replace(/^```mermaid[ \t]*\n/, "").replace(/\n```[ \t]*$/, "");
    const original = originals[index++];
    replacements.push(original && (await mermaidError(code)) ? original : block);
  }
  let position = 0;
  return translated.replace(MERMAID_BLOCK, () => replacements[position++]);
}

const LANGUAGE_NAMES: Record<Language, string> = { fr: "français", en: "anglais" };

/** The language version shown, as it is kept aside while the other one is on screen. */
function snapshot(result: TranslatableResult): DocumentVersion {
  return {
    markdown: result.markdown,
    warnings: result.warnings,
    resolvedWarnings: result.resolvedWarnings,
    generatedAt: result.generatedAt,
    originalMarkdown: result.originalMarkdown,
    editedAt: result.editedAt,
    translatedAt: result.translatedAt,
  };
}

function withoutLanguage(alternates: TranslatableResult["alternates"], language: Language) {
  const rest = { ...alternates };
  delete rest[language];
  return rest;
}

/** Shows the other language version: the one on screen is kept aside, with its own edits. */
export function switchLanguage<T extends TranslatableResult>(result: T, current: Language, target: Language): T {
  const version = result.alternates?.[target];
  if (!version) return result;
  return {
    ...result,
    ...snapshot({ markdown: "" }),
    ...version,
    language: target,
    alternates: { ...withoutLanguage(result.alternates, target), [current]: snapshot(result) },
  };
}

/** French / English switch, once the document exists in both languages. */
export function LanguageVersions({
  result,
  language,
  disabled,
  onSwitch,
}: {
  result: TranslatableResult;
  language: Language;
  disabled?: boolean;
  onSwitch: (target: Language) => void;
}) {
  const languages = (["fr", "en"] as Language[]).filter((option) => option === language || result.alternates?.[option]);
  if (languages.length < 2) return null;
  return (
    <div role="radiogroup" aria-label="Version du document" className="flex rounded-lg bg-surface-3 p-1">
      {languages.map((option) => (
        <button
          key={option}
          type="button"
          role="radio"
          aria-checked={option === language}
          disabled={disabled && option !== language}
          title={option === language ? undefined : `Afficher la version en ${LANGUAGE_NAMES[option]}`}
          onClick={() => option !== language && onSwitch(option)}
          className={`min-h-[36px] rounded-md px-3.5 text-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${
            option === language ? "bg-surface font-medium text-ink shadow-[0_1px_2px_rgba(16,24,64,0.12)]" : "text-ink-muted hover:text-ink"
          }`}
        >
          {option === "fr" ? "Français" : "English"}
        </button>
      ))}
    </div>
  );
}

/**
 * Translates the document shown (edits included) into the other language. The translation
 * is shown in its place; the source version is kept, with its edits, behind the language switch.
 */
export function TranslateButton<T extends TranslatableResult>({
  kind,
  result,
  language,
  disabled,
  disabledReason,
  onBusyChange,
  onTranslated,
}: {
  kind: DocKind;
  result: T;
  language: Language;
  disabled?: boolean;
  disabledReason?: string | null;
  onBusyChange?: (busy: boolean) => void;
  onTranslated: (result: T) => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const target: Language = language === "fr" ? "en" : "fr";
  const hasTarget = Boolean(result.alternates?.[target]);
  const label = `${hasTarget ? "Retraduire" : "Traduire"} en ${LANGUAGE_NAMES[target]}`;

  const handleTranslate = async () => {
    setBusy(true);
    onBusyChange?.(true);
    try {
      const translated = await api.translate(kind, result.markdown, target);
      const markdown = await keepValidDiagrams(result.markdown, translated.markdown);
      onTranslated({
        ...result,
        markdown,
        language: target,
        translatedAt: new Date().toISOString(),
        originalMarkdown: undefined,
        editedAt: undefined,
        warnings: [...(result.warnings ?? []), ...translated.warnings],
        alternates: { ...withoutLanguage(result.alternates, target), [language]: snapshot(result) },
      });
      toast(
        translated.warnings.length ? "info" : "success",
        `Document traduit en ${target === "en" ? "anglais" : "français"} en ${translated.timings.total} s${
          translated.warnings.length ? ", avec des passages à relire." : "."
        }`,
      );
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(false);
      onBusyChange?.(false);
    }
  };

  return (
    <button
      type="button"
      className="btn-secondary"
      disabled={busy || disabled || Boolean(disabledReason)}
      title={
        disabledReason ??
        (hasTarget
          ? `Remplace la version en ${LANGUAGE_NAMES[target]} par une nouvelle traduction du document affiché.`
          : `Traduit le document affiché, modifications comprises, en ${LANGUAGE_NAMES[target]}. Cette version reste disponible.`)
      }
      onClick={handleTranslate}
    >
      <Languages className="h-4 w-4" aria-hidden />
      {busy ? "Traduction…" : label}
    </button>
  );
}
