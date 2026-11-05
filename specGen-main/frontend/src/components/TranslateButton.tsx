import { useState } from "react";
import { Languages } from "lucide-react";
import { api } from "../lib/api";
import type { DocKind, Language } from "../lib/types";
import { mermaidError } from "./MermaidDiagram";
import { useToast } from "./Toasts";

const MERMAID_BLOCK = /^```mermaid[ \t]*\n[\s\S]*?\n```[ \t]*$/gm;

interface TranslatableResult {
  markdown: string;
  warnings?: string[];
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

/**
 * Translates the document shown (edits included) into the other language. The translation
 * becomes the new reference version: the exports and the edits start from it.
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
  const label = target === "en" ? "Traduire en anglais" : "Traduire en français";

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
      title={disabledReason ?? `Traduit le document affiché, modifications comprises, en ${target === "en" ? "anglais" : "français"}.`}
      onClick={handleTranslate}
    >
      <Languages className="h-4 w-4" aria-hidden />
      {busy ? "Traduction…" : label}
    </button>
  );
}
