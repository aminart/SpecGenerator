from __future__ import annotations

from openai_client import get_model_name, get_openai_client


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


def generate_mermaid_flow_from_context(markdown_text: str, language: str = "fr") -> str:
    client = get_openai_client()

    system_prompt = (
        "You are a senior UX architect. "
        "Convert a context markdown document into a Mermaid user flow diagram. "
        "Return Mermaid code only, without explanation. "
        "Use valid Mermaid syntax compatible with flowchart TD. "
        "Keep the diagram readable, concise, and structured. "
        "Do not invent major steps that are not supported by the source document."
    )

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
            "- Use short labels.",
            "- Avoid unsupported Mermaid features.",
            "- Return only Mermaid code.",
            f"Source context markdown:\n{markdown_text}",
        ]
    )

    response = client.chat.completions.create(
        model=get_model_name(),
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content or "flowchart TD\n    A[No content]"
    return _extract_mermaid_code_block(content)
