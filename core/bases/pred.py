from __future__ import annotations

import logging

import pint
from build123d import (
    Axis, BuildLine, BuildPart, BuildSketch, CenterArc, Circle, Compound,
    FilletPolyline, Location, Locations, Mode, Plane, Polyline, RectangleRounded,
    Sketch, Vector, add, chamfer, extrude, fillet, make_face, mirror,
)

from ..options import LabelStyle
from ..util import unit_registry
from . import LabelBase

logger = logging.getLogger(__name__)


def _outer_edge(width_mm: float, height_mm: float) -> Sketch:
    straight_width = width_mm - (1.9 * 2)
    with BuildSketch() as sketch:
        with BuildLine() as line:
            x = -straight_width / 2
            l1 = Polyline([(x - 1.9, 0), (x - 1.9, 2.85), (x - 0.9, 2.85)])
            FilletPolyline(
                [l1 @ 1, (x - 0.9, height_mm / 2), (0, height_mm / 2)],
                radius=0.9,
            )
            mirror(line.line, Plane.XZ)
            mirror(line.line, Plane.YZ)
        make_face()
        with Locations([(x - 0.4, 0, 0.4), (x + straight_width + 0.4, 0, 0.4)]):
            Circle(0.75, mode=Mode.SUBTRACT)
    return sketch.sketch


def _inner_edge(width_mm: float, height_mm: float) -> Sketch:
    straight_width = width_mm - (1.9 * 2)
    x = -straight_width / 2
    with BuildSketch() as sketch:
        with BuildLine() as line:
            a1 = CenterArc((x - 0.4, 0), 1.25, 0, 90)
            FilletPolyline(
                [a1 @ 1, (x - 0.4, (height_mm - 1) / 2), (0, (height_mm - 1) / 2)],
                radius=0.4,
            )
            fillet([line.vertices().sort_by_distance(a1 @ 1)[0]], radius=1)
            mirror(line.line, Plane.XZ)
            mirror(line.line, Plane.YZ)
        make_face()
    return sketch.sketch


class PredBase(LabelBase):
    DEFAULT_WIDTH = pint.Quantity("1u")
    DEFAULT_WIDTH_UNIT = unit_registry.u

    def __init__(self, args):
        def _convert_u_to_mm(u):
            return u * unit_registry.Quantity("42mm/u") - unit_registry.Quantity("4.2mm")

        with unit_registry.context("u", fn=_convert_u_to_mm):
            width_mm = args.width.to("mm").magnitude

        HALF = 0.4  # fixed pred base half-thickness — never changes with depth or body_depth

        recessed = args.style == LabelStyle.EMBOSSED
        # body_depth = total thickness below Z=0 (label face).
        # Default HALF means the original symmetric shape (Z=-0.4…+0.4).
        # Any value > HALF adds a text-colored slab below without touching the rim.
        body_depth = max(getattr(args, "body_depth", None) or HALF, HALF)
        height_mm = 11.5
        if args.height is not None:
            height_mm = args.height.to("mm").magnitude
        if height_mm < 9.0:
            raise ValueError(
                f"Pred base requires height ≥ 9 mm (got {height_mm:.1f} mm). "
                "The base geometry has fixed arc/fillet values that need this minimum space."
            )

        outer_face = _outer_edge(width_mm=width_mm, height_mm=height_mm)
        inner_face = _inner_edge(width_mm=width_mm, height_mm=height_mm)

        # Standard symmetric base — always Z=-HALF…+HALF regardless of depth/body_depth.
        with BuildPart() as part:
            add(outer_face)
            extrude(amount=HALF, both=True)

            if recessed:
                add(inner_face)
                extrude(amount=HALF, mode=Mode.SUBTRACT)

            fillet_edges = [
                *part.edges().group_by(Axis.Z)[-1],
                *part.edges().group_by(Axis.Z)[0],
            ]
            fillet(fillet_edges, radius=0.2)

        straight_width = width_mm - (1.9 * 2)
        self.area = Vector(width_mm - 5.5, height_mm - 1)
        self.background_area = Vector(straight_width, height_mm - 1)
        self._background_face = inner_face
        self._width_mm = width_mm
        self._height_mm = height_mm
        self._body_depth = body_depth
        self._extra_depth = (body_depth - HALF) if (body_depth - HALF > 1e-4 and recessed) else 0.0

        if recessed:
            self.part = part.part
        else:
            self.part = part.part.locate(Location((0, 0, -HALF)))

    def make_background_slab(self, depth: float, loc_x: float = 0, loc_y: float = 0):
        """Return a solid matching the inner recessed face for background multi-material."""
        face = self._background_face.located(Location((loc_x, loc_y, 0)))
        return extrude(face, amount=-depth)

    def make_extra_slab(self, loc_x: float = 0, loc_y: float = 0):
        """Slab from Z=0 down to Z=-body_depth (text color).
        Identical pattern to make_background_slab: face at Z=0, negative amount."""
        if self._extra_depth <= 0:
            return None
        face = _outer_edge(self._width_mm, self._height_mm).located(Location((loc_x, loc_y, 0)))
        return extrude(face, amount=-self._body_depth)


class PredBoxBase(LabelBase):
    DEFAULT_WIDTH = None
    DEFAULT_WIDTH_UNIT = unit_registry.u
    DEFAULT_MARGIN = unit_registry.Quantity(3, "mm")

    def __init__(self, args):
        def _convert_u_to_mm(u: pint.Quantity):
            sizes = {4: 25.5, 5: 67.5, 6: 82, 7: 82}
            if u.magnitude not in sizes:
                raise ValueError("Pred box only supports 4u, 5u, 6u, 7u")
            return pint.Quantity(sizes[u.magnitude], "mm")

        with unit_registry.context("u", fn=_convert_u_to_mm):
            width_mm = args.width.to("mm").magnitude

        r_edge = 3.5
        depth = 0.85
        chamfer_d = 0.2
        height_mm = 24.5
        if args.height is not None:
            height_mm = args.height.to("mm").magnitude

        with BuildPart() as part:
            with BuildSketch() as sketch:
                RectangleRounded(width_mm, height_mm, r_edge)
            extrude(sketch.sketch, -depth)
            chamfer(part.faces().filter_by(Plane.XY).edges(), chamfer_d)

        self.part = part.part
        self.area = Vector(width_mm - chamfer_d * 2, height_mm - chamfer_d * 2)
