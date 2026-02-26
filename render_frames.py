#!/usr/bin/env python3
"""Render one frame of each stardust animation to a PNG file."""

import sys
import os
import math
import random
import re

sys.path.insert(0, os.path.dirname(__file__))

# Import animation classes from stardust
import importlib.util
import types
stardust_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stardust")
loader = importlib.machinery.SourceFileLoader("stardust_mod", stardust_path)
spec = importlib.util.spec_from_loader("stardust_mod", loader)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from PIL import Image, ImageDraw, ImageFont

# ─── 256-color ANSI palette → RGB ───────────────────────────────────────────

def build_ansi_256_palette():
    palette = {}
    # Standard 16 colors (approx)
    base16 = [
        (0,0,0),(128,0,0),(0,128,0),(128,128,0),(0,0,128),(128,0,128),(0,128,128),(192,192,192),
        (128,128,128),(255,0,0),(0,255,0),(255,255,0),(0,0,255),(255,0,255),(0,255,255),(255,255,255),
    ]
    for i, c in enumerate(base16):
        palette[i] = c
    # 216 color cube (16-231)
    for i in range(216):
        r = i // 36
        g = (i % 36) // 6
        b = i % 6
        palette[16 + i] = (r * 51, g * 51, b * 51)
    # Grayscale (232-255)
    for i in range(24):
        v = 8 + i * 10
        palette[232 + i] = (v, v, v)
    return palette

PALETTE = build_ansi_256_palette()

# ─── Parse ANSI from grid cell value ────────────────────────────────────────

def parse_cell(val):
    """Extract (char, color_rgb, bold) from an ANSI-escaped cell string."""
    # Pattern: \033[...m<char>\033[0m
    # Codes can be like: 1;38;5;255  or  2;38;5;51  or  38;5;240
    m = re.match(r'\033\[([\d;]*)m(.)', val)
    if not m:
        return val[0] if val else ' ', (128, 128, 128), False

    codes_str = m.group(1)
    char = m.group(2)
    codes = [int(c) for c in codes_str.split(';') if c]

    bold = False
    dim = False
    color = (192, 192, 192)  # default

    i = 0
    while i < len(codes):
        c = codes[i]
        if c == 1:
            bold = True
        elif c == 2:
            dim = True
        elif c == 38 and i + 2 < len(codes) and codes[i+1] == 5:
            color = PALETTE.get(codes[i+2], (192, 192, 192))
            i += 2
        i += 1

    if dim:
        color = tuple(max(0, int(v * 0.5)) for v in color)

    return char, color, bold


# ─── Render one animation frame ─────────────────────────────────────────────

TERM_W = 100
TERM_H = 32
CELL_W = 9
CELL_H = 16
FONT_SIZE = 14
BG_COLOR = (13, 13, 18)  # dark space background

def render_animation(anim_def, output_path, t_value=2.5, sim_steps=150):
    """Render a single frame of the given animation to a PNG.

    Simulates sim_steps frames up to t_value so that time-accumulated
    elements (meteors, rings, particles) are properly populated.
    """
    random.seed(42)  # deterministic

    anim_cls = mod.ANIM_CLASSES[anim_def['class']]
    anim = anim_cls(
        anim_def['colors'],
        None,
        anim_def['name'],
        activity=None,
    )

    h, w = TERM_H, TERM_W

    # Simulate animation over time so elements accumulate
    dt = t_value / max(sim_steps, 1)
    for step in range(sim_steps):
        anim.start_time = 0.0
        anim.t = dt * (step + 1)
        anim._regenerate(h, w)
        grid = {}
        anim._render_content(h, w, grid)

    # Final frame
    anim.t = t_value
    grid = {}
    anim._render_content(h, w, grid)

    # Create image
    img_w = TERM_W * CELL_W
    img_h = (TERM_H - 2) * CELL_H  # render area only (no status bar)
    img = Image.new('RGB', (img_w, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype('Menlo', FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()

    render_h = h - 2

    for (row, col), val in grid.items():
        if row >= render_h or col >= w:
            continue
        char, color, bold = parse_cell(val)

        x = col * CELL_W
        y = row * CELL_H

        # Slight glow for bold characters
        if bold:
            glow = tuple(min(255, int(v * 0.3)) for v in color)
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((x + dx, y + dy), char, fill=glow, font=font)

        draw.text((x, y), char, fill=color, font=font)

    # Draw the status bar
    sep_y = render_h * CELL_H - 2
    c0 = PALETTE.get(anim_def['colors'][0], (128, 128, 128))
    sep_color = tuple(int(v * 0.4) for v in c0)
    draw.line([(0, sep_y), (img_w, sep_y)], fill=sep_color, width=1)

    # Add a subtle vignette
    for row in range(img_h):
        for pass_n in range(2):
            edge_dist = min(row, img_h - row) / (img_h / 2)
            if edge_dist < 0.15:
                alpha = edge_dist / 0.15
                # Darken edges
                if pass_n == 0 and row < 3:
                    draw.line([(0, row), (img_w, row)],
                              fill=tuple(int(v * (0.3 + 0.7 * alpha)) for v in BG_COLOR))
                break

    # Add animation name as subtle label bottom-right
    label = f"  {anim_def['name']}  "
    label_color = tuple(min(255, int(v * 0.8)) for v in c0)
    try:
        label_font = ImageFont.truetype('Menlo', 11)
    except Exception:
        label_font = font
    bbox = draw.textbbox((0, 0), label, font=label_font)
    lw = bbox[2] - bbox[0]
    lh = bbox[3] - bbox[1]
    lx = img_w - lw - 8
    ly = img_h - lh - 6
    draw.rounded_rectangle([(lx - 4, ly - 2), (lx + lw + 4, ly + lh + 4)],
                           radius=4, fill=(20, 20, 28))
    draw.text((lx, ly), label, fill=label_color, font=label_font)

    img.save(output_path, 'PNG', optimize=True)
    print(f"  Saved {output_path}")


# ─── Best time values per animation for a nice frame ────────────────────────

BEST_TIMES = {
    'SpiralGalaxy': 4.0,
    'Nebula': 5.0,
    'MeteorShower': 3.5,
    'Pulsar': 6.0,
    'Aurora': 3.0,
    'Wormhole': 4.0,
}

SIM_STEPS = {
    'SpiralGalaxy': 60,
    'Nebula': 80,
    'MeteorShower': 200,
    'Pulsar': 250,
    'Aurora': 60,
    'Wormhole': 100,
}

def main():
    out_dir = os.path.join(os.path.dirname(__file__), 'assets')
    os.makedirs(out_dir, exist_ok=True)

    for anim_def in mod.ANIMATIONS:
        name = anim_def['class']
        t = BEST_TIMES.get(name, 2.5)
        slug = anim_def['name'].lower().replace(' ', '-')
        path = os.path.join(out_dir, f'{slug}.png')
        steps = SIM_STEPS.get(name, 150)
        render_animation(anim_def, path, t_value=t, sim_steps=steps)

    print("\nAll frames rendered.")


if __name__ == '__main__':
    main()
