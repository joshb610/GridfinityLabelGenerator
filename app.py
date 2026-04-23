"""FastAPI web application for the Gridfinity label generator."""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.fragments import fragment_description_table
from core.generator import export_to_bytes, generate

_MAX_GENERATION_ATTEMPTS = 3


def _generate_with_retry(cfg):
    """Retry generate() on non-deterministic OCCT failures (BRep_API errors)."""
    last_exc = None
    for attempt in range(_MAX_GENERATION_ATTEMPTS):
        try:
            return generate(cfg)
        except Exception as e:
            last_exc = e
            if attempt < _MAX_GENERATION_ATTEMPTS - 1:
                logger.warning("Generation attempt %d failed for %s: %s — retrying", attempt + 1, cfg.name, e)
    raise last_exc

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gridfinity Label Generator")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class LabelConfig(BaseModel):
    name: str = "label"
    base: str = "pred"
    width: float = 1.0
    width_unit: str = "u"          # "u" or "mm"
    height: float | None = None
    depth: float = 0.4
    divisions: int = 1
    labels: list[str] = Field(default_factory=lambda: ["Label"])
    font: str | None = None
    font_style: str = "bold"        # regular | bold | italic
    font_size: float | None = None
    font_size_maximum: float | None = None
    margin: float | None = None
    style: str = "embossed"        # embossed | debossed | embedded
    label_gap: float = 2.0
    column_gap: float = 0.4
    no_overheight: bool = False
    version: str = "latest"        # for cullenect base versions
    multimaterial: str = "none"   # "none" | "text" | "split" | "background"
    output_format: str = "step"    # "step" or "stl"
    body_depth: float | None = None  # base Z half-thickness; None = same as depth


class GenerateRequest(BaseModel):
    configs: list[LabelConfig]


# ---------------------------------------------------------------------------
# Preview endpoint — returns STL binary for Three.js rendering
# ---------------------------------------------------------------------------

@app.post("/api/preview")
def preview(config: LabelConfig):
    """
    Generate a single label and return STL for 3D preview.

    Single-material: returns binary STL (Content-Type: model/stl).
    Multi-material:  returns JSON with base64-encoded body + text STLs.
    """
    import base64

    try:
        result = _generate_with_retry(config)
    except Exception as e:
        logger.exception("Preview generation failed")
        raise HTTPException(status_code=500, detail=str(e))

    is_mm = config.multimaterial not in ("none", "", False)
    if is_mm and result.text is not None:
        body_b64 = base64.b64encode(export_to_bytes(result.body, "stl")).decode()
        text_b64 = base64.b64encode(export_to_bytes(result.text, "stl")).decode()
        return JSONResponse({"multimaterial": True, "body": body_b64, "text": text_b64})

    stl_bytes = export_to_bytes(result.body, "stl")
    return Response(content=stl_bytes, media_type="model/stl")


# ---------------------------------------------------------------------------
# Generate endpoint — returns ZIP of all label files
# ---------------------------------------------------------------------------

@app.post("/api/generate")
def generate_labels(request: GenerateRequest):
    """Generate all label configs and return a ZIP archive."""
    if not request.configs:
        raise HTTPException(status_code=400, detail="No label configs provided")

    errors = []
    generated = 0
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cfg in request.configs:
            fmt = cfg.output_format
            safe_name = cfg.name.replace(" ", "_")
            try:
                result = _generate_with_retry(cfg)
                if cfg.multimaterial not in ("none", "", False):
                    zf.writestr(f"{safe_name}/{safe_name}_body.{fmt}", export_to_bytes(result.body, fmt))
                    if result.text:
                        zf.writestr(f"{safe_name}/{safe_name}_text.{fmt}", export_to_bytes(result.text, fmt))
                else:
                    zf.writestr(f"{safe_name}.{fmt}", export_to_bytes(result.body, fmt))
                generated += 1
            except Exception as e:
                logger.exception("Label generation failed for %s", cfg.name)
                errors.append(f"• {cfg.name}: {e}")

        if errors:
            zf.writestr("_errors.txt",
                "The following labels failed to generate:\n\n" + "\n".join(errors))

    if generated == 0:
        raise HTTPException(status_code=500,
            detail=f"All labels failed. First error: {errors[0] if errors else 'unknown'}")

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="labels.zip"'},
    )


# ---------------------------------------------------------------------------
# Single-label download (convenience, skips ZIP for one non-multimaterial label)
# ---------------------------------------------------------------------------

@app.post("/api/generate/single")
def generate_single(config: LabelConfig):
    """Generate a single label and return the file directly (no ZIP)."""
    try:
        result = _generate_with_retry(config)
    except Exception as e:
        logger.exception("Single label generation failed")
        raise HTTPException(status_code=500, detail=str(e))

    fmt = config.output_format
    safe_name = config.name.replace(" ", "_")

    if config.multimaterial not in ("none", "", False):
        # Still ZIP for multi-material even for a single label
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{safe_name}_body.{fmt}", export_to_bytes(result.body, fmt))
            if result.text:
                zf.writestr(f"{safe_name}_text.{fmt}", export_to_bytes(result.text, fmt))
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.zip"'},
        )

    file_bytes = export_to_bytes(result.body, fmt)
    media = "model/step" if fmt == "step" else "model/stl"
    return Response(
        content=file_bytes,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.{fmt}"'},
    )


# ---------------------------------------------------------------------------
# Fragment reference
# ---------------------------------------------------------------------------

@app.get("/api/fragments")
def list_fragments():
    rows = fragment_description_table()
    return JSONResponse([
        {
            "names": row.names,
            "description": row.description,
            "examples": row.examples,
        }
        for row in rows
    ])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
