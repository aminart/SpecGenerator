import remarkGfm from "remark-gfm";
import remarkParse from "remark-parse";
import { unified } from "unified";

/** How a block is edited in place: rich text, cell by cell, or as source code. */
export type BlockKind = "text" | "table" | "code" | "mermaid" | "rule" | "raw";

export interface MarkdownBlock {
  kind: BlockKind;
  /** The block's exact Markdown source. */
  source: string;
  start: number;
  end: number;
  /** Heading depth, for headings. */
  depth?: number;
  /** Code and language, for code blocks. */
  code?: string;
  lang?: string;
}

const parser = unified().use(remarkParse).use(remarkGfm);

const TEXT_TYPES = new Set(["heading", "paragraph", "list", "blockquote"]);

/** Splits a document into its top-level blocks, keeping each block's source offsets. */
export function splitBlocks(markdown: string): MarkdownBlock[] {
  const tree = parser.parse(markdown);
  const blocks: MarkdownBlock[] = [];
  for (const node of tree.children) {
    const start = node.position?.start.offset;
    const end = node.position?.end.offset;
    if (start === undefined || end === undefined) continue;
    let kind: BlockKind = "raw";
    if (TEXT_TYPES.has(node.type)) kind = "text";
    else if (node.type === "table") kind = "table";
    else if (node.type === "thematicBreak") kind = "rule";
    else if (node.type === "code") kind = node.lang === "mermaid" ? "mermaid" : "code";
    blocks.push({
      kind,
      source: markdown.slice(start, end),
      start,
      end,
      depth: node.type === "heading" ? node.depth : undefined,
      code: node.type === "code" ? node.value : undefined,
      lang: node.type === "code" ? (node.lang ?? "") : undefined,
    });
  }
  return blocks;
}

/** Replaces one block's source; an empty replacement removes the block and its surrounding blank lines. */
export function replaceBlock(markdown: string, block: MarkdownBlock, replacement: string): string {
  const before = markdown.slice(0, block.start);
  const after = markdown.slice(block.end);
  const text = replacement.trim();
  if (!text) return `${before.replace(/\s*$/, "")}\n\n${after.replace(/^\s*/, "")}`.trim() + "\n";
  return before + text + after;
}

export function insertAfter(markdown: string, block: MarkdownBlock, source: string): string {
  return `${markdown.slice(0, block.end)}\n\n${source.trim()}${markdown.slice(block.end)}`;
}

/** Fenced code block, with a fence longer than any backtick run inside the code. */
export function fenced(code: string, lang = ""): string {
  const longest = Math.max(2, ...(code.match(/`+/g) ?? []).map((run) => run.length));
  const fence = "`".repeat(longest + 1);
  return `${fence}${lang}\n${code.replace(/\n+$/, "")}\n${fence}`;
}

// ---------------------------------------------------------------------------
// DOM → Markdown, for blocks edited with contentEditable. It only needs to cover
// what react-markdown renders for these documents, plus what browsers insert
// while typing (div, br, b, i, span).
// ---------------------------------------------------------------------------

const INLINE_TAGS = new Set(["A", "B", "STRONG", "I", "EM", "CODE", "DEL", "S", "SPAN", "FONT", "BR", "IMG", "U", "SUB", "SUP", "MARK"]);
const BLOCK_TAGS = new Set(["P", "DIV", "H1", "H2", "H3", "H4", "H5", "H6", "UL", "OL", "BLOCKQUOTE", "PRE", "TABLE", "HR", "SECTION", "ARTICLE"]);

function wrap(marker: string, inner: string): string {
  const text = inner.trim();
  if (!text) return inner;
  const lead = inner.match(/^\s*/)?.[0] ?? "";
  const trail = inner.match(/\s*$/)?.[0] ?? "";
  return `${lead}${marker}${text}${marker}${trail}`;
}

/** Inline content of an element; line breaks come out as "\n". */
export function inlineMarkdown(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return (node.textContent ?? "").replace(/ /g, " ").replace(/​/g, "");
  if (!(node instanceof HTMLElement)) return "";
  const children = () => Array.from(node.childNodes).map(inlineMarkdown).join("");
  switch (node.tagName) {
    case "BR":
      return "\n";
    case "B":
    case "STRONG":
      return wrap("**", children());
    case "I":
    case "EM":
      return wrap("*", children());
    case "DEL":
    case "S":
      return wrap("~~", children());
    case "CODE": {
      const code = node.textContent ?? "";
      return code ? (code.includes("`") ? `\`\` ${code} \`\`` : `\`${code}\``) : "";
    }
    case "A": {
      const label = children();
      const href = node.getAttribute("href");
      return href && label.trim() ? `[${label.trim()}](${href})` : label;
    }
    case "IMG": {
      const src = node.getAttribute("src");
      return src ? `![${node.getAttribute("alt") ?? ""}](${src})` : "";
    }
    case "INPUT":
      return "";
    default:
      return children();
  }
}

function cleanLines(text: string): string {
  return text
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trim())
    .join("\n")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

function listMarkdown(list: HTMLElement): string {
  const ordered = list.tagName === "OL";
  let number = Number(list.getAttribute("start") ?? "1") || 1;
  const items: string[] = [];
  for (const item of Array.from(list.children)) {
    if (item.tagName !== "LI") continue;
    const marker = ordered ? `${number++}.` : "-";
    const indent = " ".repeat(marker.length + 1);
    const checkbox = item.querySelector(":scope > input[type=checkbox], :scope > p > input[type=checkbox]") as HTMLInputElement | null;
    const textParts: string[] = [];
    const nested: string[] = [];
    let inline = "";
    for (const child of Array.from(item.childNodes)) {
      if (child instanceof HTMLElement && (child.tagName === "UL" || child.tagName === "OL")) {
        nested.push(listMarkdown(child));
      } else if (child instanceof HTMLElement && BLOCK_TAGS.has(child.tagName)) {
        if (inline.trim()) textParts.push(inline);
        inline = "";
        textParts.push(inlineMarkdown(child));
      } else {
        inline += inlineMarkdown(child);
      }
    }
    if (inline.trim()) textParts.push(inline);
    const text = cleanLines(textParts.join("\n"));
    if (!text && !nested.length) continue;
    const task = checkbox ? (checkbox.checked ? "[x] " : "[ ] ") : "";
    const lines = [`${marker} ${task}${text.replace(/\n/g, `\n${indent}`)}`.trimEnd()];
    for (const sub of nested) lines.push(sub.replace(/^/gm, indent));
    items.push(lines.join("\n"));
  }
  return items.join("\n");
}

/** Text of a table cell, on one line, with pipes escaped. */
export function cellMarkdown(cell: Node): string {
  return inlineMarkdown(cell).replace(/\s*\n\s*/g, " ").replace(/\s+/g, " ").trim().replace(/(?<!\\)\|/g, "\\|");
}

export type Alignment = "left" | "center" | "right" | null;

export function tableMarkdown(rows: string[][], align: Alignment[] = []): string {
  const columns = Math.max(1, ...rows.map((row) => row.length));
  const pad = (row: string[]) => [...row, ...Array(columns - row.length).fill("")];
  const line = (row: string[]) => `| ${pad(row).join(" | ")} |`;
  const separator = Array.from({ length: columns }, (_, index) => {
    const value = align[index];
    return value === "center" ? ":---:" : value === "right" ? "---:" : value === "left" ? ":---" : "---";
  });
  const [header = [], ...body] = rows;
  return [line(header), `| ${separator.join(" | ")} |`, ...body.map(line)].join("\n");
}

export function readTable(table: HTMLTableElement): { rows: string[][]; align: Alignment[] } {
  const rows = Array.from(table.rows).map((row) => Array.from(row.cells).map(cellMarkdown));
  const align = Array.from(table.rows[0]?.cells ?? []).map((cell) => {
    const value = (cell.style.textAlign || cell.getAttribute("align") || "").toLowerCase();
    return value === "left" || value === "center" || value === "right" ? value : null;
  });
  return { rows, align };
}

/** Serializes the children of an edited container into Markdown blocks. */
export function blocksMarkdown(container: Node): string {
  const blocks: string[] = [];
  let inline = "";
  const flush = () => {
    const text = cleanLines(inline);
    if (text) blocks.push(text);
    inline = "";
  };
  for (const child of Array.from(container.childNodes)) {
    if (!(child instanceof HTMLElement) || INLINE_TAGS.has(child.tagName)) {
      inline += inlineMarkdown(child);
      continue;
    }
    flush();
    const tag = child.tagName;
    if (/^H[1-6]$/.test(tag)) {
      const text = cleanLines(inlineMarkdown(child)).replace(/\n/g, " ");
      if (text) blocks.push(`${"#".repeat(Number(tag[1]))} ${text}`);
    } else if (tag === "UL" || tag === "OL") {
      const list = listMarkdown(child);
      if (list) blocks.push(list);
    } else if (tag === "BLOCKQUOTE") {
      const inner = blocksMarkdown(child);
      if (inner) blocks.push(inner.replace(/^/gm, "> ").replace(/^> $/gm, ">"));
    } else if (tag === "PRE") {
      const lang = /language-(\S+)/.exec(child.querySelector("code")?.className ?? "")?.[1] ?? "";
      blocks.push(fenced(child.textContent ?? "", lang));
    } else if (tag === "TABLE") {
      const { rows, align } = readTable(child as HTMLTableElement);
      if (rows.length) blocks.push(tableMarkdown(rows, align));
    } else if (tag === "HR") {
      blocks.push("---");
    } else if (Array.from(child.children).some((element) => BLOCK_TAGS.has(element.tagName))) {
      // Browsers wrap new lines in <div>; nested block content is flattened.
      const inner = blocksMarkdown(child);
      if (inner) blocks.push(inner);
    } else {
      inline = inlineMarkdown(child);
      flush();
    }
  }
  flush();
  return blocks.join("\n\n");
}
