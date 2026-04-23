from __future__ import annotations

import logging

from build123d import Axis, BuildPart, BuildSketch, Rectangle, Vector, extrude, fillet

from ..util import unit_registry
from . import LabelBase

logger = logging.getLogger(__name__)


class PlainBase(LabelBase):
    DEFAULT_WIDTH = None
    DEFAULT_WIDTH_UNIT = unit_registry.mm

    def __init__(self, args):
        if args.width.units == unit_registry.u:
            raise ValueError("Cannot specify width in gridfinity units for plain base — use mm")
        width_mm = args.width.to("mm").magnitude
        height_mm = args.height.to("mm").magnitude if args.height else 15.0

        with BuildPart() as part:
            with BuildSketch():
                Rectangle(width_mm, height=height_mm)
            extrude(amount=-0.8)
            fillet_edges = list(part.edges().group_by(Axis.Z)[-1])
            fillet(fillet_edges, radius=0.2)

        self.part = part.part
        self.area = Vector(width_mm, height_mm)
