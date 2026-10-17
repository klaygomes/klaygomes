from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONT = ROOT / "tools" / "fonts" / "Archivo.ttf"
OUT = ROOT / "assets"

WIDTH = 880
GUTTER = 160
RIGHT = WIDTH - 36
RADIUS = 20

PURPLE_900 = "#480F7B"
PURPLE_700 = "#7E23B3"
MAGENTA_500 = "#C63F75"
MAGENTA_700 = "#B61A54"
YELLOW = "#FAD30B"
LILAC_50 = "#F7F2FB"
LILAC_100 = "#EDE3F5"
WHITE = "#FDFDFD"
INK = "#25063C"


@dataclass(frozen=True)
class Style:
    size: float
    wght: int = 400
    wdth: int = 100
    tracking: float = 0.0


NAME = Style(56, 820, 112, -0.015)
ROLE = Style(22, 500)
READOUT = Style(36, 780, 100, -0.01)
READOUT_SUB = Style(16, 400)
LABEL = Style(15, 650, 70, 0.08)
INDEX = Style(12, 560, 70, 0.08)
FLAG = Style(12, 720, 70)
PACKET = Style(17, 540, 92)
PACKET_STRONG = Style(17, 720, 92)
SECTION = Style(30, 820, 108, -0.01)
SECTION_INDEX = Style(14, 720, 70, 0.08)
BADGE_TAG = Style(12, 700, 70, 0.12)
BADGE = Style(18, 600, 96)
CLOSE = Style(32, 820, 108, -0.01)

MOTION = """<style>
.clk{animation:run 1s linear infinite}
@keyframes run{to{transform:translateX(-22px)}}
.a0,.a1,.a2,.a3{animation-timing-function:cubic-bezier(.45,0,.55,1);animation-iteration-count:infinite;animation-direction:alternate}
.a0{animation-name:d0;animation-duration:31s;animation-delay:-4s}
.a1{animation-name:d1;animation-duration:43s;animation-delay:-27s}
.a2{animation-name:d2;animation-duration:37s;animation-delay:-15s}
.a3{animation-name:d3;animation-duration:53s;animation-delay:-41s}
@keyframes d0{from{transform:translate(0,0)}to{transform:translate(-26px,12px)}}
@keyframes d1{from{transform:translate(0,0)}to{transform:translate(22px,-14px)}}
@keyframes d2{from{transform:translate(0,0)}to{transform:translate(-14px,-18px)}}
@keyframes d3{from{transform:translate(0,0)}to{transform:translate(18px,16px)}}
@media (prefers-reduced-motion:reduce){.clk,.a0,.a1,.a2,.a3{animation:none}}
</style>"""


class Typesetter:
    def __init__(self, path: Path):
        self.tt = TTFont(path)
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        self.hbfont = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))

    @cache
    def glyphset(self, wght: int, wdth: int):
        return self.tt.getGlyphSet(location={"wght": wght, "wdth": wdth}, normalized=False)

    def shape(self, text: str, style: Style):
        self.hbfont.set_variations({"wght": style.wght, "wdth": style.wdth})
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hbfont, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, text: str, style: Style) -> float:
        scale = style.size / self.upem
        _, positions = self.shape(text, style)
        advance = sum(p.x_advance for p in positions) * scale
        return advance + style.tracking * style.size * (len(positions) - 1)

    def path(self, text: str, x: float, y: float, style: Style, fill: str, anchor: str = "start", opacity: float = 1) -> str:
        scale = style.size / self.upem
        if anchor != "start":
            w = self.width(text, style)
            x -= w if anchor == "end" else w / 2
        infos, positions = self.shape(text, style)
        glyphs = self.glyphset(style.wght, style.wdth)
        pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
        cursor = x
        for info, pos in zip(infos, positions):
            glyph_x = cursor + pos.x_offset * scale
            glyph_y = y - pos.y_offset * scale
            glyphs[self.order[info.codepoint]].draw(TransformPen(pen, (scale, 0, 0, -scale, glyph_x, glyph_y)))
            cursor += pos.x_advance * scale + style.tracking * style.size
        alpha = f' fill-opacity="{opacity:g}"' if opacity < 1 else ""
        return f'<path fill="{fill}"{alpha} d="{pen.getCommands()}"/>'


TS = Typesetter(FONT)


@dataclass(frozen=True)
class Packet:
    x: float
    text: str
    fill: str = WHITE
    ink: str = PURPLE_900
    strong: bool = False


def svg(width: float, height: float, body: list[str], title: str, motion: bool = False) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
        f'viewBox="0 0 {width:g} {height:g}" role="img"><title>{title}</title>'
        + (MOTION if motion else "")
        + "".join(body)
        + "</svg>\n"
    )


@dataclass(frozen=True)
class Aura:
    color: str
    opacity: float
    seed: int
    cx: float
    cy: float
    r: float
    frequency: str = "0.003 0.005"
    blend: str = ""


def hex_rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def panel(height: float, ground: str, auras: Sequence[Aura], uid: str, border: str = LILAC_100) -> list[str]:
    bleed = 90
    defs, layers = [], []
    for i, a in enumerate(auras):
        r, g, b = hex_rgb(a.color)
        gain, cut = 2.6 * a.opacity, -1.1 * a.opacity
        defs.append(
            f'<filter id="aura-{uid}-{i}" filterUnits="userSpaceOnUse" x="{-bleed}" y="{-bleed}" '
            f'width="{WIDTH + bleed * 2}" height="{height + bleed * 2:g}" color-interpolation-filters="sRGB">'
            f'<feTurbulence type="fractalNoise" baseFrequency="{a.frequency}" numOctaves="2" seed="{a.seed}"/>'
            f'<feColorMatrix type="matrix" values="0 0 0 0 {r:.3f} 0 0 0 0 {g:.3f} 0 0 0 0 {b:.3f} {gain:.2f} 0 0 0 {cut:.2f}"/>'
            f'<feGaussianBlur stdDeviation="32"/></filter>'
            f'<radialGradient id="spot-{uid}-{i}" gradientUnits="userSpaceOnUse" cx="{a.cx:g}" cy="{a.cy:g}" r="{a.r:g}">'
            f'<stop offset="0" stop-color="#fff"/><stop offset=".5" stop-color="#fff" stop-opacity=".55"/>'
            f'<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
            f'<mask id="mask-{uid}-{i}" maskUnits="userSpaceOnUse" x="0" y="0" width="{WIDTH}" height="{height:g}">'
            f'<rect width="{WIDTH}" height="{height:g}" fill="url(#spot-{uid}-{i})"/></mask>'
        )
        blend = f' style="mix-blend-mode:{a.blend}"' if a.blend else ""
        layers.append(
            f'<g mask="url(#mask-{uid}-{i})"{blend}><rect class="a{i}" x="{-bleed}" y="{-bleed}" '
            f'width="{WIDTH + bleed * 2}" height="{height + bleed * 2:g}" filter="url(#aura-{uid}-{i})"/></g>'
        )
    return [
        f'<defs>{"".join(defs)}<clipPath id="clip-{uid}"><rect width="{WIDTH}" height="{height:g}" rx="{RADIUS}"/></clipPath></defs>',
        f'<g clip-path="url(#clip-{uid})"><rect width="{WIDTH}" height="{height:g}" fill="{ground}"/>{"".join(layers)}</g>',
        f'<rect x=".75" y=".75" width="{WIDTH - 1.5}" height="{height - 1.5:g}" rx="{RADIUS - 0.75}" fill="none" stroke="{border}" stroke-width="1.5"/>',
    ]


def hexagon(x: float, mid: float, w: float, h: float, point: float = 9) -> str:
    top, bottom = mid - h / 2, mid + h / 2
    return (
        f"M{x:g} {mid:g}L{x + point:g} {top:g}H{x + w - point:g}L{x + w:g} {mid:g}"
        f"L{x + w - point:g} {bottom:g}H{x + point:g}Z"
    )


def line(x1: float, y1: float, x2: float, y2: float, stroke: str, width: float = 1.5, opacity: float = 1, dash: str = "") -> str:
    extra = (f' stroke-opacity="{opacity:g}"' if opacity < 1 else "") + (f' stroke-dasharray="{dash}"' if dash else "")
    return f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{stroke}" stroke-width="{width:g}"{extra}/>'


def packet_width(p: Packet, pad: float = 18) -> float:
    return TS.width(p.text, PACKET_STRONG if p.strong else PACKET) + pad * 2


def draw_packet(p: Packet, mid: float, h: float = 30) -> list[str]:
    style = PACKET_STRONG if p.strong else PACKET
    w = packet_width(p)
    return [
        f'<path d="{hexagon(p.x, mid, w, h)}" fill="{p.fill}" stroke="{PURPLE_700}" stroke-opacity=".3" '
        f'stroke-width="1.5" stroke-linejoin="round"/>',
        TS.path(p.text, p.x + w / 2, mid + style.size * 0.35, style, p.ink, "middle"),
    ]


def flow(start: float, packets: Sequence[Packet], gap: float = 14) -> list[Packet]:
    placed, x = [], start
    for p in packets:
        placed.append(Packet(x, p.text, p.fill, p.ink, p.strong))
        x += packet_width(p) + gap
    if x - gap > RIGHT:
        raise ValueError(f"lane overflows by {x - gap - RIGHT:.0f}px: {[p.text for p in packets]}")
    return placed


def bus(mid: float, packets: Sequence[Packet], start: float = GUTTER, end: float = RIGHT) -> list[str]:
    parts = []
    cursor = start
    for p in packets:
        parts.append(line(cursor, mid, p.x, mid, PURPLE_700, opacity=0.22))
        parts += draw_packet(p, mid)
        cursor = p.x + packet_width(p)
    parts.append(line(cursor, mid, end, mid, PURPLE_700, opacity=0.22))
    return parts


def clock(mid: float, start: float, end: float, uid: str, stroke: str = YELLOW, period: float = 22, amp: float = 11) -> list[str]:
    high, low = mid - amp, mid + amp
    x = start
    d = [f"M{x:g} {low:g}"]
    while x < end + period * 2:
        d.append(f"H{x + period / 2:g}V{high:g}H{x + period:g}V{low:g}")
        x += period
    return [
        f'<clipPath id="clk-{uid}"><rect x="{start:g}" y="{high - 2:g}" width="{end - start:g}" height="{amp * 2 + 4:g}"/></clipPath>',
        f'<g clip-path="url(#clk-{uid})"><path class="clk" d="{"".join(d)}" fill="none" stroke="{stroke}" '
        f'stroke-width="2" stroke-linejoin="miter"/></g>',
    ]


def channel_label(index: str, name: str, mid: float) -> list[str]:
    return [
        TS.path(index, 36, mid + 4.4, INDEX, PURPLE_700, opacity=0.7),
        TS.path(name, 64, mid + 5, LABEL, PURPLE_900),
    ]


def cursor_flag(x: float, top: float, bottom: float, letter: str) -> list[str]:
    return [
        line(x, top + 18, x, bottom, PURPLE_700, 1.25, 0.4, "4 4"),
        f'<rect x="{x - 10:g}" y="{top:g}" width="20" height="20" rx="4" fill="{YELLOW}"/>',
        TS.path(letter, x, top + 14.5, FLAG, INK, "middle"),
    ]


def hero() -> str:
    height = 556
    body = panel(height, LILAC_50, [
        Aura(YELLOW, 0.55, 23, 820, 30, 340, "0.0026 0.004"),
        Aura(MAGENTA_500, 0.16, 11, 90, 110, 420, "0.0034 0.0042"),
        Aura(PURPLE_700, 0.12, 3, 520, 420, 380),
        Aura(WHITE, 0.8, 41, 380, 260, 420, "0.004 0.006", "lighten"),
    ], "hero")
    body.append(TS.path("Cleiton Loiola", 36, 78, NAME, PURPLE_900))
    body.append(TS.path("Tech Lead at Qred, Stockholm", 38, 114, ROLE, INK))
    body.append(TS.path("Δ A→B  20+ years", RIGHT, 80, READOUT, MAGENTA_700, "end"))
    body.append(TS.path("of JavaScript and Node.js on UNIX", RIGHT, 112, READOUT_SUB, INK, "end"))

    rule_y = 144
    body.append(line(0, rule_y, WIDTH, rule_y, PURPLE_700, 1, 0.15))
    x, i = GUTTER, 0
    while x <= RIGHT:
        body.append(line(x, rule_y, x, rule_y + (9 if i % 4 == 0 else 5), PURPLE_700, 1, 0.35))
        x += 11
        i += 1

    lanes_top, lane_h = 182, 46
    work = [
        ("D0", "CAREER", 200, [Packet(0, "Resultados Digitais"), Packet(0, "Klarna"), Packet(0, "SEB"),
                               Packet(0, "Mentimeter"), Packet(0, "Qred", YELLOW, INK, True)]),
        ("D1", "LEAD", 250, [Packet(0, "tech leadership"), Packet(0, "hiring"),
                             Packet(0, "coaching"), Packet(0, "agentic AI")]),
        ("D2", "FRONTEND", 214, [Packet(0, "React"), Packet(0, "Next.js"), Packet(0, "TypeScript"),
                                 Packet(0, "micro-frontends", LILAC_100, PURPLE_900, True)]),
        ("D3", "BACKEND", 190, [Packet(0, "Node.js", LILAC_100, PURPLE_900, True), Packet(0, "JavaScript"),
                                Packet(0, "PostgreSQL"), Packet(0, "Redis")]),
        ("D4", "PLATFORM", 236, [Packet(0, "AWS"), Packet(0, "Docker"), Packet(0, "Kubernetes"),
                                 Packet(0, "OpenTelemetry"), Packet(0, "CI/CD")]),
    ]
    for n, (index, name, start, packets) in enumerate(work):
        mid = lanes_top + n * lane_h + lane_h / 2
        body += channel_label(index, name, mid)
        body += bus(mid, flow(start, packets))

    divider_y = lanes_top + len(work) * lane_h + 14
    body.append(line(36, divider_y, RIGHT, divider_y, PURPLE_700, 1, 0.18))
    tag = "AFTER HOURS: HOBBIES"
    tag_w = TS.width(tag, LABEL) + 24
    body.append(f'<rect x="{GUTTER + 34:g}" y="{divider_y - 11:g}" width="{tag_w:g}" height="22" rx="4" fill="{MAGENTA_500}"/>')
    body.append(TS.path(tag, GUTTER + 46, divider_y + 5, LABEL, WHITE))

    hobby_top = divider_y + 14
    hobby_mid = hobby_top + lane_h / 2
    body += channel_label("D5", "LOW-LEVEL", hobby_mid)
    body += bus(hobby_mid, flow(300, [Packet(0, "C", MAGENTA_500, WHITE, True), Packet(0, "Rust", MAGENTA_500, WHITE, True),
                                      Packet(0, "embedded")]))

    clk_mid = hobby_top + lane_h + lane_h / 2
    body += channel_label("D6", "STM32 CLK", clk_mid)
    tag = Packet(0, "STM32 clock tree")
    tag = Packet(RIGHT - packet_width(tag), tag.text)
    body += clock(clk_mid, GUTTER, tag.x - 14, "hero", MAGENTA_500)
    body += draw_packet(tag, clk_mid)

    body += cursor_flag(182, rule_y + 14, height - 16, "A")
    body += cursor_flag(RIGHT - 4, rule_y + 14, height - 16, "B")
    return svg(
        WIDTH,
        height,
        body,
        "Cleiton Loiola, Tech Lead at Qred, Stockholm. 20+ years of JavaScript and Node.js on UNIX. Previously Mentimeter, SEB, Klarna and Resultados Digitais. Hobbies: C, Rust and STM32.",
        motion=True,
    )


def section(title: str, index: str) -> str:
    height, mid = 80, 40
    body = [TS.path(index, 2, mid + 5, SECTION_INDEX, MAGENTA_500)]
    x = 44
    w = TS.width(title, SECTION) + 52
    body.append(line(28, mid, x, mid, MAGENTA_500, 1.5))
    body.append(
        f'<path d="{hexagon(x, mid, w, 54, 14)}" fill="{LILAC_50}" stroke="{PURPLE_700}" stroke-opacity=".35" '
        f'stroke-width="1.5" stroke-linejoin="round"/>'
    )
    body.append(TS.path(title, x + w / 2, mid + 10.5, SECTION, PURPLE_900, "middle"))
    end = x + w
    body.append(line(end, mid, end + 40, mid, MAGENTA_500, 1.5))
    pulse = f"M{end + 40:g} {mid:g}V{mid - 12:g}H{end + 60:g}V{mid:g}H{WIDTH - 2:g}"
    body.append(f'<path d="{pulse}" fill="none" stroke="{MAGENTA_500}" stroke-width="1.5"/>')
    return svg(WIDTH, height, body, title)


def badge(tag: str, text: str, fill: str, ink: str) -> str:
    height, pad, point = 44, 20, 12
    tag_w = TS.width(tag, BADGE_TAG)
    text_w = TS.width(text, BADGE)
    width = pad + tag_w + 12 + text_w + pad + 2
    body = [
        f'<path d="{hexagon(1, height / 2, width - 2, height - 2, point)}" fill="{fill}"/>',
        TS.path(tag, 1 + pad, height / 2 + 4, BADGE_TAG, ink, opacity=0.7),
        TS.path(text, 1 + pad + tag_w + 12, height / 2 + 6.3, BADGE, ink),
    ]
    return svg(round(width, 1), height, body, f"{tag}: {text}")


def close() -> str:
    height = 124
    body = panel(height, YELLOW, [
        Aura(WHITE, 0.55, 29, 660, 10, 280, "0.005 0.014", "lighten"),
        Aura(MAGENTA_500, 0.16, 5, 110, 80, 300, "0.004 0.012"),
        Aura(PURPLE_700, 0.1, 9, 470, 124, 240, "0.003 0.01"),
    ], "close", YELLOW)
    mid = 64
    body += channel_label("D6", "STM32 CLK", mid)
    body += clock(mid, GUTTER, 470, "close", PURPLE_900)
    body.append(line(470, 22, 470, height - 22, PURPLE_900, 1.25, 0.45, "4 4"))
    body.append(TS.path("ssh cleiton.se", 496, mid + 11.5, CLOSE, PURPLE_900))
    return svg(WIDTH, height, body, "ssh cleiton.se", motion=True)


def main():
    OUT.mkdir(exist_ok=True)
    for stale in OUT.glob("*.svg"):
        stale.unlink()
    files = {
        "capture": hero(),
        "section-building": section("Building now", "D5"),
        "section-projects": section("Projects", "D6"),
        "section-writing": section("Writing", "D7"),
        "contact-email": badge("MAIL", "email@cleiton.dev", YELLOW, INK),
        "contact-linkedin": badge("LINKEDIN", "klaygomes", LILAC_100, PURPLE_900),
        "contact-blog": badge("BLOG", "estacouveflor.com", LILAC_100, MAGENTA_700),
        "close": close(),
    }
    for name, content in files.items():
        (OUT / f"{name}.svg").write_text(content)


if __name__ == "__main__":
    main()
