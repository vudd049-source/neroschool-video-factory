import os
import sys
import gc
import warnings
import subprocess
import json
import random
import numpy as np
from PIL import Image as PIL_Image, ImageFilter

warnings.filterwarnings("ignore", category=UserWarning)

try:
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip, ColorClip, concatenate_videoclips
except ImportError:
    from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip, ColorClip
    from moviepy.video.compositing.concatenate import concatenate_videoclips

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.config import CHANNEL_VISUALS, CHANNELS, VIDEO_FPS, VIDEO_RESOLUTION
from modules.text_renderer import render_text_to_png
from modules.logger import info, warn, error, ok


def get_font_for_channel(channel_id):
    channel = CHANNELS.get(channel_id)
    if not channel:
        return None, None
    font_name = channel.get("font", "Nunito-Bold.ttf")
    font_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
    font_path = os.path.join(font_dir, font_name)
    if os.path.exists(font_path):
        return font_path, font_name
    return "C:/Windows/Fonts/impact.ttf", "impact.ttf"


def _render_ken_burns_video(image_path, duration, output_path, vw=1080, vh=1920, seed=0):
    """Pre-render AI image with Ken Burns zoompan + directional pan via ffmpeg."""
    import random
    rng = random.Random(seed)
    img = PIL_Image.open(image_path)
    iw, ih = img.size
    img.close()
    scale = max(vw / iw, vh / ih)
    new_w, new_h = int(iw * scale), int(ih * scale)
    crop_x = (new_w - vw) // 2
    crop_y = (new_h - vh) // 2
    fps = VIDEO_FPS
    n_frames = max(1, int(duration * fps))
    zoom_end = 1.18
    zoom_step = (zoom_end - 1.0) / n_frames
    pan_range = 0.06
    dx = rng.uniform(-pan_range, pan_range)
    dy = rng.uniform(-pan_range, pan_range)
    x_expr = f'iw/2 + iw*{dx}*on/{n_frames}'
    y_expr = f'ih/2 + ih*{dy}*on/{n_frames}'
    cmd = [
        'ffmpeg', '-y',
        '-i', image_path,
        '-vf', (
            f'scale={new_w}:{new_h},crop={vw}:{vh}:{crop_x}:{crop_y},'
            f'zoompan=z=\'if(eq(on,1),1,min(zoom+{zoom_step},{zoom_end}))\':'
            f'd={n_frames}:s={vw}x{vh}:fps={fps}:'
            f'x=\'{x_expr}\':y=\'{y_expr}\''
        ),
        '-c:v', 'libx264', '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
    subprocess.run(cmd, capture_output=True, timeout=60)


def overlay_audio(video_path, audio_path, output_path, music_path=None, music_volume=0.15):
    if not audio_path or not os.path.exists(audio_path):
        return False
    try:
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                           '-of', 'json', video_path], capture_output=True, text=True)
        info_data = json.loads(r.stdout)
        video_duration = float(info_data['format']['duration'])

        cmd = ['ffmpeg', '-y', '-i', video_path]
        if music_path and os.path.exists(music_path):
            cmd += ['-stream_loop', '-1', '-i', music_path, '-i', audio_path]
            filter = (
                f'[2:a]volume=1.0[a_voice];'
                f'[1:a]volume={music_volume}[a_music];'
                f'[a_voice][a_music]amix=inputs=2:duration=first[audio]'
            )
            cmd += ['-filter_complex', filter, '-map', '0:v:0', '-map', '[audio]']
        else:
            cmd += ['-i', audio_path, '-map', '0:v:0', '-map', '1:a:0']
        cmd += ['-c:v', 'copy', '-c:a', 'aac', '-t', str(video_duration), output_path]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            warn("ffmpeg overlay error: %s", result.stderr[:200])
            return False
        return True
    except Exception as e:
        warn("Ошибка наложения аудио: %s", e)
        return False


def _append_color_clip(clip_list, duration, vw, vh):
    c = ColorClip(size=(vw, vh), color=(20, 10, 40)).set_duration(duration)
    clip_list.append(c)

def create_video(background_path, frames, music_path, output_path,
                 platform='tiktok', channel_id=1, tts_audio_path=None,
                 frame_durations=None):
    ok("Монтаж видео...")

    channel_cfg = CHANNELS.get(channel_id, CHANNELS[1])
    vis = CHANNEL_VISUALS.get(channel_id, CHANNEL_VISUALS[1])

    # Random font from rotation
    from modules.config import FONT_ROTATION, FONTS_DIR
    font_name = random.choice(FONT_ROTATION) if FONT_ROTATION else channel_cfg.get("font", "Montserrat-Bold.ttf")
    font_path = os.path.join(FONTS_DIR, font_name)
    if not os.path.exists(font_path):
        font_path, font_name = get_font_for_channel(channel_id)

    sw = vis["stroke_width"]
    text_color = vis["text_color"]
    stroke_color = vis["stroke_color"]
    text_alpha = vis.get("text_alpha", 0.9)
    bg_box = vis.get("bg_box", False)
    bg_color = vis.get("bg_color", (20, 10, 40))
    bg_alpha = vis.get("bg_alpha", 0.55)
    bg_radius = vis.get("bg_radius", 20)
    padding = vis.get("padding", 24)
    padding_bottom = vis.get("padding_bottom", 24)
    line_spacing = vis.get("line_spacing", 20)
    text_y_offset = vis.get("text_y_offset", 0)

    n_frames = len(frames)

    if frame_durations:
        total_duration = sum(frame_durations)
        ok("Длительность: %.1f сек, кадров: %d", total_duration, n_frames)
        for idx, (f, d) in enumerate(zip(frames, frame_durations)):
            ft = f.get("type", "?")
            txt = f.get("text", "")[:30].replace('\n', ' ')
            has_img = "🖼" if f.get("image_path") else "  "
            ok("  %s кадр %d [%s]: %.1fс — %s", has_img, idx + 1, ft, d, txt)
    else:
        total_duration = max(15, n_frames * 4)

    temp_text_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "cache", "text_pngs")
    os.makedirs(temp_text_dir, exist_ok=True)

    vw, vh = VIDEO_RESOLUTION
    background_clips = []
    text_clips = []

    for i, frame in enumerate(frames):
        if i > 0 and i % 10 == 0:
            gc.collect()

        text = frame.get("text", "")
        text = text.replace('*', '').replace('_', '').replace('(', '').replace(')', '')
        text = text.replace('[', ']').replace('"', '').replace("'", '')
        text = text.replace('«', '').replace('»', '').replace('\n', ' ').replace('\r', ' ')

        if frame_durations:
            start = sum(frame_durations[:i])
            dur = frame_durations[i]
        else:
            start = 0
            dur = total_duration // n_frames

        ftype = frame.get("type", "body")
        image_path = frame.get("image_path")

        margin = int(vw * 0.08)
        mw = vw - margin * 2
        if ftype == "hook":
            fs = 88
        elif ftype == "cta":
            fs = 80
        else:
            total_chars = len(text)
            if total_chars > 200:
                fs = 54
            elif total_chars > 100:
                fs = 62
            else:
                fs = 72

        if image_path and os.path.exists(image_path):
            try:
                ken_cache = os.path.join(os.path.dirname(temp_text_dir), "ken_burns")
                os.makedirs(ken_cache, exist_ok=True)
                fname = os.path.splitext(os.path.basename(image_path))[0]
                ken_path = os.path.join(ken_cache, f"kb_{fname}_{i}.mp4")
                if not os.path.exists(ken_path):
                    _render_ken_burns_video(image_path, dur, ken_path, vw, vh, seed=i)
                bg_clip = VideoFileClip(ken_path).without_audio()
                background_clips.append(bg_clip)
                ok("  AI-фон [%d]: %s (zoompan 1.0→1.18 + pan)", i + 1, fname)
            except Exception as e:
                warn("Ошибка AI-фона: %s", e)
                _append_color_clip(background_clips, dur, vw, vh)
        else:
            _append_color_clip(background_clips, dur, vw, vh)
            ok("  Цвет-фон [%d]: %.1fс (нет AI-картинки)", i + 1, dur)

        png_path = render_text_to_png(
            text=text, font_path=font_path, fontsize=fs,
            text_color=text_color, stroke_color=stroke_color,
            stroke_width=sw, max_width=mw,
            bg_box=bg_box, bg_color=bg_color, bg_alpha=bg_alpha,
            padding=padding, padding_bottom=padding_bottom, line_spacing=line_spacing,
            temp_dir=temp_text_dir, bg_radius=bg_radius, text_alpha=text_alpha,
            shadow_enabled=True,
            align="center" if ftype in ("hook", "cta") else "left",
        )

        txt_clip = (ImageClip(png_path, transparent=True)
            .set_duration(dur).set_start(start))
        try:
            pe = PIL_Image.open(png_path)
            ph = pe.size[1]
            pe.close()
            py = max(60, (vh - ph) // 2 + text_y_offset)
        except Exception:
            py = vh // 2
        txt_clip = txt_clip.set_position(('center', py))
        text_clips.append(txt_clip)

    bg_concatenated = concatenate_videoclips(background_clips).resize(VIDEO_RESOLUTION)
    final = CompositeVideoClip([bg_concatenated] + text_clips, size=VIDEO_RESOLUTION)

    no_audio_path = output_path.replace('.mp4', '_noaudio.mp4')
    has_tts = tts_audio_path and os.path.exists(tts_audio_path)
    music_for_ffmpeg = music_path if music_path and os.path.exists(music_path) else None

    gc.collect()

    if has_tts or music_for_ffmpeg:
        ok("Рендер без звука...")
        final.write_videofile(
            no_audio_path,
            fps=VIDEO_FPS,
            codec='libx264',
            audio_codec=None,
            preset='ultrafast',
            threads=4,
            logger=None,
        )
        gc.collect()
        if has_tts:
            ok("Наложение голоса...")
            if not overlay_audio(no_audio_path, tts_audio_path, output_path, music_path=music_for_ffmpeg):
                import shutil
                shutil.copy2(no_audio_path, output_path)
        elif music_for_ffmpeg:
            ok("Добавление музыки...")
            subprocess.run([
                'ffmpeg', '-y',
                '-i', no_audio_path,
                '-stream_loop', '-1', '-i', music_for_ffmpeg,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-af', f'atrim=0:{total_duration}',
                '-shortest',
                output_path
            ], capture_output=True)
        try:
            os.remove(no_audio_path)
        except Exception:
            pass
    else:
        ok("Рендер (без звука)...")
        final.write_videofile(
            output_path,
            fps=VIDEO_FPS,
            codec='libx264',
            audio_codec='aac',
            preset='ultrafast',
            threads=1,
            logger=None,
        )

    ok("Готово: %s", os.path.basename(output_path))

    for clip in background_clips + text_clips:
        try:
            clip.close()
        except Exception:
            pass
    try:
        bg_concatenated.close()
    except Exception:
        pass
    try:
        final.close()
    except Exception:
        pass
    gc.collect()
