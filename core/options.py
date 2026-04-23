from __future__ import annotations

import contextlib
import importlib.resources
import logging
from enum import Enum, auto
from typing import Iterator, NamedTuple

import pint
from build123d import FontStyle, Path

logger = logging.getLogger(__name__)


class LabelStyle(Enum):
    EMBOSSED = auto()
    DEBOSSED = auto()
    EMBEDDED = auto()

    @classmethod
    def _missing_(cls, value):
        for kind in cls:
            if kind.name.lower() == value.lower():
                return kind

    def __str__(self):
        return self.name.lower()


class FontOptions(NamedTuple):
    font: str | None = None
    font_style: FontStyle = FontStyle.REGULAR
    font_path: Path | None = None
    font_height_mm: float | None = None
    font_height_exact: bool = True

    def get_allowed_height(self, requested_height: float) -> float:
        if not requested_height:
            raise ValueError("Requested zero height")
        if self.font_height_exact:
            return self.font_height_mm or requested_height
        else:
            return min(self.font_height_mm or requested_height, requested_height)

    @contextlib.contextmanager
    def font_options(self) -> Iterator:
        kwargs = {"font_style": self.font_style}
        if self.font_path:
            kwargs["font_path"] = str(self.font_path)
        if self.font:
            kwargs["font"] = self.font

        with contextlib.ExitStack() as stack:
            if not self.font and not self.font_path:
                logger.debug("Falling back to internal font OpenSans")
                fontfile = stack.enter_context(
                    importlib.resources.as_file(
                        importlib.resources.files("gflabel").joinpath(
                            f"resources/OpenSans-{self.font_style.name.title()}"
                        )
                    )
                )
                kwargs["font_path"] = str(fontfile)
            yield kwargs


class RenderOptions(NamedTuple):
    line_spacing_mm: float = 0.1
    margin_mm: float = 0.4
    font: FontOptions = FontOptions()
    allow_overheight: bool = True
    column_gap: float = 0.4

    @classmethod
    def from_request(cls, req) -> RenderOptions:
        font_style_map = {s.name.lower(): s for s in FontStyle}
        font_style = font_style_map.get(req.font_style.lower(), FontStyle.REGULAR)

        margin_mm = req.margin if req.margin is not None else 0.4

        return cls(
            margin_mm=margin_mm,
            font=FontOptions(
                font=req.font,
                font_style=font_style,
                font_height_mm=req.font_size or req.font_size_maximum,
                font_height_exact=req.font_size_maximum is None,
                font_path=req.font_path if hasattr(req, "font_path") else None,
            ),
            allow_overheight=not req.no_overheight,
            column_gap=req.column_gap,
        )
