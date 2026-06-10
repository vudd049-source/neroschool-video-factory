import os
import sys
import hashlib
import requests
import subprocess
import struct
import gc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.config import YANDEX_TTS_KEY
from modules.logger import info, warn, error, ok, debug

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "cache", "tts")
os.makedirs(CACHE_DIR, exist_ok=True)


def synthesize(text, voice="ermil", emotion="good", speed=1.0, max_retries=3):
    if not text or not text.strip():
        return None

    cache_key = hashlib.md5(f"{text}:{voice}:{emotion}:{speed}".encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.wav")

    if os.path.exists(cache_path):
        debug("TTS из кэша: %s", os.path.basename(cache_path))
        return cache_path

    text_clean = _prepare_text(text)

    for attempt in range(max_retries):
        try:
            url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
            headers = {"Authorization": f"Api-Key {YANDEX_TTS_KEY}"}
            data = {
                "text": text_clean,
                "voice": voice,
                "emotion": emotion,
                "speed": str(speed),
                "format": "lpcm",
                "sampleRateHertz": 48000,
            }

            resp = requests.post(url, headers=headers, data=data, timeout=60)
            if resp.status_code == 200:
                raw_path = cache_path.replace(".wav", "_raw.raw")
                with open(raw_path, "wb") as f:
                    f.write(resp.content)

                _raw_to_wav(raw_path, cache_path)
                if os.path.exists(raw_path):
                    os.remove(raw_path)
                if os.path.exists(cache_path) and os.path.getsize(cache_path) > 100:
                    ok("TTS синтезирован: %d слов -> %s", len(text.split()), os.path.basename(cache_path))
                    return cache_path
            else:
                warn("Yandex TTS HTTP %d (попытка %d/3): %s", resp.status_code, attempt + 1, resp.text[:100])
        except requests.exceptions.Timeout:
            warn("Yandex TTS timeout (попытка %d/3)", attempt + 1)
        except Exception as e:
            warn("Yandex TTS ошибка (попытка %d/3): %s", attempt + 1, e)
        import time
        time.sleep(2)

    error("TTS не удался после %d попыток: %s", max_retries, text[:50])
    return None


def synthesize_per_frame(frames, voice="ermil", emotion="good", speed=1.0):
    audio_paths = []
    for i, frame in enumerate(frames):
        voice_text = frame.get("voice_text", frame.get("text", ""))
        path = synthesize(voice_text, voice=voice, emotion=emotion, speed=speed)
        audio_paths.append(path)
        if i == 0 and path:
            _add_silence_at_start(path, 0.5)
    return audio_paths


def _prepare_text(text):
    text = text.replace("\n", " ").replace("\r", " ")
    text = text.replace("*", "").replace("_", "").replace("|||", ". ")
    text = " ".join(text.split())
    if len(text) > 5000:
        text = text[:4997] + "..."
    return text


def _raw_to_wav(raw_path, wav_path):
    import wave
    sample_rate = 48000
    with open(raw_path, "rb") as raw:
        raw_data = raw.read()
    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(raw_data)


def _add_silence_at_start(wav_path, duration=0.5):
    import wave
    try:
        with wave.open(wav_path, "rb") as w:
            params = w.getparams()
            frames = w.readframes(w.getnframes())
        silence_frames = int(params.framerate * duration)
        silence = struct.pack(f"<{silence_frames}h", *([0] * silence_frames))
        with wave.open(wav_path, "wb") as w:
            w.setparams(params)
            w.writeframes(silence + frames)
    except Exception as e:
        debug("Не удалось добавить тишину: %s", e)


def get_audio_duration(wav_path):
    import wave
    try:
        with wave.open(wav_path, "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


def add_pauses(text, pause_duration=0.3):
    return text
