import { isValidElement, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { MermaidDiagram } from "./MermaidDiagram";
import { unwrapMarkdownFence } from "../lib/files";
import type { FeatureImage } from "../lib/types";

export const PROSE =
  "doc-prose prose max-w-none [&>:first-child]:mt-0 text-[15px] text-ink-body prose-headings:text-ink prose-h1:text-2xl prose-h2:mt-8 prose-h2:border-b prose-h2:border-line prose-h2:pb-2 prose-h2:text-[22px] prose-h3:text-lg prose-table:text-sm prose-th:bg-[#1B1D2A] prose-th:px-3 prose-th:py-2.5 prose-th:font-medium prose-th:text-white dark:prose-th:bg-surface-3 dark:prose-th:text-ink prose-td:border prose-td:border-line prose-td:px-3 prose-td:py-2.5 prose-blockquote:rounded-lg prose-blockquote:border-0 prose-blockquote:bg-warning-soft prose-blockquote:px-4 prose-blockquote:py-1 prose-blockquote:font-normal prose-blockquote:not-italic prose-blockquote:text-warning-text prose-code:rounded prose-code:bg-surface-3 prose-code:px-1 prose-code:py-0.5 prose-code:before:content-none prose-code:after:content-none prose-pre:bg-[#1B1D2A] prose-pre:border prose-pre:border-line [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-[13px] [&_pre_code]:text-[#EDEFF8]";

/** ```mermaid blocks (draw.io conversions, user flows) are drawn instead of shown as code. */
export const COMPONENTS: Components = {
  pre({ children }) {
    const code = Array.isArray(children) ? children[0] : children;
    if (isValidElement<{ className?: string; children?: ReactNode }>(code) && code.props.className?.includes("language-mermaid")) {
      return <MermaidDiagram code={String(code.props.children ?? "").trim()} />;
    }
    return <pre>{children}</pre>;
  },
};

/** Renders a document body; the optional image goes right under the first section heading. */
export function MarkdownPreview({ markdown: source, image, imageAlt }: { markdown: string; image?: FeatureImage | null; imageAlt?: string }) {
  const markdown = unwrapMarkdownFence(source);
  let before = markdown;
  let after = "";
  if (image) {
    const match = /^##\s+.+$/m.exec(markdown);
    const splitAt = match ? match.index + match[0].length : 0;
    before = markdown.slice(0, splitAt);
    after = markdown.slice(splitAt);
  }

  return (
    <article className={PROSE}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {before}
      </ReactMarkdown>
      {image && (
        <img
          src={`data:${image.mime};base64,${image.base64}`}
          alt={imageAlt ?? image.name}
          className="my-4 max-h-[420px] w-full rounded-lg border border-line bg-surface-2 object-contain"
        />
      )}
      {after && (
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
          {after}
        </ReactMarkdown>
      )}
    </article>
  );
}
