from __future__ import annotations

import logging
import math

import pint
from build123d import (
    Align, Axis, Box, BuildLine, BuildPart, BuildSketch, Locations, Mode, Plane,
    Polyline, Select, Vector, add, chamfer, extrude, make_face, mirror,
)

from ..util import unit_registry
from . import LabelBase

logger = logging.getLogger(__name__)


class ModernBase(LabelBase):
    KNOWN_WIDTHS = {3: 31.8, 4: 50.8, 5: 75.8, 6: 115.8, 7: 140.800, 8: 140.800}

    def __init__(self, args):
        EXTRA_WIDTH_TOL = 0.5
        INDENT_WIDTH_MARGINS = 15.8
        EXTRA_INDENT_TOL = 0.4
        INDENT_DEPTH = 0.8

        def _convert_u_to_mm(u: pint.Quantity):
            if u.magnitude not in self.KNOWN_WIDTHS:
                raise ValueError(f"Modern base only supports 3u-8u. Got {u.magnitude}u.")
            return pint.Quantity(self.KNOWN_WIDTHS[u.magnitude] - EXTRA_WIDTH_TOL, "mm")

        with unit_registry.context("u", fn=_convert_u_to_mm):
            W_mm = args.width.to("mm").magnitude

        H_mm = 22.117157
        if args.height is not None:
            H_mm = args.height.to("mm").magnitude

        depth = 2.2
        W_inner = W_mm - depth
        H_inner = H_mm - depth

        with BuildPart() as part:
            with BuildSketch(Plane.XY.offset(amount=-depth / 2)) as _sketch:
                with BuildLine() as _line:
                    corner_length = 1.8
                    corner_off = corner_length * math.sin(math.pi / 4)
                    Polyline([
                        (0, -H_inner / 2), (-W_inner / 2, -H_inner / 2),
                        (-W_inner / 2, H_inner / 2 - corner_off),
                        (-W_inner / 2 + corner_off, H_inner / 2), (0, H_inner / 2),
                    ])
                    mirror(_line.line, Plane.YZ)
                make_face()
            extrude(amount=depth / 2, taper=-45, both=True)

            with BuildPart(mode=Mode.PRIVATE) as _bottom_part:
                with Locations([(0, -H_mm / 2, -depth / 2)]):
                    Box(W_mm, depth, depth, align=(Align.CENTER, Align.MIN, Align.CENTER))
                    edges = (
                        _bottom_part.edges(Select.LAST).filter_by(Axis.Z).group_by(Axis.Y)[-1]
                    )
                    chamfer(edges, length=1.2)
            add(_bottom_part.part)

            with Locations([(0, -H_mm / 2 + 4.7, -depth)]):
                Box(
                    W_mm - INDENT_WIDTH_MARGINS + EXTRA_INDENT_TOL, 13, INDENT_DEPTH,
                    mode=Mode.SUBTRACT,
                    align=(Align.CENTER, Align.MIN, Align.MIN),
                )

        self.part = part.part
        self.area = Vector(W_mm, H_mm)
