from __future__ import annotations

import functools
import importlib.resources
import io
import itertools
import json
import logging
import re
import textwrap
import zipfile
from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from math import cos, radians, sin
from typing import Any, ClassVar, Iterable, NamedTuple, Type, TypedDict

from build123d import (
    Align,
    Axis,
    BuildLine,
    BuildSketch,
    CenterArc,
    Circle,
    EllipticalCenterArc,
    GridLocations,
    Line,
    Location,
    Locations,
    Mode,
    Plane,
    PolarLocations,
    Polyline,
    Rectangle,
    RectangleRounded,
    RegularPolygon,
    Rot,
    Sketch,
    SlotCenterToCenter,
    Text,
    Triangle,
    Vector,
    add,
    fillet,
    import_svg,
    make_face,
    mirror,
    offset,
)

from .options import RenderOptions

logger = logging.getLogger(__name__)
RE_FRAGMENT = re.compile(r"(.+?)(?:\((.*)\))?$")

FRAGMENTS: dict[str, Type[Fragment] | Callable[..., Fragment]] = {}

DRIVE_ALIASES = {
    "+": "phillips",
    "posidrive": "pozidrive",
    "posi": "pozidrive",
    "pozi": "pozidrive",
    "-": "slot",
    "tri": "triangle",
    "robertson": "square",
}
DRIVES = {
    "phillips",
    "pozidrive",
    "slot",
    "hex",
    "cross",
    "square",
    "triangle",
    "torx",
    "security",
    "phillipsslot",
}


class InvalidFragmentSpecification(RuntimeError):
    pass


def fragment_from_spec(spec: str) -> Fragment:
    try:
        value = float(spec)
    except ValueError:
        pass
    else:
        return SpacerFragment(value)

    match = RE_FRAGMENT.match(spec)
    assert match
    name, args = match.groups()
    args = [x.strip() for x in args.split(",")] if args else []

    if name not in FRAGMENTS:
        raise RuntimeError(f"Unknown fragment class: {name}")
    return FRAGMENTS[name](*args)


def fragment(*names: str, examples: list[str] = [], overheight: float | None = None):
    def _wrapped(fn):
        if not isinstance(fn, type) and callable(fn):
            def _fragment(*args):
                frag = FunctionalFragment(fn, *args)
                frag.overheight = overheight
                frag.examples = examples
                return frag

            _fragment.__doc__ = fn.__doc__
            setattr(_fragment, "examples", examples)
            setattr(_fragment, "overheight", overheight)
        else:
            _fragment = fn

        for name in names:
            FRAGMENTS[name] = _fragment
        return fn

    return _wrapped


class Fragment(metaclass=ABCMeta):
    variable_width = False
    priority: float = 1
    visible = True
    examples: list[str] | None = None
    overheight: float | None = None

    def __init__(self, *args: list[Any]):
        if args:
            raise ValueError("Not all fragment arguments handled")

    def min_width(self, height: float) -> float:
        if self.variable_width:
            raise NotImplementedError(f"min_width not implemented for '{type(self).__name__}'")
        return 0

    @abstractmethod
    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        pass


class FunctionalFragment(Fragment):
    def __init__(self, fn: Callable[[float, float], Sketch], *args):
        self.args = args
        self.fn = fn

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        return self.fn(height, maxsize, *self.args)


class SpacerFragment(Fragment):
    visible = False
    examples = ["L{...}R\n{...}C{...}R"]

    def __init__(self, distance: float, *args):
        super().__init__(*args)
        self.distance = distance

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        with BuildSketch() as sketch:
            Rectangle(self.distance, height)
        return sketch.sketch


@fragment("...")
class ExpandingFragment(Fragment):
    """Blank area that always expands to fill available space. Use multiple to balance spacing."""
    variable_width = True
    priority = 0
    visible = False
    examples = ["L{...}R"]

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        with BuildSketch() as sketch:
            Rectangle(maxsize, height)
        return sketch.sketch

    def min_width(self, height: float) -> float:
        return 0


class TextFragment(Fragment):
    def __init__(self, text: str):
        self.text = text

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        if not height:
            raise ValueError("Trying to render zero-height text fragment")
        with BuildSketch() as sketch:
            with options.font.font_options() as f:
                Text(self.text, font_size=options.font.get_allowed_height(height), **f)
        return sketch.sketch


@functools.lru_cache
def _whitespace_width(spacechar: str, height: float, options: RenderOptions) -> float:
    with options.font.font_options() as f:
        w2 = (
            Text(f"a{spacechar}a", font_size=options.font.get_allowed_height(height),
                 mode=Mode.PRIVATE, **f)
            .bounding_box().size.X
        )
        wn = (
            Text("aa", font_size=options.font.get_allowed_height(height),
                 mode=Mode.PRIVATE, **f)
            .bounding_box().size.X
        )
    return w2 - wn


class WhitespaceFragment(Fragment):
    visible = False

    def __init__(self, whitespace: str):
        if not whitespace.isspace():
            raise ValueError(f"Whitespace fragment can only contain whitespace, got {whitespace!r}")
        self.whitespace = whitespace

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        with BuildSketch() as sketch:
            Rectangle(_whitespace_width(self.whitespace, height, options), height)
        return sketch.sketch


@fragment("hexhead", examples=["{hexhead}"])
def _fragment_hexhead(height: float, _maxsize: float, *drives: str) -> Sketch:
    """Hexagonal screw head. Accepts optional drive type arguments."""
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        RegularPolygon(height / 2, 6)
        if drives:
            add(compound_drive_shape(drives, 0.6 * height / 2, height / 2), mode=Mode.SUBTRACT)
    return sketch.sketch


@fragment("head")
def _fragment_head(height: float, _maxsize: float, *headshapes: str) -> Sketch:
    """Screw head with specifiable head-shape."""
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        Circle(height / 2)
        add(
            compound_drive_shape(headshapes, radius=(height / 2) * 0.7, outer_radius=height / 2),
            mode=Mode.SUBTRACT,
        )
    return sketch.sketch


@fragment("threaded_insert", examples=["{threaded_insert}"])
def _fragment_insert(height: float, _maxsize: float) -> Sketch:
    """Representation of a threaded insert."""
    with BuildSketch() as sketch:
        with BuildLine() as line:
            Polyline([(-3, 0), (-3, 1.25), (-4, 1.25), (-4, 3.75), (0, 3.75)])
            mirror(line.line, Plane.XZ)
            mirror(line.line, Plane.YZ)
            fillet(line.vertices(), radius=0.2)
        make_face()
        with Locations([(0, -3.76 - 2.5 / 2)]):
            Rectangle(6, 2.5)

        def Trap() -> Sketch:
            with BuildSketch(mode=Mode.PRIVATE) as s:
                with BuildLine() as _line:
                    Polyline([(-1.074, 0.65), (-0.226, 0.65), (1.074, -0.65), (0.226, -0.65)], close=True)
                make_face()
            return s.sketch

        with GridLocations(1.625, 5, 4, 2):
            add(Trap(), mode=Mode.SUBTRACT)

    scale = height / 10
    return sketch.sketch.locate(Location((0, 2.5 / 2))).scale(scale)


@fragment("hexnut", "nut", examples=["{nut}"])
def _fragment_hexnut(height: float, _maxsize: float) -> Sketch:
    """Hexagonal outer profile nut with circular cutout."""
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        RegularPolygon(height / 2, side_count=6)
        Circle(height / 2 * 0.4, mode=Mode.SUBTRACT)
    return sketch.sketch


@fragment("squarenut", "square_nut", examples=["{squarenut}"])
def _fragment_squarenut(height: float, _maxsize: float) -> Sketch:
    """Square nut with rounded corners and circular cutout."""
    corner_radius = height * 0.07
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        RectangleRounded(height, height, corner_radius)
        Circle(height / 2 * 0.4, mode=Mode.SUBTRACT)
    return sketch.sketch


@fragment("nut_profile", examples=["{nut_profile}"])
def _fragment_nut_profile(height: float, _maxsize: float | None = None) -> Sketch:
    """Hex nut side profile."""
    width = height / 2.25
    _cutout_height = 1 / 10 * height
    _cutout_y = 1 / 4 * height
    with BuildSketch() as sketch:
        Rectangle(width, height)
        r1 = Rectangle(width, _cutout_height)
        add(r1.locate(Location((0, _cutout_y))), mode=Mode.SUBTRACT)
        add(r1.locate(Location((0, -1 * _cutout_y))), mode=Mode.SUBTRACT)
    return sketch.sketch


@fragment("locknut", "locknut_profile", examples=["{locknut}"])
def _fragment_locknut(height: float, _maxsize: float | None = None) -> Sketch:
    """Lock nut side profile: wide body with overlapping nylon insert on top."""
    width = height * 1.5
    body_radius = height * 0.07
    insert_radius = height * 0.12

    body_h = height * 0.70
    insert_h = height * 0.45   # tall enough to overlap body by 0.15h
    insert_w = width * 0.78

    # body spans −0.50h to +0.20h; insert spans +0.05h to +0.50h
    # overlap = 0.15h > insert_radius (0.12h) → insert bottom corners hidden inside body
    body_cy = -height / 2 + body_h / 2
    insert_cy = height / 2 - insert_h / 2

    with BuildSketch() as sketch:
        with Locations([(0, body_cy)]):
            RectangleRounded(width, body_h, body_radius)
        with Locations([(0, insert_cy)]):
            RectangleRounded(insert_w, insert_h, insert_radius)
    return sketch.sketch


@fragment("washer", examples=["{washer}"])
def _fragment_washer(height: float, _maxsize: float) -> Sketch:
    """Circular washer with a circular hole."""
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        Circle(height / 2)
        Circle(height / 2 * 0.55, mode=Mode.SUBTRACT)
    return sketch.sketch


@fragment("oring", "o_ring", examples=["{oring}"])
def _fragment_oring(height: float, _maxsize: float) -> Sketch:
    """O-ring cross-section: thin circular washer profile."""
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        Circle(height / 2)
        Circle(height / 2 * 0.78, mode=Mode.SUBTRACT)
    return sketch.sketch


@fragment("lockwasher", examples=["{lockwasher}"])
def _fragment_lockwasher(height: float, _maxsize: float) -> Sketch:
    """Circular washer with a locking cutout."""
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        inner_radius = 0.55
        Circle(height / 2)
        Circle(height / 2 * inner_radius, mode=Mode.SUBTRACT)
        y_cutout = height / 2 * (inner_radius + 1) / 2
        r = Rectangle(height / 2 * inner_radius / 2, y_cutout * 2, mode=Mode.PRIVATE)
        add(r.locate(Location((height * 0.1, y_cutout))).rotate(Axis.Z, 45), mode=Mode.SUBTRACT)
    return sketch.sketch


@fragment("circle", examples=["{circle}"])
def _fragment_circle(height: float, _maxsize: float) -> Sketch:
    """A filled circle."""
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        Circle(height / 2)
    return sketch.sketch


@fragment("ball_bearing", "bearing", examples=["{ball_bearing}"])
def _fragment_ball_bearing(height: float, _maxsize: float) -> Sketch:
    """Ball bearing symbol — filled circle."""
    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        Circle(height / 2)
    return sketch.sketch


class BoltBase(Fragment):
    HEAD_SHAPES = {"countersunk", "pan", "round", "socket"}
    MODIFIERS = {"tapping", "flip", "partial"}
    FEATURE_ALIAS = {
        "countersink": "countersunk",
        "tap": "tapping",
        "tapped": "tapping",
        "flipped": "flip",
        "square": "socket",
    }
    DEFAULT_HEADSHAPE = "pan"

    def __init__(self, *req_features: str):
        features = {self.FEATURE_ALIAS.get(x.lower(), x.lower()) for x in req_features}
        requested_head_shapes = features & self.HEAD_SHAPES
        if len(requested_head_shapes) > 1:
            raise ValueError("More than one head shape specified")
        self.headshape = next(iter(requested_head_shapes), self.DEFAULT_HEADSHAPE)
        features -= {self.headshape}
        self.modifiers = features & self.MODIFIERS
        self.partial = "partial" in self.modifiers
        features -= self.MODIFIERS
        self.drives = features


@fragment("bolt")
class BoltFragment(BoltBase):
    """
    Variable length bolt. If bolt is longer than available space, it renders
    with a broken thread indicator.

    Usage: {bolt(length, head_type, drive_type)}
    Example: {bolt(16, socket)} {bolt(20, pan, phillips)}
    """
    variable_width = True

    def __init__(self, length: str, *features: str):
        self.slotted = bool({"slotted", "slot"} & {x.lower() for x in features})
        self.flanged = bool({"flanged", "flange"} & {x.lower() for x in features})
        features = tuple(x for x in features if x.lower() not in {"slotted", "flanged"})
        self.length = float(length)
        super().__init__(*features)

    def min_width(self, height: float) -> float:
        return height

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        length = self.length
        lw = height / 2.25
        half_split = 0.75

        if self.headshape == "countersunk":
            length -= lw

        maxsize = max(maxsize, lw * 2 + half_split * 2 + 0.1)
        split_bolt = length + lw > maxsize
        hw = maxsize / 2 if split_bolt else (length + lw) / 2

        head_h = height / 2
        if self.flanged:
            head_h -= lw / 3

        if "tapping" in self.modifiers:
            bolt_bottom = [(hw - lw / 2, lw / 2), (hw, 0), (hw - lw / 2, -lw / 2)]
        else:
            bolt_bottom = [(hw, lw / 2), (hw, -lw / 2)]

        with BuildSketch(mode=Mode.PRIVATE) as sketch:
            with BuildLine() as _line:
                head_connector_top: Vector
                head_connector_bottom: Vector

                if self.headshape == "pan":
                    head_radius = min(2, lw / 2)
                    _top_arc = CenterArc((-hw + head_radius, head_h - head_radius), head_radius, 90, 90)
                    _bottom_arc = CenterArc((-hw + head_radius, -head_h + head_radius), head_radius, 180, 90)
                    Line([_top_arc @ 1, _bottom_arc @ 0])
                    if head_radius == lw:
                        head_connector_top = _top_arc @ 0
                        head_connector_bottom = _bottom_arc @ 1
                    else:
                        head_connector_top = Vector(-hw + lw, head_h)
                        head_connector_bottom = Vector(-hw + lw, -head_h)
                        Line([head_connector_top, _top_arc @ 0])
                        Line([head_connector_bottom, _bottom_arc @ 1])
                elif self.headshape == "socket":
                    _head = Polyline([(-hw + lw, -head_h), (-hw, -head_h), (-hw, head_h), (-hw + lw, head_h)])
                    head_connector_bottom = _head @ 0
                    head_connector_top = _head @ 1
                elif self.headshape == "countersunk":
                    head_connector_bottom = Vector(-hw, -head_h)
                    head_connector_top = Vector(-hw, head_h)
                    Line([head_connector_bottom, head_connector_top])
                elif self.headshape == "round":
                    _head = EllipticalCenterArc((-hw + lw, 0), lw, head_h, 90, -90)
                    head_connector_top = _head @ 0
                    head_connector_bottom = _head @ 1
                else:
                    raise ValueError(f"Unknown bolt head type: {self.headshape!r}")

                if not split_bolt:
                    Polyline([head_connector_top, (-hw + lw, lw / 2), *bolt_bottom,
                               (-hw + lw, -lw / 2), head_connector_bottom])
                else:
                    x_shaft_midpoint = lw + (maxsize - lw) / 2 - hw
                    Polyline([
                        head_connector_top, (-hw + lw, lw / 2),
                        (x_shaft_midpoint + lw / 2 - half_split, lw / 2),
                        (x_shaft_midpoint - lw / 2 - half_split, -lw / 2),
                        (-hw + lw, -lw / 2), head_connector_bottom,
                    ])

            make_face()

            if split_bolt:
                with BuildLine() as _line:
                    Polyline([
                        (x_shaft_midpoint + lw / 2 + half_split, lw / 2),
                        *bolt_bottom,
                        (x_shaft_midpoint - lw / 2 + half_split, -lw / 2),
                    ], close=True)
                make_face()

            if self.slotted:
                with Locations([(-hw, 0)]):
                    Rectangle(lw / 2, lw / 2, align=(Align.MIN, Align.CENTER), mode=Mode.SUBTRACT)
            if self.flanged:
                with Locations([(-hw + lw, 0)]):
                    Rectangle(lw / 4, height, align=(Align.MAX, Align.CENTER))

        if "flip" in self.modifiers:
            return sketch.sketch.scale(-1)
        return sketch.sketch


@fragment("webbolt", "cullbolt", "cullenectbolt")
class CullenectBoltFragment(BoltBase):
    """
    Detailed bolt with thread profile and drive cutout.

    Usage: {cullbolt(head_type, drive_type)}
    Example: {cullbolt(socket, hex)} {cullbolt(pan, phillips)}
    """
    overheight = 1.6

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        height *= self.overheight
        width = 1.456 * height
        body_w = 0.856 * height
        n_threads = 6
        thread_depth = 0.0707 * height
        head_w = width - body_w
        x_head = body_w - width / 2
        x0 = -width / 2
        thread_pitch = body_w / n_threads
        thread_lines: list[tuple[float, float]] = [(x0, 0)]
        thread_tip_height = (height / 4) + thread_depth

        if "tapping" in self.modifiers:
            thread_lines.append((x0 + thread_pitch * 2 - 0.2, thread_tip_height - thread_depth))
            n_threads -= 2
            x0 += thread_pitch * 2

        if self.partial:
            n_threads = 3

        for i in range(n_threads):
            thread_lines.extend([
                (x0 + i * thread_pitch, thread_tip_height - thread_depth),
                (x0 + (i + 0.5) * thread_pitch, thread_tip_height),
            ])

        if self.partial:
            thread_lines.append((x0 + n_threads * thread_pitch, thread_tip_height - thread_depth))

        with BuildSketch() as sketch:
            with BuildLine() as line:
                head_connector: Vector
                if self.headshape == "pan":
                    head_radius = 2
                    head_arc = CenterArc((width / 2 - head_radius, height / 2 - head_radius), head_radius, 0, 90)
                    Line([head_arc @ 0, (width / 2, 0)])
                    _top = Line([(x_head, height / 2), head_arc @ 1])
                    head_connector = _top @ 0
                elif self.headshape == "countersunk":
                    _top = Line([(width / 2, height / 2), (width / 2, 0)])
                    head_connector = _top @ 0
                elif self.headshape == "socket":
                    head_connector = (
                        Polyline([(x_head, height / 2), (width / 2, height / 2), (width / 2, 0)]) @ 0
                    )
                elif self.headshape == "round":
                    if head_w > height / 2:
                        x_roundhead = width / 2 - height / 2
                        _arc = CenterArc((x_roundhead, 0), height / 2, 0, 90)
                        flat = Line([(x_head, height / 2), _arc @ 1])
                        head_connector = flat @ 0
                    else:
                        raise NotImplementedError("Round head on this aspect is not implemented.")

                Polyline([*thread_lines, (x_head, thread_tip_height - thread_depth), head_connector])
                mirror(line.line, Plane.XZ)
            make_face()

            if self.drives:
                fudge = thread_depth / 2
                location = Location((width / 2 - head_w / 2 - fudge, 0))
                add(
                    compound_drive_shape(self.drives, radius=head_w * 0.9 / 2, outer_radius=head_w / 2)
                    .locate(location),
                    mode=Mode.SUBTRACT,
                )

        if "flip" in self.modifiers:
            return sketch.sketch.scale(-1)
        return sketch.sketch


@fragment("variable_resistor", examples=["{variable_resistor}"], overheight=1.5)
def _fragment_variable_resistor(height: float, maxsize: float) -> Sketch:
    """Electrical symbol of a variable resistor."""
    t = 0.4 / 2
    w = 6.5
    h = 2
    l_arr = 7
    l_head = 1.5
    angle = 30

    with BuildSketch(mode=Mode.PRIVATE) as sketch:
        with BuildLine():
            Polyline([
                (-6, 0), (-6, t), (-w / 2 - t, t), (-w / 2 - t, h / 2 + t),
                (0, h / 2 + t), (0, h / 2 - t), (-w / 2 + t, h / 2 - t), (-w / 2 + t, 0),
            ], close=True)
        make_face()
        mirror(sketch.sketch, Plane.XZ)
        mirror(sketch.sketch, Plane.YZ)

        theta = radians(angle)
        with BuildSketch(mode=Mode.PRIVATE) as arrow:
            with BuildLine() as _line:
                Polyline([
                    (0, -l_arr / 2), (0, l_arr / 2),
                    (-sin(theta) * l_head, l_arr / 2 - cos(theta) * l_head),
                ])
                offset(amount=t)
            make_face()
            mirror(arrow.sketch, Plane.YZ)
        add(arrow.sketch.rotate(Axis.Z, -30))

    size = sketch.sketch.bounding_box().size
    scale = (height * 1.5) / size.Y
    return sketch.sketch.scale(scale)


def drive_shape(shape: str, radius: float = 1, outer_radius: float = 1) -> Sketch:
    positive = False
    shape = shape.lower()
    cut_radius = max(radius, outer_radius) / radius
    with BuildSketch(mode=Mode.PRIVATE) as sk:
        if shape in {"phillips", "+"}:
            Rectangle(1, 0.2)
            Rectangle(0.2, 1)
            Rectangle(0.4, 0.4, rotation=45)
        elif shape in {"pozidrive", "posidrive", "posi", "pozi"}:
            Rectangle(1, 0.2)
            Rectangle(0.2, 1)
            Rectangle(0.4, 0.4, rotation=45)
            Rectangle(1, 0.1, rotation=45)
            Rectangle(1, 0.1, rotation=-45)
        elif shape in {"slot", "-"}:
            Rectangle(cut_radius, 0.2)
        elif shape == "hex":
            RegularPolygon(0.5, side_count=6)
        elif shape == "cross":
            Rectangle(1, 0.2)
            Rectangle(0.2, 1)
        elif shape == "phillipsslot":
            Rectangle(1, 0.2)
            Rectangle(0.2, 1)
            Rectangle(0.4, 0.4, rotation=45)
            Rectangle(cut_radius, 0.2)
        elif shape == "square":
            Rectangle(0.6, 0.6, rotation=45)
        elif shape in {"triangle", "tri"}:
            Triangle(a=0.95, b=0.95, c=0.95)
        elif shape == "torx":
            Circle(0.74 / 2)
            with PolarLocations(0, 3):
                SlotCenterToCenter(0.82, 0.19)
            with PolarLocations(0.41, 6, start_angle=360 / 12):
                Circle(0.11, mode=Mode.SUBTRACT)
        elif shape == "security":
            Circle(0.1)
            positive = True
        else:
            raise ValueError(f"Unknown head type: {shape}")

    sketch = sk.sketch.scale(2 * radius)
    sketch.positive = positive
    return sketch


def compound_drive_shape(shapes: Iterable[str], radius: float = 1, outer_radius: float = 1) -> Sketch:
    if not shapes:
        raise ValueError("No drive shapes requested")
    plus: list[Sketch] = []
    minus: list[Sketch] = []
    for shape in shapes:
        s = drive_shape(shape, radius=radius, outer_radius=outer_radius)
        (minus if s.positive else plus).append(s)

    with BuildSketch() as sketch:
        for shape in plus:
            add(shape)
        for shape in minus:
            add(shape, mode=Mode.SUBTRACT)
    return sketch.sketch


@fragment("box", examples=["{box(35)}"])
def _box_fragment(height: float, maxsize: float, in_width: str, in_height: str | None = None) -> Sketch:
    """Arbitrary width/height centered box. Height defaults to row height if omitted."""
    width = float(in_width)
    height = float(in_height) if in_height else height
    with BuildSketch() as sketch:
        Rectangle(width, height)
    return sketch.sketch


@fragment("|")
class SplitterFragment(Fragment):
    """Column divider. Specify relative proportions: {1|2} gives left=1, right=2 width ratio."""
    _SIIF = r"(\d*(?:\d[.]|[.]\d)?\d*)"
    SPLIT_RE: ClassVar[re.Pattern] = re.compile(f"\\{{{_SIIF}\\|{_SIIF}}}")
    alignment: str | None

    def __init__(self, left: str | None = None, right: str | None = None, *args):
        assert not args
        self.left = float(left or 1)
        self.right = float(right or 1)

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        raise NotImplementedError("Splitters should never be rendered")


@fragment("measure")
class DimensionFragment(Fragment):
    """Fills available area with a dimension line showing the length. Useful for debugging layouts."""
    variable_width = True
    examples = ["{measure}A{measure}", "{bolt(10)}{measure}"]

    def min_width(self, height: float) -> float:
        return 1

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        lw = 0.4
        with BuildSketch() as sketch:
            with Locations([(-maxsize / 2, 0)]):
                Rectangle(lw, height / 4, align=(Align.MIN, Align.CENTER))
            with Locations([(maxsize / 2, 0)]):
                Rectangle(lw, height / 4, align=(Align.MAX, Align.CENTER))
            with Locations([(0, 0)]):
                Rectangle(maxsize - lw * 2, lw)
            avail = height / 2 - lw / 2
            with Locations([(0, -avail / 2)]):
                Text(f"{maxsize:.1f}", font_size=height / 2)
        return sketch.sketch


@fragment("<", ">")
class AlignmentFragment(Fragment):
    """Place at the start of a label or column to left-align ({<}) or right-align ({>}) all lines."""
    examples = ["{<}Left\nLines", "{>}Right"]

    def __init__(self, *args):
        raise InvalidFragmentSpecification(
            "Alignment fragment ({<} or {>}) must be at the start of a label."
        )


@fragment("magnet", examples=["{magnet}"])
def _fragment_magnet(height: float, _maxsize: float) -> Sketch:
    """Horseshoe shaped magnet symbol."""
    scale = height * 2 / 3
    thickness = 0.2
    arm_len = 1.8
    with BuildSketch() as sketch:
        Circle(scale / 2)
        Circle(scale / 2 * (1 - thickness * 2), mode=Mode.SUBTRACT)
        Rectangle(scale * arm_len, scale, align=(Align.MIN, Align.CENTER), mode=Mode.SUBTRACT)
        with Locations((0, scale / 2 - scale * thickness / 2), (0, -(scale / 2 - scale * thickness / 2))):
            Rectangle(scale / 2, scale * thickness, align=(Align.MIN, Align.CENTER))
    return Rot(0, 0, 45) * sketch.sketch


class ManifestItem(TypedDict):
    id: str
    name: str
    category: str
    standard: str
    filename: str


@functools.cache
def electronic_symbols_manifest() -> list[ManifestItem]:
    with (
        importlib.resources.files("gflabel")
        .joinpath("resources")
        .joinpath("chris-pikul-symbols.zip")
        .open("rb") as f
    ):
        z = zipfile.ZipFile(f)
        return json.loads(z.read("manifest.json"))


def _get_standard_requested(selectors: Iterable[str]) -> str | None:
    aliases = {"com": "common", "ansi": "ieee", "euro": "iec", "europe": "iec"}
    requested = set(aliases.get(x.lower(), x.lower()) for x in selectors)
    standards = {x.upper() for x in requested & {"iec", "ieee", "common"}}
    if len(standards) > 1:
        raise ValueError(f"Got more than one symbol standard: '{', '.join(standards)}'")
    return next(iter(standards), None)


def _match_electronic_symbol_from_standard(preferred_standards, matches):
    def _get_standard(x):
        return x["standard"].lower()

    grouped = itertools.groupby(
        sorted(matches, key=lambda x: preferred_standards.index(_get_standard(x))),
        key=_get_standard,
    )
    return list(next(iter(grouped), [[]])[1])


def _match_electronic_symbol_with_selectors(selectors: Iterable[str]) -> ManifestItem:
    aliases: dict[str, str] = {}
    requested = set(
        aliases.get(x.lower(), x.lower()).removesuffix(".svg").removesuffix(".png").removesuffix(".jpg")
        for x in selectors
    )

    standard_req = _get_standard_requested(requested)
    standards_order = ["common", "iec", "ieee"]
    if standard_req:
        standards_order.remove(standard_req.lower())
        standards_order.insert(0, standard_req.lower())
        requested.remove(standard_req.lower())

    manifest = electronic_symbols_manifest()

    matches = [
        x for x in manifest
        if {
            x["name"].lower(), x["id"].lower(), x["filename"].lower(),
            x["name"].lower().replace(" (IEEE/ANSI)", "").replace(" (Common Style)", ""),
        } & requested
    ]

    if len(matches) == 1:
        return matches[0]

    if not matches:
        match_tokens = set(itertools.chain(*[x.split() for x in requested]))
        for symbol in manifest:
            soup = set(itertools.chain(
                *[x.lower().split() for x in {symbol["category"], symbol["name"], symbol["id"]}]
            ))
            if "logic" in soup:
                soup.add("gate")
            if all(any(cand in s for s in soup) for cand in match_tokens):
                matches.append(symbol)

    if len(matches) == 1:
        return matches[0]

    if not matches:
        raise InvalidFragmentSpecification(f"No matches for '{','.join(requested)}'")

    if len({x["category"] for x in matches}) == 1:
        matches = _match_electronic_symbol_from_standard(standards_order, matches)
        if len(matches) == 1:
            return matches[0]

    raise InvalidFragmentSpecification("Please specify symbol more precisely.")


@fragment("symbol", "sym")
class _electrical_symbol_fragment(Fragment):
    """Render an electronic symbol from the Chris Pikul library.

    Usage: {symbol(name)} or {sym(category, name)}
    Example: {symbol(resistor)} {sym(capacitor, electrolytic)}
    """

    def __init__(self, *selectors: str):
        self.symbol = _match_electronic_symbol_with_selectors(selectors)
        with (
            importlib.resources.files("gflabel")
            .joinpath("resources/chris-pikul-symbols.zip")
            .open("rb") as f
        ):
            z = zipfile.ZipFile(f)
            svg_data = io.StringIO(z.read("SVG/" + self.symbol["filename"] + ".svg").decode())
            self.shapes = import_svg(svg_data, flip_y=False)

    def render(self, height: float, maxsize: float, options: RenderOptions) -> Sketch:
        with BuildSketch() as _sketch:
            add(self.shapes)
        bb = _sketch.sketch.bounding_box()
        return _sketch.sketch.translate(-bb.center()).scale(height / bb.size.Y)


class FragmentDescriptionRow(NamedTuple):
    names: list[str]
    description: str | None
    examples: list[str]


def fragment_description_table() -> list[FragmentDescriptionRow]:
    descriptions: list[FragmentDescriptionRow] = []
    known_as: dict = {}
    for name, frag in FRAGMENTS.items():
        known_as.setdefault(frag, []).append(name)
    for frag, names in known_as.items():
        descriptions.append(FragmentDescriptionRow(
            names=sorted(names),
            description=(textwrap.dedent(frag.__doc__).strip() if frag.__doc__ else None),
            examples=getattr(frag, "examples", None) or [],
        ))
    descriptions.append(FragmentDescriptionRow(
        names=["1", "4.2", "..."],
        description="A gap of specific width in mm.",
        examples=["]{12.5}["],
    ))
    return sorted(descriptions, key=lambda x: x.names[0])
