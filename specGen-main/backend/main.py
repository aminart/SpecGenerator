"""HTTP API for the spec generator.

Exposes the existing Python generation pipeline (context, journeys, Mermaid,
UX/HMI spec) and the document exports to the React frontend. When the
frontend has been built (frontend/dist), it is also served from here so the
whole app runs from a single process.
"""
from __future__ import annotations

import base64
import io
import json
import re
import time
import unicodedata
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from context_generator import generate_context_markdown
from document_export import (
    build_component_library_summary,
    build_context_docx_from_template,
    build_context_source_payload,
    build_docx_from_template,
    build_export_html,
    format_generation_error,
    get_context_default_title,
    get_context_document_subtitle,
    get_spec_default_title,
    get_spec_document_subtitle,
    is_timeout_error,
    normalize_markdown_title,
)
from journey_analysis import analyze_user_journeys_from_json
from json_analysis import analyze_json_structure, classify_component_scope
from markdown_cleanup import unwrap_markdown_fence
from drawio_converter import NotADrawioFile
from markdown_converter import SUPPORTED_EXTENSIONS, convert_to_markdown
from mermaid_generator import generate_mermaid_flow_from_context
from app_paths import frontend_dist_dir
from openai_client import get_missing_settings, get_model_name, is_custom_configured
from settings_api import router as settings_router
from spec_generator import generate_spec

SPEC_TEMPLATE_KEY = "ux_hmi_detailed"
FRONTEND_DIST = frontend_dist_dir()

Language = Literal["fr", "en"]
DetailLevel = Literal["compact", "standard", "detailed"]

app = FastAPI(title="Spec Generator API")
app.include_router(settings_router)


class SourceFile(BaseModel):
    name: str
    content: Any


class ContextRequest(BaseModel):
    designer_description: str = ""
    markdown_sources: list[SourceFile] = Field(default_factory=list)
    json_sources: list[SourceFile] = Field(default_factory=list)
    component_library: Any | None = None
    language: Language = "fr"
    # The interface always wants the most detailed document.
    detail_level: DetailLevel = "detailed"
    mode: Literal["standard", "light"] = "standard"


class MermaidRequest(BaseModel):
    markdown: str
    language: Language = "fr"
    # Sent by the frontend when the diagram it received does not parse: the model fixes it.
    previous_code: str | None = None
    error: str | None = None


class SpecRequest(BaseModel):
    business_context: str = ""
    spec_json: Any
    component_library: Any | None = None
    language: Language = "fr"
    # The interface always wants the most detailed document.
    detail_level: DetailLevel = "detailed"


class MarkdownDocument(BaseModel):
    name: str
    markdown: str


class MarkdownBundleRequest(BaseModel):
    documents: list[MarkdownDocument]


class ExportRequest(BaseModel):
    markdown: str
    language: Language = "fr"
    image_base64: str | None = None
    image_mime: str | None = None


def _require_llm() -> None:
    if not is_custom_configured():
        raise HTTPException(
            status_code=503,
            detail=f"Paramètres de connexion incomplets : {', '.join(get_missing_settings())}. Renseignez-les dans Paramètres.",
        )


def _generation_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=504 if is_timeout_error(exc) else 500, detail=format_generation_error(exc))


def _aggregate_json_sources(sources: list[SourceFile]) -> str:
    if not sources:
        return ""
    if len(sources) == 1:
        return json.dumps(sources[0].content, ensure_ascii=False, indent=2)
    return json.dumps(
        {
            "source_type": "multi_json_context",
            "file_count": len(sources),
            "files": [{"file_name": source.name, "content": source.content} for source in sources],
        },
        ensure_ascii=False,
        indent=2,
    )


def _aggregate_markdown_sources(sources: list[SourceFile]) -> str:
    contents = [(source.name, str(source.content or "").strip()) for source in sources]
    contents = [(name, content) for name, content in contents if content]
    if len(contents) == 1:
        return contents[0][1]
    return "\n\n---\n\n".join(f"# Source Markdown: {name}\n\n{content}" for name, content in contents)


def _component_library_summary(component_library: Any | None) -> str:
    if component_library is None:
        return ""
    return build_component_library_summary(analyze_json_structure(component_library))


@lru_cache(maxsize=16)
def _cached_context_analysis(payload_text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = json.loads(payload_text)
    analysis = analyze_json_structure(payload)
    return analysis, analyze_user_journeys_from_json(payload, analysis)


def _safe_filename(title: str, fallback: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_title).strip("-").lower()
    return slug[:60] or fallback


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "configured": is_custom_configured(),
        "missing": get_missing_settings(),
        "model": get_model_name(),
    }


@app.post("/api/context/generate")
def generate_context(request: ContextRequest) -> dict[str, Any]:
    _require_llm()
    json_text = _aggregate_json_sources(request.json_sources)
    markdown_text = _aggregate_markdown_sources(request.markdown_sources)
    if not json_text and not markdown_text:
        raise HTTPException(status_code=400, detail="Veuillez fournir au moins un JSON global ou un fichier Markdown de contexte.")

    timing_start = time.perf_counter()
    context_source_text, _ = build_context_source_payload(json_text, markdown_text)
    analysis, journey_result = _cached_context_analysis(context_source_text)
    analysis_duration = time.perf_counter() - timing_start

    priority_parts: list[str] = []
    if markdown_text:
        priority_parts.append(f"# Markdown de contexte projet\n\n{markdown_text}")
    if request.designer_description.strip():
        priority_parts.append(f"# Description designer\n\n{request.designer_description.strip()}")

    # The designer description is already in the priority documents: it is not sent twice.
    generation_kwargs = dict(
        json_source=json_text,
        language=request.language,
        detail_level=request.detail_level,
        analysis=analysis,
        component_library_summary=_component_library_summary(request.component_library),
        priority_context_documents="\n\n---\n\n".join(priority_parts),
    )

    retried_light = False
    llm_start = time.perf_counter()
    try:
        try:
            generated = generate_context_markdown(context_mode=request.mode, **generation_kwargs)
        except Exception as exc:
            if request.mode != "standard" or not is_timeout_error(exc):
                raise
            retried_light = True
            llm_start = time.perf_counter()
            generated = generate_context_markdown(context_mode="light", **generation_kwargs)
    except Exception as exc:
        raise _generation_error(exc) from exc

    return {
        "markdown": generated["markdown"],
        "warnings": generated["warnings"],
        "corrected": generated["corrected"],
        "journey_markdown": journey_result["journey_markdown"],
        "journey_mermaid": journey_result["journey_mermaid"],
        "retried_light": retried_light,
        "timings": {
            "analysis": round(analysis_duration, 1),
            "llm": round(time.perf_counter() - llm_start, 1),
            "total": round(time.perf_counter() - timing_start, 1),
        },
    }


@app.post("/api/context/mermaid")
def generate_mermaid(request: MermaidRequest) -> dict[str, str]:
    _require_llm()
    try:
        return {
            "mermaid": generate_mermaid_flow_from_context(
                request.markdown, request.language, previous_code=request.previous_code, error=request.error
            )
        }
    except Exception as exc:
        raise _generation_error(exc) from exc


@app.post("/api/spec/generate")
def generate_spec_document(request: SpecRequest) -> dict[str, Any]:
    _require_llm()
    timing_start = time.perf_counter()
    analysis = analyze_json_structure(request.spec_json)
    scope = classify_component_scope(analysis)
    business_context = request.business_context.strip()

    try:
        generated = generate_spec(
            json_source=json.dumps(request.spec_json, ensure_ascii=False, indent=2),
            # The context goes in once, as the priority source: passing it a second time as
            # business context only doubled the prompt.
            business_context="",
            language=request.language,
            detail_level=request.detail_level,
            template_key=SPEC_TEMPLATE_KEY,
            analysis=analysis,
            custom_template=None,
            component_library_summary=_component_library_summary(request.component_library),
            priority_context_documents=f"# Contexte de référence\n\n{business_context}" if business_context else None,
            component_scope_label=scope["label"],
            component_scope_rationale=scope["rationale"],
        )
    except Exception as exc:
        raise _generation_error(exc) from exc

    return {
        "markdown": generated["markdown"],
        "warnings": generated["warnings"],
        "corrected": generated["corrected"],
        "inventory": generated["inventory"],
        "scope": scope,
        "timings": {"total": round(time.perf_counter() - timing_start, 1)},
    }


@app.post("/api/markdown/convert")
def convert_document(file: UploadFile = File(...)) -> dict[str, str]:
    filename = file.filename or "document"
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Format non pris en charge ({extension or 'inconnu'}). Formats acceptés : {', '.join(sorted(SUPPORTED_EXTENSIONS))}.",
        )
    # "schema.drawio.png" -> "schema"
    stem = re.sub(r"\.(drawio|dio)$", "", Path(filename).stem, flags=re.IGNORECASE)
    try:
        markdown_text = convert_to_markdown(file.file.read(), extension, stem)
    except NotADrawioFile as exc:
        raise HTTPException(status_code=422, detail=f"{filename} : {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Conversion impossible de {filename} : {exc}") from exc
    if not markdown_text.strip():
        raise HTTPException(status_code=422, detail=f"Aucun texte exploitable n'a été trouvé dans {filename}.")
    return {"name": f"{stem}.md", "markdown": markdown_text}


@app.post("/api/markdown/bundle")
def bundle_markdown(request: MarkdownBundleRequest) -> Response:
    buffer = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for document in request.documents:
            name, index = document.name, 1
            while name in used_names:
                index += 1
                name = f"{Path(document.name).stem}-{index}.md"
            used_names.add(name)
            archive.writestr(name, document.markdown)
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="markdown.zip"'},
    )


@app.post("/api/export/{kind}/{fmt}")
def export_document(kind: Literal["context", "spec"], fmt: Literal["md", "html", "docx"], request: ExportRequest) -> Response:
    # Documents generated before the fence cleanup may still be wrapped in ```markdown.
    request.markdown = unwrap_markdown_fence(request.markdown)
    if kind == "context":
        title = normalize_markdown_title(request.markdown, get_context_default_title(request.language))
        subtitle = get_context_document_subtitle(request.language)
    else:
        title = normalize_markdown_title(request.markdown, get_spec_default_title(request.language))
        subtitle = get_spec_document_subtitle(request.language)

    image_data = request.image_base64 if kind == "spec" else None
    image_mime = request.image_mime if image_data else None
    filename = _safe_filename(title, kind)

    if fmt == "md":
        content: bytes = request.markdown.encode("utf-8")
        media_type = "text/markdown; charset=utf-8"
    elif fmt == "html":
        content = build_export_html(request.markdown, title, subtitle, None, request.language, image_data, image_mime).encode("utf-8")
        media_type = "text/html; charset=utf-8"
    else:
        if kind == "context":
            content = build_context_docx_from_template(request.markdown, title, subtitle, request.language)
        else:
            image_bytes = base64.b64decode(image_data) if image_data else None
            content = build_docx_from_template(request.markdown, title, subtitle, request.language, image_bytes)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}.{fmt}"'},
    )


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file() and FRONTEND_DIST in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
