const FLOW_HEADINGS = /^#{1,3}\s+(Parcours utilisateur|Parcours principaux|User flows?|Main user flows)\s*$/im;

export function hasMermaidBlock(markdown: string): boolean {
  return /^```mermaid\s*$/m.test(markdown);
}

/** Places the flow diagram at the top of the document's user flow section (or in a new one at the end). */
export function insertFlowDiagram(markdown: string, code: string, language: "fr" | "en"): string {
  const block = "```mermaid\n" + code.trim() + "\n```";
  const match = FLOW_HEADINGS.exec(markdown);
  if (!match) {
    const title = language === "en" ? "# User flow" : "# Parcours utilisateur";
    return `${markdown.trimEnd()}\n\n${title}\n\n${block}\n`;
  }
  const end = match.index + match[0].length;
  return `${markdown.slice(0, end)}\n\n${block}\n${markdown.slice(end).replace(/^\n*/, "\n")}`;
}
