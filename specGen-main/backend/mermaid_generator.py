from __future__ import annotations

import re

from openai_client import get_model_name, get_openai_client

SYSTEM_PROMPT = (
    "You are a senior UX architect. "
    "Convert a context markdown document into a Mermaid user flow diagram. "
    "Return Mermaid code only, without explanation. "
    "Use valid Mermaid syntax compatible with flowchart TD. "
    "Keep the diagram readable, concise, and structured. "
    "Do not invent major steps that are not supported by the source document."
)

_NODE_LABEL = re.compile(r"[\[({]")
_BRACKETS = {"[": "]", "(": ")", "{": "}"}


def _extract_mermaid_code_block(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```"):
        parts = stripped.split("```")
        for part in parts:
            candidate = part.strip()
            if not candidate:
                continue
            if candidate.startswith("mermaid"):
                return candidate[len("mermaid"):].strip()
    return stripped


def find_mermaid_problems(code: str) -> list[str]:
    """Cheap checks for the mistakes models make most; the frontend parser catches the rest."""
    problems: list[str] = []
    lines = [line for line in code.splitlines() if line.strip() and not line.strip().startswith("%%")]
    if not lines or not re.match(r"^\s*(flowchart|graph)\s+(TD|TB|LR|RL|BT)\b", lines[0]):
        problems.append("The first line must be 'flowchart TD'.")
    for number, line in enumerate(lines[1:], start=2):
        stack: list[str] = []
        in_quotes = False
        for char in line:
            if char == '"':
                in_quotes = not in_quotes
            elif in_quotes:
                continue
            elif char in _BRACKETS:
                stack.append(_BRACKETS[char])
            elif char in _BRACKETS.values():
                if not stack or stack.pop() != char:
                    stack.append("!")
                    break
        if stack or in_quotes:
            problems.append(
                f"Line {number} has unbalanced brackets or quotes: {line.strip()}. "
                'Put labels containing brackets, quotes or punctuation in double quotes: A["Label (detail)"].'
            )
    return problems[:10]


def _ask(messages: list[dict[str, str]]) -> str:
    response = get_openai_client().chat.completions.create(model=get_model_name(), temperature=0, messages=messages)
    content = response.choices[0].message.content or "flowchart TD\n    A[No content]"
    return _extract_mermaid_code_block(content)


def _fix_messages(base: list[dict[str, str]], code: str, problems: str) -> list[dict[str, str]]:
    return [
        *base,
        {"role": "assistant", "content": code},
        {
            "role": "user",
            "content": "This Mermaid code does not render:\n"
            f"{problems}\n"
            "Return the complete corrected diagram, Mermaid code only, with the same content.",
        },
    ]


def generate_mermaid_flow_from_context(
    markdown_text: str, language: str = "fr", previous_code: str | None = None, error: str | None = None
) -> str:
    user_prompt = "\n\n".join(
        [
            f"Output language for node labels: {'French' if language == 'fr' else 'English'}",
            "Expected format:",
            "flowchart TD",
            "Constraints:",
            "- Start with 'flowchart TD'.",
            "- Model the main user journey and key branching points.",
            "- Include user actions, system feedback, and important navigation transitions when available.",
            "- Keep between 8 and 20 nodes when possible.",
            "- Use short labels, in double quotes when they contain punctuation: A[\"Label (detail)\"].",
            "- Node ids are letters and digits only (A, B1, step2).",
            "- Avoid unsupported Mermaid features.",
            "- Return only Mermaid code.",
            f"Source context markdown:\n{markdown_text}",
        ]
    )
    base = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]

    # The frontend could not parse the previous diagram: one fix with the parser's message.
    if previous_code and error:
        return _ask(_fix_messages(base, previous_code, error))

    code = _ask(base)
    problems = find_mermaid_problems(code)
    if problems:
        fixed = _ask(_fix_messages(base, code, "\n".join(f"- {problem}" for problem in problems)))
        if len(find_mermaid_problems(fixed)) <= len(problems):
            code = fixed
    return code
