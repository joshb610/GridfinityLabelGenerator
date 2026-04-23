"""Core label generation logic."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import NamedTuple

import build123d as bd
import pint
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Compound,
    Location,
    Locations,
    Mode,
    Vector,
    add,
    export_step,
    extrude,
)

from .bases.cullenect import CullenectBase
from .bases.modern import ModernBase
from .bases.none import NoneBase
from .bases.plain import PlainBase
from .bases.pred import PredBase, PredBoxBase
from .label import render_divided_label
from .options import LabelStyle, RenderOptions
from .util import batched, unit_registry

logger = logging.getLogger(__name__)

BASE_MAP = {
    "pred": PredBase,
    "predbox": PredBoxBase,
    "plain": PlainBase,
    "cullenect": CullenectBase,
    "modern": ModernBase,
    "none": NoneBase,
}


class GenerateResult(NamedTuple):
    """Holds the generated geometry for a single label config."""
    body: Compound
    text: Compound | None  # Only set for multi-material


def _make_args(req):
    """Build an argparse-like namespace from a request object so base constructors work."""
    import argparse

    width_unit = getattr(req, "width_unit", "u")
    try:
        width = pint.Quantity(req.width, unit_registry.u if width_unit == "u" else unit_registry.mm)
    except Exception:
        width = pint.Quantity(req.width, unit_registry.u)

    height = pint.Quantity(req.height, unit_registry.mm) if req.height else None
    margin_val = req.margin if req.margin is not None else None

    return argparse.Namespace(
        width=width,
        height=height,
        depth=req.depth,
        style=LabelStyle(req.style) if isinstance(req.style, str) else req.style,
        base=req.base,
        version=getattr(req, "version", "latest") or "latest",
        margin=pint.Quantity(margin_val, unit_registry.mm) if margin_val is not None else None,
        font=req.font,
        font_style=req.font_style,
        font_size=req.font_size,
        font_size_maximum=req.font_size_maximum,
        font_path=None,
        no_overheight=req.no_overheight,
        column_gap=req.column_gap,
        label_gap=req.label_gap,
        body_depth=getattr(req, "body_depth", None),
    )


def generate(req) -> GenerateResult:
    """
    Generate label geometry from a request.

    Returns a GenerateResult with:
      - body:  the full assembly (single-material) or base-only (multi-material)
      - text:  None for single-material, or the text solid for multi-material
    """
    base_cls = BASE_MAP.get(req.base)
    if base_cls is None:
        raise ValueError(f"Unknown base type: {req.base!r}")

    args = _make_args(req)

    # Resolve width defaults
    if args.width.units == unit_registry.dimensionless:
        default_unit = base_cls.DEFAULT_WIDTH_UNIT or unit_registry.mm
        args.width = pint.Quantity(args.width.magnitude, default_unit)

    # Resolve margin defaults
    if args.margin is None:
        args.margin = base_cls.DEFAULT_MARGIN

    options = RenderOptions.from_request(req)

    labels = [x.replace("\\n", "\n") for x in req.labels]
    divisions = req.divisions or len(labels)
    is_embossed = args.style == LabelStyle.EMBOSSED
    mm_mode = getattr(req, "multimaterial", "none")
    if isinstance(mm_mode, bool):
        mm_mode = "text" if mm_mode else "none"
    mm_mode = mm_mode or "none"
    multimaterial = mm_mode not in ("none", "")

    base_obj = base_cls(args)

    if base_obj.part:
        y_offset = base_obj.part.bounding_box().size.Y + req.label_gap
        label_area = base_obj.area
    else:
        h = args.height.to("mm").magnitude if args.height else 12.0
        w = args.width.to("mm").magnitude
        y_offset = h + req.label_gap
        label_area = Vector(X=w, Y=h)

    body_locations = []
    y = 0.0

    with BuildPart() as part:
        with BuildSketch(mode=Mode.PRIVATE) as label_sketch:
            all_labels = []
            for batch in batched(labels, divisions):
                body_locations.append((0, y))
                rendered = render_divided_label(
                    list(batch), label_area, divisions=divisions, options=options
                ).locate(Location([0, y]))
                all_labels.append(rendered)
                y -= y_offset
            add(all_labels)

        if base_obj.part:
            with Locations(body_locations):
                add(base_obj.part)

        # For embossed multi-material we do NOT extrude text onto the body —
        # the body stays flat and the text is a separate solid.
        if not (multimaterial and is_embossed):
            extrude(
                label_sketch.sketch,
                amount=req.depth if is_embossed else -req.depth,
                mode=Mode.ADD if is_embossed else Mode.SUBTRACT,
            )

    # Extra bottom slab (text color) — one per body location, Z=-body_depth to Z=-0.4.
    # Uses make_extra_slab() which extrudes the outer face at the correct absolute Z,
    # the same way make_background_slab() works (confirmed reliable pattern).
    extra_slabs = []
    if hasattr(base_obj, "make_extra_slab"):
        for loc_x, loc_y in body_locations:
            slab = base_obj.make_extra_slab(loc_x, loc_y)
            if slab is not None:
                extra_slabs.append(slab)

    # Build the text solid for multi-material
    text_part = None
    if multimaterial:
        text_extrusion = extrude(label_sketch.sketch, amount=req.depth)

        if mm_mode == "text" or not is_embossed or base_obj.part is None:
            # ── Mode "text": original behaviour ────────────────────────────────
            # Body = full assembled base (flat face), Text = raised text shapes only.
            text_part = Compound([text_extrusion] + extra_slabs) if extra_slabs else text_extrusion

        elif mm_mode == "split":
            # ── Mode "split": cut at the label face plane (Z=0) ────────────────
            # Body = base structure below Z=0.
            # Text = raised surfaces above Z=0 + text extrusions.
            BIG = 10_000.0
            above_z0 = Box(BIG, BIG, BIG).locate(Location((0, 0,  BIG / 2)))
            below_z0 = Box(BIG, BIG, BIG).locate(Location((0, 0, -BIG / 2)))
            try:
                body_shape = part.part - above_z0
                label_face = part.part - below_z0
                text_shapes = [text_extrusion] + extra_slabs
                if label_face.volume > 1e-6:
                    text_shapes.insert(0, label_face)
                return GenerateResult(
                    body=Compound(body_shape),
                    text=Compound(text_shapes),
                )
            except Exception:
                logger.warning("Z-split failed, falling back to text-only mm")
                text_part = text_extrusion

        elif mm_mode == "background":
            # ── Mode "background": body = flat label face slab ─────────────────
            # Slab goes downward from Z=0 — its top face IS the visible background
            # color at the label face. Text extrudes upward above it (Z=0→+depth).
            # Subtract slabs from the base so the background area is carved out of
            # the text-color file. With body_depth > depth, text-color material
            # remains below the slab, making the back face text-colored.
            bg_slabs = []
            for loc_x, loc_y in body_locations:
                if hasattr(base_obj, "make_background_slab"):
                    slab = base_obj.make_background_slab(req.depth, loc_x, loc_y)
                else:
                    bg_area = getattr(base_obj, "background_area", label_area)
                    slab = Box(
                        float(bg_area.X), float(bg_area.Y), req.depth,
                    ).locate(Location((loc_x, loc_y, -req.depth / 2)))
                bg_slabs.append(slab)
            base_shape = part.part
            for slab in bg_slabs:
                try:
                    base_shape = base_shape - slab
                except Exception:
                    pass

            # Subtract bg_slabs from extra_slabs — they overlap volumetrically in
            # the Z=0→-depth band (inner face ⊂ outer face), so without this the
            # slicer sees the same voxel claimed by both files.
            clean_extra = list(extra_slabs)
            for slab in bg_slabs:
                for i, es in enumerate(clean_extra):
                    try:
                        clean_extra[i] = es - slab
                    except Exception:
                        pass

            return GenerateResult(
                body=Compound(bg_slabs),
                text=Compound([base_shape, text_extrusion] + clean_extra),
            )

        elif mm_mode == "background_full":
            # ── Mode "background_full": bg fills entire body depth ─────────────
            # Background = inner face area slab from Z=0 all the way to Z=-fill_depth
            #              (the full label body thickness, not just the face depth).
            # Text       = outer rim/structure + raised text letters.
            # Bottom view: bg color fills the center, text color is visible as a
            #              narrow rim frame around the edges of the bottom surface.
            _HALF = 0.4
            fill_depth = max(getattr(args, "body_depth", None) or _HALF, _HALF)

            bg_full_slabs = []
            for loc_x, loc_y in body_locations:
                if hasattr(base_obj, "make_background_slab"):
                    slab = base_obj.make_background_slab(fill_depth, loc_x, loc_y)
                else:
                    bg_area = getattr(base_obj, "background_area", label_area)
                    slab = Box(
                        float(bg_area.X), float(bg_area.Y), fill_depth,
                    ).locate(Location((loc_x, loc_y, -fill_depth / 2)))
                bg_full_slabs.append(slab)

            base_shape = part.part
            for slab in bg_full_slabs:
                try:
                    base_shape = base_shape - slab
                except Exception:
                    pass

            # Subtract bg_full_slabs from extra_slabs to remove volumetric overlap
            # (inner face ⊂ outer face across the full Z=0→-fill_depth band).
            clean_extra = list(extra_slabs)
            for slab in bg_full_slabs:
                for i, es in enumerate(clean_extra):
                    try:
                        clean_extra[i] = es - slab
                    except Exception:
                        pass

            return GenerateResult(
                body=Compound(bg_full_slabs),
                text=Compound([base_shape, text_extrusion] + clean_extra),
            )

        else:
            # Unknown mode — fall back to text-only
            text_part = text_extrusion

    # Embedded single-material: keep text and body as a two-body compound
    if args.style == LabelStyle.EMBEDDED and not multimaterial:
        embedded = extrude(label_sketch.sketch, amount=-req.depth)
        return GenerateResult(body=Compound([part.part, embedded] + extra_slabs), text=None)

    if extra_slabs and not multimaterial:
        return GenerateResult(body=Compound([part.part] + extra_slabs), text=None)

    return GenerateResult(body=Compound(part.part), text=text_part)


def export_to_bytes(shape: Compound, fmt: str) -> bytes:
    """Export a shape to bytes in the requested format (step or stl)."""
    with tempfile.NamedTemporaryFile(suffix=f".{fmt}", delete=False) as f:
        tmp = Path(f.name)

    try:
        if fmt == "stl":
            bd.export_stl(shape, str(tmp))
        else:
            export_step(shape, str(tmp))
        return tmp.read_bytes()
    finally:
        tmp.unlink(missing_ok=True)
