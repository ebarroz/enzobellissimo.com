#!/usr/bin/env python3
"""Render a 1200x630 Open Graph card.

    python3 tools/make-og.py "Title of the essay" assets/og-my-post.png [--eyebrow "ESSAY"]

Needs rsvg-convert (librsvg). The card mirrors the site's dark palette so a
shared link looks like the page it opens.
"""
import argparse, html, subprocess, sys, tempfile, os

W, H = 1200, 630
BG, FG, DIM = "#0b0d12", "#ebe6dc", "#8b8791"
TEAL, EMBER, SAND = "#5eead4", "#fb923c", "#fde68a"
SERIF = "P052, Palatino, Georgia, serif"
MONO = "DejaVu Sans Mono, monospace"


def wrap(text, max_chars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) <= max_chars or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build(title, eyebrow, footer):
    size = 74
    lines = wrap(title, 26)
    while len(lines) > 4 and size > 46:          # shrink until it fits four lines
        size -= 8
        lines = wrap(title, int(26 * 74 / size))
    lines = lines[:4]

    leading = int(size * 1.16)
    block_h = leading * len(lines)
    top = 300 - block_h // 2 + size            # baseline of first line

    tspans = "".join(
        f'<tspan x="90" y="{top + i * leading}">{html.escape(l)}</tspan>'
        for i, l in enumerate(lines)
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="mark" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#14b8a6"/><stop offset=".48" stop-color="#0f766e"/><stop offset="1" stop-color="#c2410c"/>
    </linearGradient>
    <radialGradient id="glowA" cx="0" cy="0" r="1">
      <stop offset="0" stop-color="{TEAL}" stop-opacity=".26"/><stop offset="1" stop-color="{TEAL}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glowB" cx="1" cy="1" r="1">
      <stop offset="0" stop-color="{EMBER}" stop-opacity=".20"/><stop offset="1" stop-color="{EMBER}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{TEAL}"/><stop offset="1" stop-color="{EMBER}"/>
    </linearGradient>
    <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
      <path d="M48 0H0v48" fill="none" stroke="{FG}" stroke-opacity=".05" stroke-width="1"/>
    </pattern>
  </defs>

  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect width="{W}" height="{H}" fill="url(#grid)"/>
  <ellipse cx="120" cy="40" rx="620" ry="480" fill="url(#glowA)"/>
  <ellipse cx="1120" cy="600" rx="560" ry="420" fill="url(#glowB)"/>
  <rect x="0" y="0" width="{W}" height="6" fill="url(#rule)"/>

  <!-- brand mark -->
  <g transform="translate(90,74) scale(0.72)">
    <rect width="64" height="64" rx="16" fill="url(#mark)"/>
    <g fill="#f5f1e8">
      <rect x="18" y="16" width="8" height="32" rx="1.5"/>
      <rect x="18" y="16" width="28" height="7" rx="1.5"/>
      <rect x="18" y="28.5" width="21" height="7" rx="1.5"/>
      <rect x="18" y="41" width="28" height="7" rx="1.5"/>
    </g>
    <circle cx="45" cy="32" r="2.6" fill="{SAND}"/>
  </g>
  <text x="150" y="99" font-family="{MONO}" font-size="20" letter-spacing="3" fill="{DIM}">{html.escape(eyebrow.upper())}</text>

  <!-- title -->
  <text font-family="{SERIF}" font-size="{size}" fill="{FG}" letter-spacing="-1">{tspans}</text>

  <!-- footer -->
  <line x1="90" y1="524" x2="1110" y2="524" stroke="{FG}" stroke-opacity=".12" stroke-width="1"/>
  <text x="90" y="566" font-family="{MONO}" font-size="21" letter-spacing="1.5" fill="{FG}">{html.escape(footer)}</text>
  <text x="1110" y="566" text-anchor="end" font-family="{MONO}" font-size="21" letter-spacing="1.5" fill="{DIM}">blog.enzobellissimo.com</text>
</svg>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("title")
    ap.add_argument("out")
    ap.add_argument("--eyebrow", default="Essay")
    ap.add_argument("--footer", default="Enzo Barros Bellissimo")
    a = ap.parse_args()

    svg = build(a.title, a.eyebrow, a.footer)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False, encoding="utf-8") as f:
        f.write(svg)
        tmp = f.name
    try:
        subprocess.run(
            ["rsvg-convert", "-w", str(W), "-h", str(H), "-o", a.out, tmp], check=True
        )
    finally:
        os.unlink(tmp)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
