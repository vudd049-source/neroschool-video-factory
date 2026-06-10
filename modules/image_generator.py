import os
import sys
import hashlib
import requests
import random
import gc
import io
import base64
import json
import time
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.config import AI_IMAGE_CACHE, AI_IMAGE_STYLE_ANCHOR, AI_IMAGE_PROMPT_TEMPLATES, OPENROUTER_API_KEY, OPENROUTER_MODEL, POLLINATIONS_API_KEY
from modules.logger import info, warn, error, ok, debug

CLOUDFLARE_WORKER_URL = os.environ.get("CF_WORKER_URL") or ""
CLOUDFLARE_WORKER_KEY = os.environ.get("CF_WORKER_KEY") or ""

_PROMPT_TOPIC_MAP = {
    "нейросеть": "glowing neural network with colorful nodes",
    "ии": "artificial intelligence brain made of light",
    "ai": "digital brain with circuit patterns",
    "чат-бот": "friendly chatbot interface with floating messages",
    "чат": "conversation bubbles with AI responses",
    "промпт": "magical text prompts floating in the air",
    "алгоритм": "flowchart with glowing pathways",
    "данные": "streams of data flowing like a river",
    "бот": "robot assistant with chat interface",
    "код": "lines of colorful code on a screen",
    "программа": "software interface with colorful modules",
    "игра": "video game world with characters",
    "гайд": "step by step guide with numbered steps",
    "лайфхак": "lightbulb moment with sparks",
    "миф": "question mark made of mysteries",
    "факт": "floating fact cards with checkmarks",
    "топ": "numbered list with trophy",
}

_SCENE_CONTEXT = {
    "hook": "futuristic classroom with holographic displays, neon purple lighting",
    "body": "digital learning environment with floating screens, cyber-academic",
    "cta": "bright futuristic school corridor, warm golden accents, celebration",
}

_VISUAL_AIDS = {
    "нейросеть": "a 3D neural network model with pulsing connections",
    "ии": "a holographic brain with flowing data streams",
    "bot": "a small robot character being built from code",
    "код": "colorful code blocks floating and arranging themselves",
    "чат": "message bubbles connecting to a glowing AI core",
    "промпт": "magical prompt cards transforming into pictures",
    "алгоритм": "a visible algorithm tree with branching paths",
    "default": "a holographic diagram with animated explanations",
}


def extract_keywords(frame_text):
    text = frame_text.lower()
    for keyword, visual in _PROMPT_TOPIC_MAP.items():
        if keyword in text:
            return visual
    words = text.split()
    if len(words) > 3:
        return "digital learning concept with glowing elements"
    return "colorful technology concept"


def get_visual_aid(frame_text):
    text = frame_text.lower()
    for keyword, aid in _VISUAL_AIDS.items():
        if keyword in text and keyword != "default":
            return aid
    return _VISUAL_AIDS["default"]


def build_prompt(frame_text, frame_type, video_seed):
    keyword_visual = extract_keywords(frame_text)
    topic = keyword_visual
    scene_context = _SCENE_CONTEXT.get(frame_type, "futuristic learning environment")
    visual_aid = get_visual_aid(frame_text)

    template = AI_IMAGE_PROMPT_TEMPLATES.get(frame_type, AI_IMAGE_PROMPT_TEMPLATES["body"])
    prompt = template.format(
        topic=topic,
        scene_context=scene_context,
        visual_aid=visual_aid,
        style_anchor=AI_IMAGE_STYLE_ANCHOR,
    )
    prompt = f"{prompt}, video game concept art style, sharp focus"
    return prompt


def generate_ai_image(prompt, output_path, seed=None, max_retries=2):
    if seed is None:
        seed = random.randint(1, 9999999)

    info("Генерация AI-картинки: seed=%d", seed)

    if _try_cloudflare_worker(prompt, output_path):
        return True

    if _try_pollinations(prompt, output_path, seed):
        return True

    if _try_openrouter_gemini(prompt, output_path):
        return True

    info("Все AI-сервисы недоступны. Генерация плейсхолдера...")
    return _generate_placeholder(prompt, output_path, seed)


def _try_cloudflare_worker(prompt, output_path):
    url = CLOUDFLARE_WORKER_URL
    key = CLOUDFLARE_WORKER_KEY
    if not url:
        return False

    info("Cloudflare Worker: генерация...")
    for attempt in range(2):
        try:
            resp = requests.post(
                url.rstrip("/") + "/",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "Accept-Encoding": "zstd, gzip, deflate",
                },
                json={
                    "prompt": prompt,
                    "model": "@cf/black-forest-labs/flux-1-schnell",
                },
                timeout=120,
            )
            if resp.status_code == 200:
                raw = resp.content
                # Try to decompress zstd if needed
                try:
                    import zstandard
                    dctx = zstandard.ZstdDecompressor()
                    raw = dctx.decompress(raw)
                except (Exception, zstandard.ZstdError):
                    pass
                ct = resp.headers.get("content-type", "")
                if "image" in ct:
                    with open(output_path, "wb") as f:
                        f.write(raw)
                else:
                    data = json.loads(raw)
                    img_b64 = data.get("image", "")
                    if img_b64 and isinstance(img_b64, str) and img_b64.startswith("data:image"):
                        b64 = img_b64.split(",", 1)[1]
                        img_data = base64.b64decode(b64)
                        with open(output_path, "wb") as f:
                            f.write(img_data)
                    else:
                        raise ValueError("No image in response")
                size_kb = os.path.getsize(output_path) / 1024
                ok("Cloudflare OK: %s (%.1f KB)", os.path.basename(output_path), size_kb)
                gc.collect()
                return True
        except Exception as e:
            warn("Cloudflare Worker (попытка %d/2): %s", attempt + 1, e)
        time.sleep(2)
    return False


def _try_pollinations(prompt, output_path, seed):
    import urllib.parse
    headers = {}
    if POLLINATIONS_API_KEY:
        headers["Authorization"] = f"Bearer {POLLINATIONS_API_KEY}"

    encoded = urllib.parse.quote(prompt)

    # New API (gen.pollinations.ai) with auth - primary
    gen_url = f"https://gen.pollinations.ai/image/{encoded}?width=1080&height=1920&seed={seed}&model=flux&nologo=true"
    for attempt in range(2):
        try:
            r = requests.get(gen_url, headers=headers, timeout=60)
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and len(r.content) > 1000 and "image" in ct:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                size_kb = os.path.getsize(output_path) / 1024
                ok("Pollinations gen OK: %s (%.1f KB)", os.path.basename(output_path), size_kb)
                gc.collect()
                return True
        except Exception as e:
            debug("Pollinations gen error: %s", e)
        time.sleep(1)

    # Legacy API (image.pollinations.ai) - fallback without auth
    urls = [
        f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&seed={seed}&model=flux",
        f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&seed={seed}&model=turbo",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=60)
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and len(r.content) > 1000 and "image" in ct:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                size_kb = os.path.getsize(output_path) / 1024
                ok("Pollinations legacy OK: %s (%.1f KB)", os.path.basename(output_path), size_kb)
                gc.collect()
                return True
            if r.status_code == 402:
                break
        except Exception as e:
            debug("Pollinations legacy error: %s", e)
        time.sleep(1)
    return False


def _try_openrouter_gemini(prompt, output_path):
    if not OPENROUTER_API_KEY:
        return False

    en_prompt = _simple_transliterate(prompt)
    info("OpenRouter Gemini: запрос картинки...")

    for attempt in range(2):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-2.5-flash-image",
                    "modalities": ["image", "text"],
                    "messages": [{"role": "user", "content": f"Generate an image in vertical 9:16 format (1080x1920): {en_prompt}"}],
                    "provider": {"order": ["Google"]},

                },
                timeout=90,
            )
            data = resp.json()
            images = data.get("choices", [{}])[0].get("message", {}).get("images", [])
            if images:
                url = images[0].get("image_url", {}).get("url", "")
                if url and url.startswith("data:image"):
                    b64 = url.split(",", 1)[1]
                    img_data = base64.b64decode(b64)
                    with open(output_path, "wb") as f:
                        f.write(img_data)
                    ok("OpenRouter Gemini OK: %s (%.1f KB)", os.path.basename(output_path), len(img_data) / 1024)
                    gc.collect()
                    return True
        except Exception as e:
            warn("OpenRouter Gemini (попытка %d/2): %s", attempt + 1, e)
        time.sleep(2)
    return False


def director_generate_prompts(frames, channel_name="", channel_desc="", format_name="", topic=""):
    """LLM-режиссёр: пишет связные английские промты для каждого кадра."""
    scenes_text = ""
    for i, f in enumerate(frames):
        scenes_text += f"  [{i}] {f.get('type','?')}: {f.get('text','')}\n"

    system = (
        "You are a film director creating a visual storyboard. "
        "For each scene, write ONE detailed image prompt in English (60-100 words). "
        "All prompts must share the same visual style (colors, lighting, art direction). "
        "Make each scene visualize what is being narrated. "
        "Use cinematic terms: lighting, camera angle, mood, composition. "
        "Vertical 9:16 format (1080x1920). "
        "Return as a numbered list, one line per scene: '0: prompt'"
    )

    user = (
        f"Channel: {channel_name}\n"
        f"Format: {format_name}\n"
        f"Topic: {topic}\n\n"
        f"Script:\n{scenes_text}\n\n"
        "Generate one detailed English image prompt per scene:"
    )

    prompts = [""] * len(frames)
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "google/gemini-2.5-flash-lite",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": 4096,
                "temperature": 0.7,
            },
            timeout=60,
        )
        data = resp.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        for line in content.strip().split("\n"):
            m = re.match(r"^(\d+)[:.)]\s*(.+)", line.strip())
            if m:
                idx = int(m.group(1))
                if 0 <= idx < len(frames):
                    prompts[idx] = m.group(2).strip()
        ok("Режиссёр: промты для %d кадров", len(frames))
    except Exception as e:
        warn("Режиссёр не ответил: %s", e)

    # fallback for any missing
    for i, f in enumerate(frames):
        if not prompts[i]:
            prompts[i] = build_prompt(f.get("text", ""), f.get("type", "body"), 0)
    return prompts


def _generate_placeholder(prompt, output_path, seed):
    from PIL import Image, ImageDraw, ImageFont
    s = seed % 10000
    w, h = 1080, 1920

    img = Image.new("RGB", (w, h), (108, 92, 231))
    draw = ImageDraw.Draw(img)

    def _hsl_to_rgb(h, s, l):
        if s == 0:
            v = int(l * 255)
            return (v, v, v)
        def hue2rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        return (int(hue2rgb(p, q, h + 1/3) * 255),
                int(hue2rgb(p, q, h) * 255),
                int(hue2rgb(p, q, h - 1/3) * 255))

    stops = [
        (_hsl_to_rgb(260/360, 0.7, 0.5), 0.0),
        (_hsl_to_rgb(330/360, 0.7, 0.6), 0.5),
        (_hsl_to_rgb(185/360, 0.8, 0.5), 1.0),
    ]
    for y in range(h):
        t = y / h
        if t < 0.5:
            t2 = t / 0.5
            r = int(stops[0][0][0] * (1 - t2) + stops[1][0][0] * t2)
            g = int(stops[0][0][1] * (1 - t2) + stops[1][0][1] * t2)
            b = int(stops[0][0][2] * (1 - t2) + stops[1][0][2] * t2)
        else:
            t2 = (t - 0.5) / 0.5
            r = int(stops[1][0][0] * (1 - t2) + stops[2][0][0] * t2)
            g = int(stops[1][0][1] * (1 - t2) + stops[2][0][1] * t2)
            b = int(stops[1][0][2] * (1 - t2) + stops[2][0][2] * t2)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    for i in range(12):
        cx = (s * (i * 73 + 11)) % w
        cy = (s * (i * 97 + 37)) % h
        r2 = 30 + (s * (i * 13 + 7)) % 60
        draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], outline=(220, 220, 255, 60))

    cx, cy = w // 2, 500
    draw.rounded_rectangle([cx - 110, cy - 110, cx + 110, cy + 110], radius=32, fill=(45, 52, 54))
    draw.rounded_rectangle([cx - 76, cy - 76, cx + 76, cy + 30], radius=16, fill=(0, 210, 211))
    draw.ellipse([cx - 44, cy - 50, cx - 16, cy - 16], fill=(255, 255, 255))
    draw.ellipse([cx + 16, cy - 50, cx + 44, cy - 16], fill=(255, 255, 255))
    draw.ellipse([cx - 36, cy - 40, cx - 24, cy - 28], fill=(45, 52, 54))
    draw.ellipse([cx + 24, cy - 40, cx + 36, cy - 28], fill=(45, 52, 54))
    draw.arc([cx - 30, cy - 10, cx + 30, cy + 20], 0, 180, fill=(255, 255, 255), width=4)
    draw.line([(cx, cy - 110), (cx, cy - 150)], fill=(255, 255, 255), width=6)
    draw.ellipse([cx - 12, cy - 164, cx + 12, cy - 140], fill=(254, 202, 87))
    draw.ellipse([cx - 124, cy - 30, cx - 96, cy + 10], fill=(108, 92, 231))
    draw.ellipse([cx + 96, cy - 30, cx + 124, cy + 10], fill=(108, 92, 231))

    badge_bg = (254, 202, 87)
    draw.rounded_rectangle([cx - 110, cy + 130, cx + 110, cy + 190], radius=40, fill=badge_bg)
    try:
        ft = ImageFont.truetype("arial.ttf", 36)
        fs = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        ft = ImageFont.load_default()
        fs = ft
    draw.text((cx, cy + 160), "NeroSchool AI", font=ft, fill=(45, 52, 54), anchor="mm")

    words = prompt.split()
    lines = []
    while words:
        line = words.pop(0)
        while words:
            test = line + " " + words[0]
            bb = draw.textbbox((0, 0), test, font=fs)
            if bb[2] - bb[0] > w - 160:
                break
            line = test
            words.pop(0)
        lines.append(line)

    y_text = cy + 240
    for i, line in enumerate(lines[:6]):
        draw.text((w // 2, y_text + i * 36), line, font=fs, fill=(255, 255, 255), anchor="mm")
    if len(lines) > 6:
        draw.text((w // 2, y_text + 6 * 36), "...", font=fs, fill=(200, 200, 200), anchor="mm")

    img.save(output_path, format="PNG")
    ok("Плейсхолдер Неро: %s", os.path.basename(output_path))
    return True


def _simple_transliterate(text):
    mapping = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo','ж':'zh',
        'з':'z','и':'i','й':'y','к':'k','л':'l','м':'m','н':'n','о':'o',
        'п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'kh','ц':'ts',
        'ч':'ch','ш':'sh','щ':'shch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu',
        'я':'ya','А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'Yo',
        'Ж':'Zh','З':'Z','И':'I','Й':'Y','К':'K','Л':'L','М':'M','Н':'N',
        'О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U','Ф':'F','Х':'Kh',
        'Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Shch','Ъ':'','Ы':'Y','Ь':'','Э':'E',
        'Ю':'Yu','Я':'Ya',
    }
    return text.translate(mapping)


def generate_images_for_frames(frames, video_seed, channel_id=1, full_mode=False, channel=None, format_name="", topic=""):
    image_paths = []
    ai_positions = []

    if full_mode:
        ai_positions = list(range(len(frames)))
        info("Режим FULL: генерация AI-картинок для всех %d кадров", len(frames))
    else:
        n = len(frames)
        if n >= 4:
            ai_positions = [0, 2, n - 1]
        elif n >= 3:
            ai_positions = [0, 1, n - 1]
        else:
            ai_positions = [0]

    image_idx = 0
    for frame_idx, frame in enumerate(frames):
        if frame_idx not in ai_positions:
            frame["image_path"] = None
            continue

        prompt = frame.get("director_prompt", "")
        if not prompt:
            frame_type = frame.get("type", "body")
            frame_text = frame.get("text", "")
            prompt = build_prompt(frame_text, frame_type, video_seed)
        prompt = f"{prompt}, artistic variation {image_idx}"

        cache_path = os.path.join(AI_IMAGE_CACHE, f"ai_img_{video_seed}_{image_idx}.png")

        if os.path.exists(cache_path):
            ok("AI-картинка из кэша: %s", os.path.basename(cache_path))
            frame["image_path"] = cache_path
        else:
            image_seed = video_seed * 10 + image_idx
            if generate_ai_image(prompt, cache_path, seed=image_seed):
                frame["image_path"] = cache_path
            else:
                frame["image_path"] = None

        frame["image_prompt"] = prompt
        frame["prompt_variant"] = image_idx
        image_paths.append(frame["image_path"])
        image_idx += 1

    return frames
