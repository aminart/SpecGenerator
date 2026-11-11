import { useEffect, useMemo, useRef, useState, type ClipboardEvent, type FocusEvent, type KeyboardEvent, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Columns3, PenLine, Plus, RotateCcw, Rows3, Trash2, Undo2 } from "lucide-react";
import { blocksMarkdown, fenced, insertAfter, readTable, replaceBlock, splitBlocks, tableMarkdown, type MarkdownBlock } from "../lib/markdownBlocks";
import { stripTitle, unwrapMarkdownFence } from "../lib/files";
import type { FeatureImage } from "../lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { COMPONENTS, MarkdownPreview, PROSE } from "./MarkdownPreview";
import { MermaidDiagram } from "./MermaidDiagram";

const NEW_PARAGRAPH = "Nouveau paragraphe";

function hash(text: string): string {
  let value = 5381;
  for (let index = 0; index < text.length; index++) value = (value * 33) ^ text.charCodeAt(index);
  return (value >>> 0).toString(36);
}

/** Pastes as plain text, so formatting from other apps does not leak into the document. */
function pastePlainText(event: ClipboardEvent) {
  event.preventDefault();
  document.execCommand("insertText", false, event.clipboardData.getData("text/plain"));
}

function leavesBlock(event: FocusEvent) {
  return !(event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget));
}

/**
 * The document, editable in place: text is typed directly into the rendered page,
 * tables cell by cell, diagrams and code in their source. Each change is written
 * back to the Markdown when the block loses focus, so blocks the user does not
 * touch stay exactly as generated.
 */
export function DocumentEditor({
  markdown,
  onChange,
  image,
  imageAlt,
  toolbarExtra,
}: {
  markdown: string;
  onChange: (markdown: string) => void;
  image?: FeatureImage | null;
  imageAlt?: string;
  toolbarExtra?: ReactNode;
}) {
  const blocks = useMemo(() => splitBlocks(markdown), [markdown]);
  const history = useRef<string[]>([]);
  const [focusIndex, setFocusIndex] = useState<number | null>(null);
  const imageAfter = image ? blocks.findIndex((block) => block.depth === 2) : -1;

  const commit = (next: string) => {
    if (next === markdown) return;
    history.current = [...history.current.slice(-49), markdown];
    onChange(next);
  };
  const undo = () => {
    const previous = history.current.pop();
    if (previous !== undefined) onChange(previous);
  };

  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target?.isContentEditable || target?.tagName === "TEXTAREA" || target?.tagName === "INPUT";
      if (!typing && (event.ctrlKey || event.metaKey) && !event.shiftKey && event.key.toLowerCase() === "z" && history.current.length) {
        event.preventDefault();
        undo();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="sticky top-0 z-10 -mx-2 flex flex-wrap items-center gap-3 rounded-lg border border-line-strong bg-navy-softer px-4 py-2.5 shadow-sm">
        <p className="min-w-0 flex-1 text-[13px] leading-snug text-ink-muted">
          <span className="font-medium text-accent">Mode édition.</span> Cliquez dans le texte pour le modifier (Ctrl+B gras, Ctrl+I italique, Entrée nouveau
          paragraphe). Survolez un bloc pour l’ajouter, le supprimer ou modifier un tableau. Les exports utilisent cette version.
        </p>
        <button type="button" className="btn-secondary min-h-[36px] px-3" onClick={undo} disabled={!history.current.length} title="Annuler la dernière modification (Ctrl+Z)">
          <Undo2 className="h-4 w-4" aria-hidden /> Annuler
        </button>
        {toolbarExtra}
      </div>
      <article className={PROSE}>
        {blocks.map((block, index) => (
          <div key={`${index}:${hash(block.source)}`}>
            <EditableBlock
              block={block}
              autoFocus={focusIndex === index}
              onFocused={() => setFocusIndex(null)}
              onCommit={(source) => commit(replaceBlock(markdown, block, source))}
              onInsertAfter={() => {
                commit(insertAfter(markdown, block, NEW_PARAGRAPH));
                setFocusIndex(index + 1);
              }}
            />
            {index === imageAfter && image && (
              <img
                src={`data:${image.mime};base64,${image.base64}`}
                alt={imageAlt ?? image.name}
                className="my-4 max-h-[420px] w-full rounded-lg border border-line bg-surface-2 object-contain"
              />
            )}
          </div>
        ))}
        {!blocks.length && (
          <button type="button" className="btn-soft" onClick={() => commit(NEW_PARAGRAPH)}>
            <Plus className="h-4 w-4" aria-hidden /> Ajouter un paragraphe
          </button>
        )}
      </article>
    </div>
  );
}

interface BlockProps {
  block: MarkdownBlock;
  autoFocus: boolean;
  onFocused: () => void;
  onCommit: (source: string) => void;
  onInsertAfter: () => void;
}

function EditableBlock(props: BlockProps) {
  switch (props.block.kind) {
    case "text":
      return <TextBlock {...props} />;
    case "table":
      return <TableBlock {...props} />;
    case "code":
    case "mermaid":
      return <CodeBlock {...props} />;
    case "rule":
      return (
        <BlockFrame {...props}>
          <hr />
        </BlockFrame>
      );
    default:
      return <SourceBlock {...props} />;
  }
}

function ToolButton({ label, onClick, children, danger }: { label: string; onClick: () => void; children: ReactNode; danger?: boolean }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      // Keeps the focus (and the caret) in the block being edited.
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className={`flex h-7 min-w-7 items-center justify-center gap-1 rounded px-1.5 text-xs font-medium ${
        danger ? "text-danger-text hover:bg-danger-soft" : "text-ink-muted hover:bg-navy-soft hover:text-accent"
      }`}
    >
      {children}
    </button>
  );
}

/** Hover outline and the block's toolbar. */
function BlockFrame({ onCommit, onInsertAfter, tools, children }: BlockProps & { tools?: ReactNode; children: ReactNode }) {
  return (
    <div className="group relative rounded-md outline-none ring-accent-soft ring-offset-4 ring-offset-surface hover:ring-1 focus-within:ring-2">
      <div
        contentEditable={false}
        className="not-prose absolute -top-3 right-0 z-[5] flex items-center gap-0.5 rounded-md border border-line bg-surface p-0.5 opacity-0 shadow-sm transition group-focus-within:opacity-100 group-hover:opacity-100"
      >
        {tools}
        <ToolButton label="Ajouter un paragraphe dessous" onClick={onInsertAfter}>
          <Plus className="h-3.5 w-3.5" aria-hidden />
        </ToolButton>
        <ToolButton label="Supprimer ce bloc" danger onClick={() => onCommit("")}>
          <Trash2 className="h-3.5 w-3.5" aria-hidden />
        </ToolButton>
      </div>
      {children}
    </div>
  );
}

function TextBlock(props: BlockProps) {
  const { block, autoFocus, onFocused, onCommit } = props;
  const ref = useRef<HTMLDivElement>(null);
  const dirty = useRef(false);
  // Bumped to throw away the DOM the user typed into (Échap).
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (!autoFocus || !ref.current) return;
    ref.current.focus();
    const range = document.createRange();
    range.selectNodeContents(ref.current);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
    onFocused();
  }, [autoFocus, onFocused]);

  const save = () => {
    if (!dirty.current || !ref.current) return;
    dirty.current = false;
    onCommit(blocksMarkdown(ref.current));
  };

  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      dirty.current = false;
      setVersion((value) => value + 1);
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      ref.current?.blur();
    }
  };

  return (
    <BlockFrame {...props}>
      <div
        key={version}
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        spellCheck
        aria-label="Bloc de texte modifiable"
        className="cursor-text rounded-sm outline-none"
        onInput={() => (dirty.current = true)}
        onBlur={(event) => leavesBlock(event) && save()}
        onPaste={pastePlainText}
        onKeyDown={onKeyDown}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
          {block.source}
        </ReactMarkdown>
      </div>
    </BlockFrame>
  );
}

function EditableCell({ header, ...props }: { header: boolean } & Record<string, unknown>) {
  const Tag = header ? "th" : "td";
  return (
    <Tag
      {...props}
      contentEditable
      suppressContentEditableWarning
      spellCheck
      className="cursor-text outline-none focus:bg-navy-softer focus:text-ink"
      onKeyDown={(event: KeyboardEvent) => event.key === "Enter" && event.preventDefault()}
      onPaste={pastePlainText}
    />
  );
}

const TABLE_COMPONENTS: Components = {
  ...COMPONENTS,
  th: ({ node: _node, ...props }) => <EditableCell header {...props} />,
  td: ({ node: _node, ...props }) => <EditableCell header={false} {...props} />,
};

function TableBlock(props: BlockProps) {
  const { block, onCommit } = props;
  const ref = useRef<HTMLDivElement>(null);
  const dirty = useRef(false);
  const cell = useRef<HTMLTableCellElement | null>(null);

  const table = () => ref.current?.querySelector("table") ?? null;
  const save = () => {
    const element = table();
    if (!dirty.current || !element) return;
    dirty.current = false;
    const { rows, align } = readTable(element);
    onCommit(tableMarkdown(rows, align));
  };

  /** Applies a row/column change around the focused cell (the last row/column when none). */
  const reshape = (change: (rows: string[][], row: number, column: number) => void) => {
    const element = table();
    if (!element) return;
    const { rows, align } = readTable(element);
    const focused = cell.current && element.contains(cell.current) ? cell.current : null;
    const row = focused ? (focused.parentElement as HTMLTableRowElement).rowIndex : rows.length - 1;
    const column = focused ? focused.cellIndex : (rows[0]?.length ?? 1) - 1;
    change(rows, row, column);
    const width = Math.max(...rows.map((cells) => cells.length));
    dirty.current = false;
    onCommit(tableMarkdown(rows, align.length > width ? align.slice(0, width) : align));
  };

  const tools = (
    <>
      <ToolButton label="Ajouter une ligne sous la cellule active" onClick={() => reshape((rows, row) => rows.splice(row + 1, 0, rows[0].map(() => "")))}>
        <Rows3 className="h-3.5 w-3.5" aria-hidden />+
      </ToolButton>
      <ToolButton label="Supprimer la ligne active" onClick={() => reshape((rows, row) => row > 0 && rows.length > 2 && rows.splice(row, 1))}>
        <Rows3 className="h-3.5 w-3.5" aria-hidden />−
      </ToolButton>
      <ToolButton label="Ajouter une colonne à droite de la cellule active" onClick={() => reshape((rows, _row, column) => rows.forEach((cells) => cells.splice(column + 1, 0, "")))}>
        <Columns3 className="h-3.5 w-3.5" aria-hidden />+
      </ToolButton>
      <ToolButton
        label="Supprimer la colonne active"
        onClick={() => reshape((rows, _row, column) => rows[0].length > 1 && rows.forEach((cells) => cells.splice(column, 1)))}
      >
        <Columns3 className="h-3.5 w-3.5" aria-hidden />−
      </ToolButton>
      <span className="mx-0.5 h-4 w-px bg-line" aria-hidden />
    </>
  );

  return (
    <BlockFrame {...props} tools={tools}>
      <div
        ref={ref}
        onFocus={(event) => (cell.current = (event.target as HTMLElement).closest("td,th"))}
        onInput={() => (dirty.current = true)}
        onBlur={(event) => leavesBlock(event) && save()}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={TABLE_COMPONENTS}>
          {block.source}
        </ReactMarkdown>
      </div>
    </BlockFrame>
  );
}

function CodeBlock(props: BlockProps) {
  const { block, onCommit } = props;
  const [code, setCode] = useState(block.code ?? "");
  const isMermaid = block.kind === "mermaid";
  const save = () => code !== block.code && onCommit(fenced(code, block.lang));
  const editor = (
    <textarea
      value={code}
      onChange={(event) => setCode(event.target.value)}
      onBlur={save}
      spellCheck={false}
      rows={Math.min(24, Math.max(4, code.split("\n").length + 1))}
      aria-label={isMermaid ? "Code Mermaid du diagramme" : "Code"}
      className="input-area not-prose font-mono text-[13px] leading-relaxed"
    />
  );
  return (
    <BlockFrame {...props}>
      {isMermaid ? (
        <div className="not-prose my-4 flex flex-col gap-2">
          <MermaidDiagram
            code={code}
            onCodeChange={(next) => {
              setCode(next);
              onCommit(fenced(next, block.lang));
            }}
          />
          <p className="text-[13px] text-ink-subtle">Cliquez sur une boîte, une flèche ou un titre de groupe pour renommer son libellé.</p>
          <details>
            <summary className="cursor-pointer text-sm font-medium text-ink-muted hover:text-ink">Modifier le code du diagramme</summary>
            <div className="mt-2">{editor}</div>
          </details>
        </div>
      ) : (
        <div className="my-4">{editor}</div>
      )}
    </BlockFrame>
  );
}

/** Anything else (HTML, link definitions…): edited as Markdown source. */
function SourceBlock(props: BlockProps) {
  const { block, onCommit } = props;
  const [source, setSource] = useState(block.source);
  return (
    <BlockFrame {...props}>
      <textarea
        value={source}
        onChange={(event) => setSource(event.target.value)}
        onBlur={() => source !== block.source && onCommit(source)}
        spellCheck={false}
        rows={Math.max(2, source.split("\n").length)}
        aria-label="Source Markdown du bloc"
        className="input-area not-prose my-4 font-mono text-[13px]"
      />
    </BlockFrame>
  );
}

export function EditToggle({ editing, onToggle, disabled }: { editing: boolean; onToggle: () => void; disabled?: boolean }) {
  return editing ? (
    <button type="button" className="btn-primary" onClick={onToggle}>
      <Check className="h-4 w-4" aria-hidden /> Terminer
    </button>
  ) : (
    <button type="button" className="btn-secondary" disabled={disabled} onClick={onToggle}>
      <PenLine className="h-4 w-4" aria-hidden /> Modifier
    </button>
  );
}

/** Read-only preview, or the in-place editor with a way back to the generated version. */
export function DocumentView({
  markdown,
  originalMarkdown,
  editing,
  onChange,
  image,
  imageAlt,
}: {
  markdown: string;
  originalMarkdown?: string;
  editing: boolean;
  onChange: (markdown: string) => void;
  image?: FeatureImage | null;
  imageAlt?: string;
}) {
  const [confirmRestore, setConfirmRestore] = useState(false);
  if (!editing) return <MarkdownPreview markdown={stripTitle(markdown)} image={image} imageAlt={imageAlt} />;
  const canRestore = originalMarkdown !== undefined && originalMarkdown !== markdown;
  return (
    <>
      <DocumentEditor
        markdown={unwrapMarkdownFence(markdown)}
        onChange={onChange}
        image={image}
        imageAlt={imageAlt}
        toolbarExtra={
          canRestore && (
            <button type="button" className="btn-secondary min-h-[36px] px-3" onClick={() => setConfirmRestore(true)}>
              <RotateCcw className="h-4 w-4" aria-hidden /> Version générée
            </button>
          )
        }
      />
      <ConfirmDialog
        open={confirmRestore}
        title="Revenir à la version générée ?"
        confirmLabel="Revenir à la version générée"
        onConfirm={() => {
          setConfirmRestore(false);
          if (originalMarkdown !== undefined) onChange(originalMarkdown);
        }}
        onCancel={() => setConfirmRestore(false)}
      >
        Toutes vos modifications de ce document seront perdues.
      </ConfirmDialog>
    </>
  );
}
