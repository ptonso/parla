"""Geometric checks over the supported SVG subset. See `specs/svg-engine.md#geometric-checks`.

The texfy-ai layout engine made overflow and overlap impossible by construction. The agent now
writes coordinates itself, so these checks measure what it wrote: every text with the Latin
Modern metrics, every shape as its bounding box, every arrow as its polyline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.parsers import expat

from ...checks import Finding
from ...checks.ids import finding
from ...names import PROJECT_DIR
from . import fonts

SUPPORTED = {
    "svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text",
    "tspan", "image", "defs", "marker", "linearGradient", "radialGradient", "stop",
    "title", "desc", "metadata",
}
INERT = {"defs", "marker", "linearGradient", "radialGradient", "stop", "title", "desc", "metadata"}
INHERITED = ("font-size", "font-family", "font-weight", "font-style", "text-anchor")
ANCHOR = {"start": 0.0, "middle": 0.5, "end": 1.0}
TOL = 0.5  # px of slack for containment and overflow
END_TOL = 4.0  # an arrow tip may stop this far outside the shape it points at
MIN_SHAPE = 2.0  # thinner shapes are rules, not boxes
BADGE = 30.0  # a shape this small and centred on an arrow is its label, not an obstacle
_NUM = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_PATH_TOKEN = re.compile(r"([A-Za-z])|([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
_TRANSLATE = re.compile(r"^\s*translate\(\s*([^,\s)]+)(?:[,\s]+([^)\s]+))?\s*\)\s*$")

Box = tuple[float, float, float, float]  # x0, y0, x1, y1


@dataclass
class El:
    tag: str
    attrs: dict[str, str]
    line: int
    content: list[str | El] = field(default_factory=list)
    parent: El | None = None

    def get(self, name: str) -> str | None:
        """An attribute, looked up the tree for the inherited ones."""
        el: El | None = self
        while el is not None:
            if name in el.attrs:
                return el.attrs[name]
            el = el.parent if name in INHERITED else None
        return None

    @property
    def children(self) -> list[El]:
        return [c for c in self.content if isinstance(c, El)]


def parse(text: str) -> El:
    """Raises `ValueError("<message>", line)` on malformed XML."""
    root: El | None = None
    stack: list[El] = []
    parser = expat.ParserCreate(namespace_separator=" ")

    def start(name: str, attrs: dict[str, str]) -> None:
        nonlocal root
        el = El(name.rsplit(" ", 1)[-1], {k.rsplit(" ", 1)[-1]: v for k, v in attrs.items()}, parser.CurrentLineNumber)
        for decl in el.attrs.get("style", "").split(";"):
            key, _, value = decl.partition(":")
            if value.strip():
                el.attrs[key.strip()] = value.strip()
        if stack:
            el.parent = stack[-1]
            stack[-1].content.append(el)
        else:
            root = el
        stack.append(el)

    def data(chars: str) -> None:
        if stack:
            if stack[-1].content and isinstance(stack[-1].content[-1], str):
                stack[-1].content[-1] += chars
            else:
                stack[-1].content.append(chars)

    parser.StartElementHandler = start
    parser.EndElementHandler = lambda name: stack.pop()
    parser.CharacterDataHandler = data
    try:
        parser.Parse(text, True)
    except expat.ExpatError as exc:
        raise ValueError(expat.ErrorString(exc.code), exc.lineno) from exc
    assert root is not None
    return root


@dataclass
class Run:
    text: str
    size: float
    fam: str
    bold: bool
    ital: bool


@dataclass
class TextLine:
    box: Box
    text: str
    runs: list[Run]


@dataclass
class Text:
    el: El
    anchor: tuple[float, float]
    lines: list[TextLine]


@dataclass
class Shape:
    kind: str
    box: Box
    el: El


@dataclass
class Arrow:
    points: list[tuple[float, float]]
    el: El


@dataclass
class Scene:
    canvas: Box | None = None
    shapes: list[Shape] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    arrows: list[Arrow] = field(default_factory=list)
    images: list[El] = field(default_factory=list)
    unsupported: list[tuple[El, str]] = field(default_factory=list)


def _num(el: El, name: str, default: float = 0.0) -> float:
    value = el.attrs.get(name)
    if value is None:
        return default
    match = _NUM.fullmatch(value.strip().removesuffix("px"))
    if match is None:
        raise ValueError(f"{name}='{value}' is not a plain number")
    return float(match.group(0))


def _translate(el: El) -> tuple[float, float]:
    value = el.attrs.get("transform")
    if value is None:
        return 0.0, 0.0
    match = _TRANSLATE.match(value)
    if match is None:
        raise ValueError(f"transform='{value}' is not a translate")
    return float(match.group(1)), float(match.group(2) or 0)


def _path_points(d: str) -> tuple[list[tuple[float, float]], bool]:
    """The vertices of a path made of `M L H V Z` (and their relative forms), and whether it closes."""
    tokens = [(m.group(1), m.group(2)) for m in _PATH_TOKEN.finditer(d)]
    points: list[tuple[float, float]] = []
    x = y = 0.0
    start = (0.0, 0.0)
    closed = False
    command = ""
    numbers: list[float] = []

    def consume() -> None:
        nonlocal x, y, start, closed
        rel = command.islower()
        op = command.upper()
        if op in ("M", "L"):
            for i in range(0, len(numbers) - 1, 2):
                x, y = (x + numbers[i], y + numbers[i + 1]) if rel else (numbers[i], numbers[i + 1])
                points.append((x, y))
                if op == "M" and i == 0:
                    start = (x, y)
        elif op == "H":
            for n in numbers:
                x = x + n if rel else n
                points.append((x, y))
        elif op == "V":
            for n in numbers:
                y = y + n if rel else n
                points.append((x, y))

    for letter, number in tokens:
        if letter:
            consume()
            command, numbers = letter, []
            if letter.upper() not in "MLHVZ":
                raise ValueError(f"path command '{letter}'")
            if letter.upper() == "Z":
                closed = True
                points.append(start)
                x, y = start
        else:
            numbers.append(float(number))
    consume()
    return points, closed


def _bbox(points: list[tuple[float, float]]) -> Box:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _shift(box: Box, dx: float, dy: float) -> Box:
    return box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy


def collect(root: El) -> Scene:
    scene = Scene()
    if "viewBox" in root.attrs:
        nums = [float(n) for n in _NUM.findall(root.attrs["viewBox"])]
        if len(nums) == 4:
            scene.canvas = (nums[0], nums[1], nums[0] + nums[2], nums[1] + nums[3])
    elif "width" in root.attrs and "height" in root.attrs:
        try:
            scene.canvas = (0.0, 0.0, _num(root, "width"), _num(root, "height"))
        except ValueError:
            pass
    _walk(root, 0.0, 0.0, scene)
    return scene


def _walk(el: El, dx: float, dy: float, scene: Scene) -> None:
    if el.tag not in SUPPORTED:
        scene.unsupported.append((el, f"<{el.tag}> is not understood; it is not checked"))
        return
    if el.tag in INERT:
        return
    try:
        tx, ty = _translate(el)
        dx, dy = dx + tx, dy + ty
        _shape(el, dx, dy, scene)
    except ValueError as exc:
        scene.unsupported.append((el, f"{exc} is not understood; <{el.tag}> is not checked"))
        return
    if el.tag in ("svg", "g"):
        for child in el.children:
            _walk(child, dx, dy, scene)


def _shape(el: El, dx: float, dy: float, scene: Scene) -> None:
    tag = el.tag
    if tag == "rect":
        x, y, w, h = _num(el, "x"), _num(el, "y"), _num(el, "width"), _num(el, "height")
        scene.shapes.append(Shape("rect", _shift((x, y, x + w, y + h), dx, dy), el))
    elif tag in ("circle", "ellipse"):
        rx = _num(el, "r") if tag == "circle" else _num(el, "rx")
        ry = rx if tag == "circle" else _num(el, "ry")
        cx, cy = _num(el, "cx"), _num(el, "cy")
        scene.shapes.append(Shape(tag, _shift((cx - rx, cy - ry, cx + rx, cy + ry), dx, dy), el))
    elif tag == "image":
        x, y, w, h = _num(el, "x"), _num(el, "y"), _num(el, "width"), _num(el, "height")
        scene.images.append(el)
        scene.shapes.append(Shape("image", _shift((x, y, x + w, y + h), dx, dy), el))
    elif tag in ("line", "polyline", "polygon", "path"):
        closed = tag == "polygon"
        if tag == "line":
            points = [(_num(el, "x1"), _num(el, "y1")), (_num(el, "x2"), _num(el, "y2"))]
        elif tag == "path":
            points, closed = _path_points(el.attrs.get("d", ""))
        else:
            nums = [float(n) for n in _NUM.findall(el.attrs.get("points", ""))]
            points = list(zip(nums[0::2], nums[1::2], strict=False))
        points = [(x + dx, y + dy) for x, y in points]
        if not points:
            return
        if "marker-end" in el.attrs or "marker-start" in el.attrs:
            scene.arrows.append(Arrow(points, el))
        elif closed:
            scene.shapes.append(Shape(tag, _bbox(points), el))
    elif tag == "text":
        scene.texts.append(_text(el, dx, dy))


def _style(el: El) -> tuple[float, str, bool, bool]:
    size = float((_NUM.findall(el.get("font-size") or "") or ["16"])[0])
    fam = "mono" if "mono" in (el.get("font-family") or "").lower() else "sans"
    weight = (el.get("font-weight") or "normal").lower()
    bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 600)
    return size, fam, bold, (el.get("font-style") or "normal").lower() in ("italic", "oblique")


def _text(el: El, dx: float, dy: float) -> Text:
    """Lines of runs: a `tspan` with its own `x`, `y` or `dy` starts a new line, others continue."""
    preserve = el.get("space") == "preserve"
    x0, y0 = _num(el, "x") + dx, _num(el, "y") + dy
    lines: list[tuple[float, float, list[Run]]] = [(x0, y0, [])]

    def add(owner: El, raw: str) -> None:
        text = raw if preserve else re.sub(r"\s+", " ", raw)
        if text:
            size, fam, bold, ital = _style(owner)
            lines[-1][2].append(Run(text, size, fam, bold, ital))

    for item in el.content:
        if isinstance(item, str):
            add(el, item)
            continue
        if any(k in item.attrs for k in ("x", "y", "dy")):
            x = _num(item, "x") + dx if "x" in item.attrs else lines[-1][0]
            y = _num(item, "y") + dy if "y" in item.attrs else lines[-1][1] + _num(item, "dy")
            lines.append((x, y, []))
        for part in item.content:
            if isinstance(part, str):
                add(item, part)
    out: list[TextLine] = []
    anchor = ANCHOR.get(el.get("text-anchor") or "start", 0.0)
    for x, y, runs in lines:
        if not runs:
            continue
        if not preserve:
            runs[0].text = runs[0].text.lstrip()
            runs[-1].text = runs[-1].text.rstrip()
        width = sum(fonts.text_width(r.text, r.fam, r.bold, r.ital, r.size) for r in runs)
        size = max(r.size for r in runs)
        asc, desc = fonts.asc_desc(runs[0].fam, size)
        left = x - anchor * width
        out.append(TextLine((left, y - asc, left + width, y + desc), "".join(r.text for r in runs), runs))
    return Text(el, (x0, y0), out)


# --- geometry ------------------------------------------------------------------------------


def _contains(outer: Box, inner: Box, tol: float = TOL) -> bool:
    return (
        outer[0] - tol <= inner[0] and outer[1] - tol <= inner[1]
        and inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol
    )


def _overlap(a: Box, b: Box) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _has_point(box: Box, point: tuple[float, float], tol: float) -> bool:
    return box[0] - tol <= point[0] <= box[2] + tol and box[1] - tol <= point[1] <= box[3] + tol


def _segment_enters(a: tuple[float, float], b: tuple[float, float], box: Box) -> bool:
    """Whether the segment runs through the interior of `box` for more than half a pixel (Liang-Barsky)."""
    (x0, y0), (x1, y1) = a, b
    t0, t1 = 0.0, 1.0
    for p, q in ((x0 - x1, x0 - box[0]), (x1 - x0, box[2] - x0), (y0 - y1, y0 - box[1]), (y1 - y0, box[3] - y0)):
        if p == 0:
            if q < 0:
                return False
        elif p < 0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
        if t0 > t1:
            return False
    return (t1 - t0) * ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 > TOL


def _distance(point: tuple[float, float], path: list[tuple[float, float]]) -> float:
    """The distance from `point` to a polyline."""
    best = float("inf")
    for (x0, y0), (x1, y1) in zip(path, path[1:], strict=False):
        dx, dy = x1 - x0, y1 - y0
        length = dx * dx + dy * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, ((point[0] - x0) * dx + (point[1] - y0) * dy) / length))
        best = min(best, ((point[0] - x0 - t * dx) ** 2 + (point[1] - y0 - t * dy) ** 2) ** 0.5)
    return best


def _solid(shape: Shape) -> bool:
    return min(shape.box[2] - shape.box[0], shape.box[3] - shape.box[1]) >= MIN_SHAPE


# --- checks --------------------------------------------------------------------------------


def _label(text: str) -> str:
    return f"'{text[:30]}...'" if len(text) > 30 else f"'{text}'"


def check_scene(scene: Scene, file: str, base: Path) -> list[Finding]:
    findings: list[Finding] = []
    for el, message in scene.unsupported:
        findings.append(finding("svg-unsupported", file, el.line, message))
    rects = [s for s in scene.shapes if s.kind == "rect" and _solid(s)]
    solid = [s for s in scene.shapes if _solid(s)]

    for text in scene.texts:
        for line in text.lines:
            for run in line.runs:
                missing = sorted({c for c in run.text if not c.isspace() and not fonts.has_glyph(c, run.fam, run.bold, run.ital)})
                for ch in missing:
                    findings.append(finding("svg-glyph-missing", file, text.el.line, f"{ch!r} (U+{ord(ch):04X}) cannot be drawn by the font; use plain ASCII"))
            if "$" in line.text:
                findings.append(finding("svg-math-in-text", file, text.el.line, f"{_label(line.text)} holds a literal `$`; render the formula as an image"))

    hosts: dict[int, Shape | None] = {}
    for text in scene.texts:
        hosting = [r for r in rects if _has_point(r.box, text.anchor, 0.0)]
        hosts[id(text)] = min(hosting, key=lambda r: (r.box[2] - r.box[0]) * (r.box[3] - r.box[1]), default=None)
        for line in text.lines:
            host = hosts[id(text)]
            if host is not None and not _contains(host.box, line.box):
                findings.append(finding("svg-overflow", file, text.el.line,
                    f"{_label(line.text)} is {line.box[2] - line.box[0]:.0f}px wide but its box at line {host.el.line} "
                    f"is {host.box[2] - host.box[0]:.0f}x{host.box[3] - host.box[1]:.0f}px; widen the box or shorten the text"))
            elif scene.canvas is not None and not _contains(scene.canvas, line.box):
                findings.append(finding("svg-overflow", file, text.el.line, f"{_label(line.text)} leaves the canvas"))

    for text in scene.texts:
        for line in text.lines:
            for shape in solid:
                if shape is hosts[id(text)] or _contains(shape.box, line.box) or _overlap(line.box, shape.box) < 1.0:
                    continue
                findings.append(finding("svg-collision", file, text.el.line,
                    f"{_label(line.text)} overlaps the {shape.kind} at line {shape.el.line} without being inside it"))
    for i, a in enumerate(scene.texts):
        for b in scene.texts[i + 1:]:
            if any(_overlap(la.box, lb.box) >= 1.0 for la in a.lines for lb in b.lines):
                findings.append(finding("svg-collision", file, b.el.line,
                    f"text at line {b.el.line} overlaps the text at line {a.el.line}"))

    for arrow in scene.arrows:
        start, end = arrow.points[0], arrow.points[-1]
        for shape in solid:
            if _has_point(shape.box, start, END_TOL) or _has_point(shape.box, end, END_TOL):
                continue
            center = ((shape.box[0] + shape.box[2]) / 2, (shape.box[1] + shape.box[3]) / 2)
            if max(shape.box[2] - shape.box[0], shape.box[3] - shape.box[1]) <= BADGE and _distance(center, arrow.points) <= 1.0:
                continue  # a badge or label background centred on the arrow
            inner = (shape.box[0] + 1, shape.box[1] + 1, shape.box[2] - 1, shape.box[3] - 1)
            if any(_segment_enters(p, q, inner) for p, q in zip(arrow.points, arrow.points[1:], strict=False)):
                findings.append(finding("svg-arrow-crossing", file, arrow.el.line,
                    f"the arrow runs through the {shape.kind} at line {shape.el.line}, which is neither its start nor its end"))

    for image in scene.images:
        href = image.attrs.get("href", "")
        # `sources/` paths belong to the shared `source-missing` check.
        if href and not href.startswith(("data:", "http://", "https://", "sources/")) and not (base / href).is_file():
            findings.append(finding("svg-href-missing", file, image.line, f"{href} does not exist (a path relative to {PROJECT_DIR}/)"))
    return findings


def check(root: Path, artifact: str, entrypoint: str) -> list[Finding]:
    base = root / PROJECT_DIR
    rel = f"artifacts/{artifact}/{entrypoint}"
    try:
        scene = collect(parse((base / rel).read_text(encoding="utf-8")))
    except ValueError as exc:
        message, line = exc.args if len(exc.args) == 2 else (str(exc), 1)
        return [finding("svg-malformed", rel, line, str(message))]
    return check_scene(scene, rel, base)
