from __future__ import annotations

import logging

import pint
from build123d import (
    Axis, BuildLine, BuildPart, BuildSketch, Edge, Mode, Part, Plane, Polyline,
    RectangleRounded, Select, ShapeList, Vector, chamfer, extrude, fillet, make_face,
)

from ..util import unit_registry
from . import LabelBase

logger = logging.getLogger(__name__)


def _body_v11(height_mm: float | None = None) -> tuple[Part, Vector]:
    width = 36.4
    height = height_mm or 11.0
    depth = 1
    with BuildPart() as part:
        with BuildSketch():
            RectangleRounded(width=width, height=height, radius=0.5)
        extrude(amount=-depth)

        with BuildSketch(Plane.XZ) as _sketch:
            for x in [-12.133, 0, 12.133]:
                with BuildLine() as _line:
                    Polyline([
                        (x - 0.5, -1), (x - 0.5, -0.8), (x - 1, -0.8),
                        (x - 1, -0.4), (x + 1, -0.4), (x + 1, -0.8),
                        (x + 0.5, -0.8), (x + 0.5, -1),
                    ], close=True)
                make_face()
        extrude(amount=height / 2, both=True, mode=Mode.SUBTRACT)

        verts = (
            part.edges().filter_by(Axis.Z)
            .filter_by(lambda x: x.length < 1)
            .group_by(lambda x: x.length)
        )
        fillet(verts[0], radius=0.5)
        fillet(verts[1], radius=0.5)

        def _get_all_start_edges():
            all_candidates = part.edges().filter_by(Axis.Y).filter_by_position(Axis.Z, -0.85, -0.75)
            start_edges = ShapeList()
            for x in [-12.133, 0, 12.133]:
                start_edges.extend(all_candidates.filter_by_position(Axis.X, x - 0.55, x + 0.55))
            return start_edges

        def _edge_matcher(vertex_set: ShapeList):
            vs = vertex_set.vertices()
            def _match_edge(edge: Edge) -> bool:
                for v in edge.vertices():
                    for v2 in vs:
                        if v.distance_to(v2) < 0.001:
                            return True
                return False
            return _match_edge

        cands_to_chamfer = part.edges().filter_by(Plane.XY).filter_by_position(Axis.Z, -0.85, -0.75)
        ext_1 = cands_to_chamfer.filter_by(_edge_matcher(_get_all_start_edges()))
        ext_2 = cands_to_chamfer.filter_by(_edge_matcher(ext_1))
        chamfer(ext_2, length=0.1999, length2=0.1)

    return part.part, Vector(36.4, 11)


def _body_v200(width: pint.Quantity, height_mm: float | None = None, ribs: bool = True) -> tuple[Part, Vector]:
    is_1u = False
    if width.check(unit_registry.u):
        if width.magnitude == 1:
            is_1u = True
        width_mm = (width * unit_registry.Quantity("42mm/u").to("mm")).magnitude - 6
    else:
        width_mm = width.to("mm").magnitude
    height = height_mm or 11
    depth = 1.2

    with BuildPart() as part:
        with BuildSketch():
            RectangleRounded(width=width_mm, height=height, radius=0.5)
        extrude(amount=-depth)

        with BuildSketch(Plane.XY.offset(-0.4)):
            RectangleRounded(width=width_mm, height=height, radius=0.5)
            RectangleRounded(width=width_mm - 0.4, height=height - 0.4, radius=0.3, mode=Mode.SUBTRACT)
        extrude(amount=-(depth - 0.6), mode=Mode.SUBTRACT)

        if is_1u and ribs:
            with BuildSketch(Plane.XZ) as _sketch:
                for x in [-12.133, 0, 12.133]:
                    with BuildLine() as _line:
                        Polyline([
                            (x - 0.5, -depth), (x - 0.5, -depth + 0.2), (x - 1, -depth + 0.2),
                            (x - 1, -depth + 0.8), (x + 1, -depth + 0.8), (x + 1, -depth + 0.2),
                            (x + 0.5, -depth + 0.2), (x + 0.5, -depth),
                        ], close=True)
                    make_face()
            extrude(amount=height / 2, both=True, mode=Mode.SUBTRACT)
            edges = part.edges(Select.LAST).filter_by(Axis.Z)
            fillet(edges, radius=0.5)

    return part.part, Vector(width_mm, height)


class CullenectBase(LabelBase):
    DEFAULT_WIDTH = pint.Quantity("1u")
    DEFAULT_WIDTH_UNIT = unit_registry.u
    DEFAULT_MARGIN = unit_registry.Quantity(0, "mm")

    def __init__(self, args):
        version = getattr(args, "version", "latest") or "latest"
        width = args.width
        height_mm = args.height.to("mm").magnitude if args.height is not None else None

        known_versions = {"latest", "v1.1", "v2.0.0", "v2+"}
        if version == "latest":
            version = "v2.0.0"
        if version not in known_versions:
            raise ValueError(f"Unknown cullenect version: {version}")

        if version == "v1.1":
            self.part, self.area = _body_v11(height_mm=height_mm)
        elif version in {"v2.0.0", "v2+"}:
            self.part, self.area = _body_v200(
                width=width or pint.Quantity("1u"),
                height_mm=height_mm,
                ribs=(version != "v2+"),
            )
        else:
            raise RuntimeError("Unreachable cullenect version branch")
