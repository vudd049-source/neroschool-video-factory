import os
import sys
import random
import requests
import subprocess
import time
import gc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.config import PEXELS_API_KEY
from modules.logger import info, warn, error, ok, debug

KID_FRIENDLY_QUERIES = [
    "kids coding robots classroom",
    "children technology learning fun",
    "robot toy happy kids",
    "colorful animation kids education",
    "futuristic robot cartoon",
    "kids using tablet happy",
    "children science experiment",
    "rainbow technology abstract",
    "cute robot animation",
    "kids virtual reality fun",
    "colorful digital art kids",
    "happy children programming",
    "robot friend kids play",
    "bright colorful abstract motion",
    "kids learning computer",
    "fun technology background",
    "cartoon robot dancing",
    "children gaming colorful",
]


def get_background_video(query_list, output_path):
    queries = KID_FRIENDLY_QUERIES[:]
    random.shuffle(queries)

    for query in queries[:6]:
        info("Pexels: \"%s\"", query)
        if _try_pexels(query, output_path):
            return True
        time.sleep(0.3)

    warn("Pexels не дал подходящего фона. Генерация AI-изображений...")
    return False


def _try_pexels(query, output_path):
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": 10, "orientation": "portrait", "size": "large"}
    try:
        resp = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            return False
        data = resp.json()
        videos = data.get("videos", [])
        if not videos:
            return False
        video = random.choice(videos[:5])
        video_files = video.get("video_files", [])
        if not video_files:
            return False
        best = max(video_files, key=lambda f: f.get("width", 0))
        url = best.get("link")
        if not url:
            return False
        info("Скачивание ID=%s...", video.get("id"))
        for dl_attempt in range(2):
            try:
                vr = requests.get(url, stream=True, timeout=60)
                if vr.status_code == 200:
                    with open(output_path, "wb") as f:
                        for chunk in vr.iter_content(8192):
                            f.write(chunk)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        size_mb = os.path.getsize(output_path) / 1024 / 1024
                        ok("Pexels OK: %s (%.1f MB)", os.path.basename(output_path), size_mb)
                        gc.collect()
                        return True
            except Exception:
                pass
            time.sleep(1)
        return _download_with_dotnet(url, output_path)
    except Exception as e:
        warn("Pexels error: %s", e)
    return False


def _download_with_dotnet(url, output_path):
    try:
        ps_cmd = (
            '[Net.ServicePointManager]::SecurityProtocol = "Tls12,Tls13"; '
            '$wc = New-Object System.Net.WebClient; '
            '$wc.Headers.Add("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"); '
            '$wc.Headers.Add("Referer", "https://www.pexels.com/"); '
            f'try {{ $wc.DownloadFile("{url}", "{output_path}"); Write-Output "OK" }} '
            f'catch {{ Write-Output "FAIL: $_" }}'
        )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_cmd],
            capture_output=True, text=True, timeout=120
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            ok(".NET OK: %s", os.path.basename(output_path))
            gc.collect()
            return True
        warn(".NET: %s", result.stdout.strip()[:100])
    except Exception as e:
        warn(".NET: %s", e)
    return False


def get_music_for_channel():
    music_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "music")
    if not os.path.exists(music_dir):
        return None
    mp3s = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]
    return os.path.join(music_dir, random.choice(mp3s)) if mp3s else None
