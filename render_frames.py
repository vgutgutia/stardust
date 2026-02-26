#!/usr/bin/env python3
"""Render animated GIFs of each stardust animation for the README."""

import sys
import os
import math
import random
import re

sys.path.insert(0, os.path.dirname(__file__))

import importlib.util
import importlib.machinery
stardust_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stardust")
loader = importlib.machinery.SourceFileLoader("stardust_mod", stardust_path)
spec = importlib.util.spec_from_loader("stardust_mod", loader)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── 256-color ANSI palette → RGB ───────────────────────────────────────────

def build_ansi_256_palette():
    palette = {}
    base16 = [
        (0,0,0),(170,0,0),(0,170,0),(170,170,0),(0,0,170),(170,0,170),(0,170,170),(170,170,170),
        (85,85,85),(255,85,85),(85,255,85),(255,255,85),(85,85,255),(255,85,255),(85,255,255),(255,255,255),
    ]
    for i, c in enumerate(base16):
        palette[i] = c
    for i in range(216):
        r = i // 36
        g = (i % 36) // 6
        b = i % 6
        # Use the actual xterm-256 color values (0, 95, 135, 175, 215, 255)
        levels = [0, 95, 135, 175, 215, 255]
        palette[16 + i] = (levels[r], levels[g], levels[b])
    for i in range(24):
        v = 8 + i * 10
        palette[232 + i] = (v, v, v)
    return palette

PALETTE = build_ansi_256_palette()

# ─── Parse ANSI from grid cell value ────────────────────────────────────────

def parse_cell(val):
    """Extract (char, color_rgb, bold, dim) from an ANSI-escaped cell string."""
    m = re.match(r'\033\[([\d;]*)m(.)', val)
    if not m:
        return val[0] if val else ' ', (128, 128, 128), False, False

    codes_str = m.group(1)
    char = m.group(2)
    codes = [int(c) for c in codes_str.split(';') if c]

    bold = False
    dim = False
    color = (192, 192, 192)

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

    return char, color, bold, dim


# ─── Rendering config ───────────────────────────────────────────────────────

TERM_W = 100
TERM_H = 32
CELL_W = 9
CELL_H = 17
FONT_SIZE = 15
BG_COLOR = (10, 10, 16)

# GIF settings
GIF_DURATION = 5.0    # seconds of animation
GIF_FPS = 15          # frames per second in the GIF
WARMUP = 3.0          # seconds to simulate before recording


def grid_to_image(grid, anim_def, h, w, font):
    """Convert a grid dict to a PIL Image."""
    render_h = h - 2
    img_w = TERM_W * CELL_W
    img_h = render_h * CELL_H
    img = Image.new('RGB', (img_w, img_h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Create a separate layer for glow effects
    glow_layer = Image.new('RGB', (img_w, img_h), (0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    for (row, col), val in grid.items():
        if row >= render_h or col >= w:
            continue
        char, color, bold, dim = parse_cell(val)
        x = col * CELL_W
        y = row * CELL_H

        if dim:
            # Terminals render dim at ~70% brightness, not 50%
            render_color = tuple(min(255, int(v * 0.75)) for v in color)
        elif bold:
            # Bold: boost brightness
            render_color = tuple(min(255, int(v * 1.2)) for v in color)
        else:
            render_color = color

        # Draw the character
        draw.text((x, y), char, fill=render_color, font=font)

        # Add glow for bold characters (bright stars, cores, etc.)
        if bold:
            glow_color = tuple(min(255, int(v * 0.6)) for v in color)
            glow_draw.text((x, y), char, fill=glow_color, font=font)
        elif not dim:
            # Even normal characters get a subtle glow
            glow_color = tuple(min(255, int(v * 0.25)) for v in color)
            glow_draw.text((x, y), char, fill=glow_color, font=font)

    # Blur the glow layer and composite
    glow_blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=3))
    img = Image.composite(
        Image.blend(img, glow_blurred, 0.7),
        img,
        glow_blurred.convert('L')
    )

    # Re-draw characters on top of the glow (glow is behind)
    draw = ImageDraw.Draw(img)
    for (row, col), val in grid.items():
        if row >= render_h or col >= w:
            continue
        char, color, bold, dim = parse_cell(val)
        x = col * CELL_W
        y = row * CELL_H

        if dim:
            render_color = tuple(min(255, int(v * 0.75)) for v in color)
        elif bold:
            render_color = tuple(min(255, int(v * 1.2)) for v in color)
        else:
            render_color = color

        draw.text((x, y), char, fill=render_color, font=font)

    # Label bottom-right
    c0 = PALETTE.get(anim_def['colors'][0], (128, 128, 128))
    label = f"  {anim_def['name']}  "
    label_color = tuple(min(255, int(v * 0.9)) for v in c0)
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
                           radius=4, fill=(18, 18, 26))
    draw.text((lx, ly), label, fill=label_color, font=label_font)

    return img


def render_gif(anim_def, output_path):
    """Render an animated GIF of the given animation."""
    random.seed(42)

    anim_cls = mod.ANIM_CLASSES[anim_def['class']]
    anim = anim_cls(anim_def['colors'], None, anim_def['name'], activity=None)

    h, w = TERM_H, TERM_W
    sim_dt = 1.0 / 30
    gif_dt = 1.0 / GIF_FPS

    try:
        font = ImageFont.truetype('Menlo', FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()

    # Warmup
    warmup_steps = int(WARMUP / sim_dt)
    for step in range(warmup_steps):
        anim.start_time = 0.0
        anim.t = sim_dt * (step + 1)
        anim._regenerate(h, w)
        grid = {}
        anim._render_content(h, w, grid)

    # Record GIF frames
    frames = []
    total_gif_frames = int(GIF_DURATION * GIF_FPS)
    sim_steps_per_gif_frame = max(1, int(gif_dt / sim_dt))

    t = WARMUP
    for frame_i in range(total_gif_frames):
        for _ in range(sim_steps_per_gif_frame):
            t += sim_dt
            anim.start_time = 0.0
            anim.t = t
            anim._regenerate(h, w)
            grid = {}
            anim._render_content(h, w, grid)

        img = grid_to_image(grid, anim_def, h, w, font)
        # 256 colors — full GIF palette, much better quality
        img = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
        frames.append(img)

        if (frame_i + 1) % 10 == 0:
            print(f"    frame {frame_i + 1}/{total_gif_frames}")

    # Save GIF
    frame_duration_ms = int(1000 / GIF_FPS)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=frame_duration_ms,
        loop=0,
        optimize=True,
    )

    size_kb = os.path.getsize(output_path) / 1024
    print(f"  Saved {output_path} ({size_kb:.0f} KB, {len(frames)} frames)")


def main():
    out_dir = os.path.join(os.path.dirname(__file__), 'assets')
    os.makedirs(out_dir, exist_ok=True)

    for anim_def in mod.ANIMATIONS:
        slug = anim_def['name'].lower().replace(' ', '-')
        path = os.path.join(out_dir, f'{slug}.gif')
        print(f"  Rendering {anim_def['name']}...")
        render_gif(anim_def, path)

    print("\nAll GIFs rendered.")


if __name__ == '__main__':
    main()
