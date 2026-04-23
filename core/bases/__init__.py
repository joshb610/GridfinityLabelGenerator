from __future__ import annotations

from abc import ABC, abstractmethod

from build123d import Part, Vector

from ..util import unit_registry


class LabelBase(ABC):
    part: Part
    area: Vector

    DEFAULT_WIDTH = None
    DEFAULT_WIDTH_UNIT = None
    DEFAULT_MARGIN = unit_registry.Quantity(0.2, "mm")

    @abstractmethod
    def __init__(self, args):
        pass
