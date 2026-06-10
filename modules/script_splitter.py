import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.logger import info


def build_frames(script, format_code="A"):
    frames = []

    hook_frame = {
        "type": "hook",
        "text": script.get("hook_text", ""),
        "voice_text": script.get("hook_voice_text", ""),
    }
    frames.append(hook_frame)

    body_texts = script.get("body_text", "").split("|||")
    body_voices = script.get("body_voice_text", "").split("|||")

    max_body = max(len(body_texts), len(body_voices))
    for i in range(max_body):
        bt = body_texts[i].strip() if i < len(body_texts) else ""
        bv = body_voices[i].strip() if i < len(body_voices) else bt
        body_frame = {
            "type": "body" if i < max_body - 1 else "body_last",
            "text": bt,
            "voice_text": bv,
        }
        frames.append(body_frame)

    cta_frame = {
        "type": "cta",
        "text": script.get("cta_text", ""),
        "voice_text": script.get("cta_voice_text", ""),
    }
    frames.append(cta_frame)

    info("Собрано кадров: %d (hook=%s, body=%d, cta=%s)",
         len(frames),
         "✓" if frames[0].get("text") else "✗",
         max_body,
         "✓" if frames[-1].get("text") else "✗")

    return frames
