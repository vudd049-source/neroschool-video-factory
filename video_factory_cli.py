import os
import sys
import random
import gc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.config import CHANNELS, FORMATS, OUTPUT_DIR, READY_DIR, MUSIC_DIR, AI_IMAGE_CACHE, CACHE_DIR
from modules.logger import info, warn, error, ok, logger
from modules.script_adapter import get_script
from modules.script_splitter import build_frames
from modules.image_generator import generate_images_for_frames
from modules.tts_engine import synthesize_per_frame, get_audio_duration, synthesize
from modules.video_editor import create_video
from modules.media_finder import get_background_video, get_music_for_channel


def _split_frames_into_chunks(frames, durations, max_chunk=3.5):
    new_frames, new_durations = [], []
    for frame, dur in zip(frames, durations):
        if dur <= max_chunk:
            new_frames.append(frame)
            new_durations.append(dur)
            continue
        n = max(2, round(dur / max_chunk))
        chunk_dur = dur / n
        for _ in range(n):
            c = dict(frame)
            new_frames.append(c)
            new_durations.append(chunk_dur)
    return new_frames, new_durations


def render_one_video(channel_id=1, format_code=None, platform="tiktok", topic=None):
    channel = CHANNELS.get(channel_id)
    if not channel:
        error("Канал %d не найден", channel_id)
        return None

    channel_name = channel["name"]
    formats = channel.get("formats", ["A"])
    if not format_code:
        format_code = random.choice(formats)
    if format_code not in FORMATS:
        error("Формат %s не найден", format_code)
        return None

    fmt = FORMATS[format_code]
    video_seed = random.randint(1000, 999999)
    voice = channel.get("voice", "ermil")
    tts_speed = channel.get("tts_speed", 1.0)

    ok("=" * 50)
    ok("Канал: %s | Формат: %s (%s)", channel["title"], format_code, fmt["name"])
    ok("Тема: %s", topic or "случайная")
    ok("Seed: %d", video_seed)

    script = get_script(topic=topic, format_code=format_code)
    ok("Сценарий: %s", script.get("topic", ""))

    frames = build_frames(script, format_code)
    info("Кадров: %d", len(frames))

    ok("Синтез голоса...")
    audio_paths = synthesize_per_frame(frames, voice=voice, emotion="good", speed=tts_speed)
    if not any(audio_paths):
        warn("TTS не удался, видео будет без голоса")

    MIN_DURATIONS = {"hook": 4.0, "body": 5.0, "body_last": 5.0, "cta": 4.0}
    frame_durations = []
    full_audio_paths = [p for p in audio_paths if p]
    if full_audio_paths:
        for i, path in enumerate(audio_paths):
            ftype = frames[i].get("type", "body") if i < len(frames) else "body"
            min_dur = MIN_DURATIONS.get(ftype, 4.0)
            if path:
                fd = get_audio_duration(path)
            else:
                fd = min_dur
            frame_durations.append(max(fd, min_dur))
    else:
        frame_durations = [MIN_DURATIONS.get(f.get("type", "body"), 4.0) for f in frames]

    combined_audio = None
    if full_audio_paths:
        combined_audio = _combine_audio(audio_paths)
        total_dur = sum(frame_durations)
        _pad_audio_to_duration(combined_audio, total_dur)

    # Режиссёр: связные промты для оригинальных кадров
    from modules.image_generator import director_generate_prompts as _director
    orig_prompts = _director(frames, channel.get("title", ""), channel.get("description", ""), format_code, topic)
    for i, f in enumerate(frames):
        if i < len(orig_prompts) and orig_prompts[i]:
            f["director_prompt"] = orig_prompts[i]

    frames, frame_durations = _split_frames_into_chunks(frames, frame_durations, max_chunk=3.5)
    info("После разбивки: %d кадров по ~3.5с", len(frames))

    ok("AI-картинки для всех %d кадров...", len(frames))
    frames = generate_images_for_frames(frames, video_seed, channel_id, full_mode=True)

    music_path = get_music_for_channel()

    ts = __import__('datetime').datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_DIR, f"{channel_name}_{format_code}_{ts}.mp4")

    create_video(
        background_path=None,
        frames=frames,
        music_path=music_path,
        output_path=output_path,
        platform=platform,
        channel_id=channel_id,
        tts_audio_path=combined_audio,
        frame_durations=frame_durations,
    )

    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        ok("Видео готово: %s (%.1f MB)", output_path, size_mb)
        # Save to готовые_видео
        import shutil
        os.makedirs(READY_DIR, exist_ok=True)
        ready_path = os.path.join(READY_DIR, os.path.basename(output_path))
        shutil.copy2(output_path, ready_path)
        ok("Сохранено: %s", ready_path)
        return output_path
    return None


def _pad_audio_to_duration(audio_path, target_dur):
    if not audio_path or not os.path.exists(audio_path):
        return
    import wave
    try:
        with wave.open(audio_path, "rb") as w:
            params = w.getparams()
            frames = w.readframes(w.getnframes())
            rate = params.framerate
            sampwidth = params.sampwidth
            nchannels = params.nchannels
            nframes = w.getnframes()
            current_dur = nframes / rate
        if current_dur >= target_dur - 0.1:
            return
        pad_frames = int((target_dur - current_dur) * rate)
        silence = b'\x00' * (pad_frames * sampwidth * nchannels)
        with wave.open(audio_path, "wb") as w:
            w.setparams(params)
            w.writeframes(frames + silence)
    except Exception as e:
        warn("Ошибка паддинга аудио: %s", e)


def _combine_audio(audio_paths):
    import wave
    valid = [p for p in audio_paths if p and os.path.exists(p)]
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0]

    output = os.path.join(CACHE_DIR, "combined_tts.wav")
    try:
        with wave.open(valid[0], "rb") as w:
            params = w.getparams()
            all_data = w.readframes(w.getnframes())
        for p in valid[1:]:
            with wave.open(p, "rb") as w:
                all_data += w.readframes(w.getnframes())
        with wave.open(output, "wb") as w:
            w.setparams(params)
            w.writeframes(all_data)
        return output
    except Exception as e:
        warn("Ошибка склейки аудио: %s", e)
        return valid[0]


def main_menu():
    import readline
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("╔══════════════════════════════════════╗")
        print("║    NeroSchool Video Factory v1.0     ║")
        print("║  Фабрика видео об AI для детей 10-17 ║")
        print("╠══════════════════════════════════════╣")
        print("║  1. Сгенерировать 1 видео            ║")
        print("║  2. Сгенерировать 5 видео             ║")
        print("║  3. Сгенерировать 10 видео            ║")
        print("║  4. Выбрать тему                      ║")
        print("║  5. Выбрать формат                    ║")
        print("║  q. Выход                             ║")
        print("╚══════════════════════════════════════╝")
        choice = input("\nВыбор: ").strip().lower()

        if choice == "q":
            break
        elif choice == "1":
            render_one_video()
        elif choice == "2":
            for _ in range(5):
                render_one_video()
                gc.collect()
        elif choice == "3":
            for _ in range(10):
                render_one_video()
                gc.collect()
        elif choice == "4":
            topics = [
                "Как нейросети пишут музыку",
                "Что такое нейронные сети",
                "Как AI учится рисовать",
                "Как работает ChatGPT",
            ]
            for i, t in enumerate(topics, 1):
                print(f"  {i}. {t}")
            t_choice = input("Тема (1-4): ").strip()
            try:
                t_idx = int(t_choice) - 1
                if 0 <= t_idx < len(topics):
                    render_one_video(topic=topics[t_idx])
            except ValueError:
                pass
        elif choice == "5":
            for fc, fmt in FORMATS.items():
                print(f"  {fc}. {fmt['name']} ({fmt['desc']})")
            fmt_choice = input("Формат: ").strip().upper()
            if fmt_choice in FORMATS:
                render_one_video(format_code=fmt_choice)
        else:
            print("Неверный выбор")


if __name__ == "__main__":
    main_menu()
