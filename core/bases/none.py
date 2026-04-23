from __future__ import annotations

from ..options import LabelStyle
from ..util import unit_registry
from . import LabelBase


class NoneBase(LabelBase):
    DEFAULT_WIDTH = None
    DEFAULT_WIDTH_UNIT = unit_registry.mm

    def __init__(self, args):
        if args.style != LabelStyle.EMBOSSED:
            raise ValueError("Only embossed style is supported without a base.")
        self.part = None
        self.area = None
