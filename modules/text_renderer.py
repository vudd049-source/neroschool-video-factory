import os
import sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.logger import debug

FONT_CACHE = {}


def _get_font(font_path, fontsize):
    key = (font_path, fontsize)
    if key not in FONT_CACHE:
        FONT_CACHE[key] = ImageFont.truetype(font_path, fontsize)
    return FONT_CACHE[key]


def _wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        bb = draw.textbbox((0, 0), test_line, font=font)
        w = bb[2] - bb[0]
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


def _draw_rounded_rect(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def render_text_to_png(text, font_path, fontsize=64, text_color="#FFFFFF",
                       stroke_color="#6C2BD9", stroke_width=3, max_width=960,
                       bg_box=True, bg_color=(20, 10, 40), bg_alpha=0.55,
                       padding=24, padding_bottom=24, line_spacing=4,
                       temp_dir=None, bg_radius=20, text_alpha=1.0,
                       effects=None, max_lines=None, shadow_enabled=True,
                       align="left"):
    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)

    import hashlib
    cache_key = hashlib.md5(f"{text}{font_path}{fontsize}{text_color}{max_width}{align}".encode()).hexdigest()[:16]
    cached = os.path.join(temp_dir, f"txt_{cache_key}.png") if temp_dir else None
    if cached and os.path.exists(cached):
        return cached

    font = _get_font(font_path, fontsize)
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    lines = _wrap_text(text, font, max_width, dummy_draw)

    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]

    line_heights = []
    total_h = 0
    for line in lines:
        bb = dummy_draw.textbbox((0, 0), line, font=font)
        lh = bb[3] - bb[1]
        line_heights.append(lh)
        total_h += lh + line_spacing
    total_h -= line_spacing

    box_pad_top = padding
    box_pad_bottom = padding_bottom
    box_w = max_width + padding * 2
    box_h = total_h + box_pad_top + box_pad_bottom

    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if bg_box:
        bg_rgba = bg_color + (int(255 * bg_alpha),)
        _draw_rounded_rect(draw, (0, 0, box_w, box_h), bg_radius, bg_rgba)

    y = box_pad_top
    for i, line in enumerate(lines):
        lh = line_heights[i]
        if align == "center":
            bb = dummy_draw.textbbox((0, 0), line, font=font)
            line_w = bb[2] - bb[0]
            x = (box_w - line_w) // 2
        else:
            x = padding
        text_rgba = _hex_to_rgba(text_color, text_alpha)
        if shadow_enabled and not bg_box:
            shadow_rgba = (0, 0, 0, int(160 * text_alpha))
            draw.text((x + 3, y + 3), line, font=font, fill=shadow_rgba)
        if stroke_width > 0:
            stroke_rgba = _hex_to_rgba(stroke_color, text_alpha)
            draw.text((x, y), line, font=font, fill=text_rgba,
                      stroke_width=stroke_width, stroke_fill=stroke_rgba)
        else:
            draw.text((x, y), line, font=font, fill=text_rgba)
        y += lh + line_spacing

    if cached:
        img.save(cached)
    return cached


def _hex_to_rgba(hex_color, alpha=1.0):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return (r, g, b, int(255 * alpha))
