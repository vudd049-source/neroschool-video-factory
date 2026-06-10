import os

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY") or ""
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") or ""
YANDEX_TTS_KEY = os.environ.get("YANDEX_TTS_KEY") or ""
POLLINATIONS_API_KEY = os.environ.get("POLLINATIONS_API_KEY") or ""
OPENROUTER_MODEL = "deepseek/deepseek-chat"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
CACHE_DIR = os.path.join(ASSETS_DIR, "cache")
AI_IMAGE_CACHE = os.path.join(CACHE_DIR, "ai_images")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
MUSIC_DIR = os.path.join(ASSETS_DIR, "music")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
READY_DIR = os.path.join(BASE_DIR, "готовые_видео")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

VIDEO_FPS = 24
VIDEO_RESOLUTION = (1080, 1920)
YANDEX_TTS_EMOTION = "good"
CHANNELS = {1: {"name": "neuro_school", "title": "Нейро Школа", "font": "Unbounded-Bold.ttf", "voice": "ermil", "formats": ["A","B","D"]}}
FORMATS = {"A": {"name":"Миф или правда","parts":3}, "B": {"name":"Как это работает","parts":4}, "D": {"name":"Топ-N","parts":4}}

for d in [ASSETS_DIR, CACHE_DIR, AI_IMAGE_CACHE, FONTS_DIR, MUSIC_DIR, OUTPUT_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)
