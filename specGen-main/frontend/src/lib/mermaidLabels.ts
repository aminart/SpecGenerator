/**
 * Labels of a Mermaid flowchart, found in its code from what the user clicks in the
 * drawn diagram, so they can be renamed without touching the rest of the code.
 */

export type LabelTarget =
  | { kind: "node"; id: string }
  | { kind: "subgraph"; id: string }
  /** An edge label, by its drawn text and its rank among the edges drawn with that same text. */
  | { kind: "edge"; text: string; occurrence: number };

interface LabelRange {
  start: number;
  end: number;
  /** The label was written between double quotes. */
  quoted: boolean;
  /** Replacement for a node or subgraph declared without a label: its id followed by the new label. */
  insertAfterId?: boolean;
}

// Longest openers first, so "([" is not read as "(".
const SHAPES: [string, string[]][] = [
  ["(((", [")))"]],
  ["([", ["])"]],
  ["[[", ["]]"]],
  ["[(", [")]"]],
  ["((", ["))"]],
  ["{{", ["}}"]],
  ["[/", ["/]", "\\]"]],
  ["[\\", ["\\]", "/]"]],
  ["[", ["]"]],
  ["(", [")"]],
  ["{", ["}"]],
  [">", ["]"]],
];

const NOT_NODE_LINE = /^\s*(%%|style\s|classDef\s|class\s|linkStyle\s|click\s|subgraph\b|end\s*$|flowchart\b|graph\b|direction\s)/;

/** Offsets of the code's lines that can declare nodes and edges (no comments, styles or subgraph lines). */
function contentLines(code: string): { start: number; text: string }[] {
  const lines: { start: number; text: string }[] = [];
  let start = 0;
  for (const text of code.split("\n")) {
    if (!NOT_NODE_LINE.test(text)) lines.push({ start, text });
    start += text.length + 1;
  }
  return lines;
}

/** The label between an opener (already passed, at `from`) and its closer. */
function bracketContent(code: string, from: number, closers: string[]): LabelRange | null {
  let position = from;
  while (code[position] === " ") position++;
  if (code[position] === '"') {
    const close = code.indexOf('"', position + 1);
    return close < 0 ? null : { start: position + 1, end: close, quoted: true };
  }
  const ends = closers.map((closer) => code.indexOf(closer, from)).filter((index) => index >= 0);
  if (!ends.length) return null;
  const end = Math.min(...ends);
  if (code.slice(from, end).includes("\n")) return null;
  return { start: from, end, quoted: false };
}

/** Each node mention of the code, in order: its id and, when declared there, its label. */
function nodeMentions(code: string): { id: string; at: number; range: LabelRange | null }[] {
  const skipped = edgeRanges(code);
  const mentions: { id: string; at: number; range: LabelRange | null }[] = [];
  for (const line of contentLines(code)) {
    const lineEnd = line.start + line.text.length;
    let position = line.start;
    while (position < lineEnd) {
      const inEdgeLabel = skipped.find((range) => range.start <= position && position < range.end);
      if (inEdgeLabel) {
        position = inEdgeLabel.end + (inEdgeLabel.quoted ? 1 : 0);
        continue;
      }
      const char = code[position];
      if (char === "|") {
        const close = code.indexOf("|", position + 1);
        position = close < 0 || close > lineEnd ? lineEnd : close + 1;
        continue;
      }
      const token = /^\w+(?:-\w+)*/.exec(code.slice(position, lineEnd));
      if (!token || (position > line.start && /[\w]/.test(code[position - 1]))) {
        position++;
        continue;
      }
      const id = token[0];
      const after = position + id.length;
      const shape = SHAPES.find(([opener]) => code.startsWith(opener, after));
      const range = shape ? bracketContent(code, after + shape[0].length, shape[1]) : null;
      if (range && range.end <= lineEnd) {
        mentions.push({ id, at: position, range });
        const closer = range.quoted ? code.indexOf(shape![1][0], range.end + 1) : range.end;
        position = Math.max(range.end + 1, closer + 1);
      } else {
        mentions.push({ id, at: position, range: null });
        position = after;
      }
    }
  }
  return mentions;
}

function nodeRange(code: string, id: string): LabelRange | null {
  const mentions = nodeMentions(code).filter((mention) => mention.id === id);
  const declared = mentions.find((mention) => mention.range);
  if (declared?.range) return declared.range;
  const bare = mentions.find((mention) => !code.startsWith("@{", mention.at + id.length));
  return bare ? { start: bare.at + id.length, end: bare.at + id.length, quoted: false, insertAfterId: true } : null;
}

function subgraphRange(code: string, id: string): LabelRange | null {
  let start = 0;
  for (const text of code.split("\n")) {
    const match = /^(\s*subgraph\s+)(.*?)\s*$/.exec(text);
    if (match) {
      const rest = match[2];
      const restStart = start + match[1].length;
      if (rest === id) return { start: restStart + id.length, end: restStart + id.length, quoted: false, insertAfterId: true };
      if (rest.startsWith(id + "[") && rest.endsWith("]")) {
        return bracketContent(code, restStart + id.length + 1, ["]"]);
      }
    }
    start += text.length + 1;
  }
  return null;
}

/** Text as drawn: no line breaks, quotes or spaces, so the code and the drawing can be compared. */
export function comparableLabel(text: string): string {
  return text
    .replace(/<br\s*\/?>/gi, "")
    .replace(/#quot;/g, '"')
    .replace(/^"|"$/g, "")
    .replace(/\s+/g, "");
}

/** Every edge label of the code, in the order they are written. */
function edgeRanges(code: string): LabelRange[] {
  const ranges: LabelRange[] = [];
  for (const line of contentLines(code)) {
    // A -->|label| B, A -.->|label| B, A ==>|"label"| B
    for (const match of line.text.matchAll(/(?<=[-=.>ox]\s*)\|([^|]*)\|/g)) {
      const start = line.start + (match.index ?? 0) + 1;
      const inner = match[1];
      const quoted = /^\s*".*"\s*$/.test(inner);
      const offset = quoted ? inner.indexOf('"') + 1 : 0;
      ranges.push({ start: start + offset, end: start + (quoted ? inner.lastIndexOf('"') : inner.length), quoted });
    }
    // A -- label --> B, A -. label .-> B, A == label ==> B
    for (const match of line.text.matchAll(/(?<![-=.])(--|==|-\.)[ \t]+([^\n|]*?)[ \t]+(--[->xo]|==[=>xo]|\.-[->xo]?)/g)) {
      const start = line.start + (match.index ?? 0) + match[0].indexOf(match[2], match[1].length);
      const inner = match[2];
      const quoted = /^".*"$/.test(inner);
      ranges.push({ start: quoted ? start + 1 : start, end: start + (quoted ? inner.length - 1 : inner.length), quoted });
    }
  }
  return ranges.sort((a, b) => a.start - b.start);
}

function findRange(code: string, target: LabelTarget): LabelRange | null {
  if (target.kind === "node") return nodeRange(code, target.id);
  if (target.kind === "subgraph") return subgraphRange(code, target.id);
  const wanted = comparableLabel(target.text);
  const same = edgeRanges(code).filter((range) => comparableLabel(code.slice(range.start, range.end)) === wanted);
  return same[target.occurrence] ?? same[0] ?? null;
}

function fromCode(label: string): string {
  return label.replace(/<br\s*\/?>/gi, "\n").replace(/#quot;/g, '"').trim();
}

/** The label as the user reads it (line breaks as new lines), or null when it cannot be found in the code. */
export function readLabel(code: string, target: LabelTarget): string | null {
  const range = findRange(code, target);
  if (!range) return null;
  if (range.insertAfterId) return target.kind === "edge" ? null : target.id;
  return fromCode(code.slice(range.start, range.end));
}

/** The code with that label replaced, or null when it cannot be found or the new label is empty. */
export function renameLabel(code: string, target: LabelTarget, label: string): string | null {
  const text = label
    .trim()
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .join("<br/>");
  const range = findRange(code, target);
  if (!text || !range) return null;
  let value = text.replace(/"/g, "#quot;");
  if (target.kind === "edge") value = value.replace(/\|/g, "#124;");
  const needsQuotes = range.quoted || range.insertAfterId || /[[\](){}|<>#;&@"]/.test(value);
  if (range.insertAfterId) return code.slice(0, range.start) + `["${value}"]` + code.slice(range.end);
  if (needsQuotes && !range.quoted) value = `"${value}"`;
  return code.slice(0, range.start) + value + code.slice(range.end);
}
