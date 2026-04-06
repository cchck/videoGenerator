"""Subtitle generation using faster-whisper and PIL-based burn-in."""

import os
import re
import subprocess
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw, ImageFont
import config


# Chinese font path on macOS
_FONT_PATH = "/System/Library/Fonts/STHeiti Medium.ttc"
_FONT_SIZE = 42
_MARGIN_BOTTOM = 60
_OUTLINE_WIDTH = 3


def generate_srt(audio_path: str, output_path: str) -> str:
    """
    Transcribe audio and generate SRT subtitle file with timestamps.
    Returns the output SRT file path.
    """
    print("  [Subtitle] Loading Whisper model...")
    model = WhisperModel("medium", device="cpu", compute_type="int8")

    print("  [Subtitle] Transcribing audio...")
    segments, info = model.transcribe(
        audio_path,
        language="zh",
        word_timestamps=True,
        vad_filter=True,
    )

    # Build SRT content
    srt_lines = []
    index = 1

    for segment in segments:
        start = _format_time(segment.start)
        end = _format_time(segment.end)
        text = segment.text.strip()
        if text:
            srt_lines.append(f"{index}")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(text)
            srt_lines.append("")
            index += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    print(f"  [Subtitle] Generated {index - 1} subtitle segments → {output_path}")
    return output_path


def burn_subtitles(video_path: str, srt_path: str, output_path: str) -> str:
    """
    Burn SRT subtitles into video using PIL for text rendering + ffmpeg pipes.
    No libass/drawtext required — works with any ffmpeg build.
    Returns the output video path.
    """
    # Parse SRT
    subtitles = _parse_srt(srt_path)
    print(f"  [Subtitle] Parsed {len(subtitles)} subtitle segments")

    # Get video dimensions and fps
    width, height, fps, total_frames = _get_video_info(video_path)
    print(f"  [Subtitle] Video: {width}x{height} @ {fps}fps, ~{total_frames} frames")

    font = ImageFont.truetype(_FONT_PATH, _FONT_SIZE)

    # Cache: pre-render subtitle overlays (text -> RGBA image)
    overlay_cache = {}

    # Decode video → raw frames
    decode_cmd = [
        config.FFMPEG_PATH,
        "-i", video_path,
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-v", "quiet",
        "-"
    ]

    # Encode processed frames → output video (copy audio from original)
    encode_cmd = [
        config.FFMPEG_PATH,
        "-y",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-i", video_path,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "copy",
        "-v", "quiet",
        output_path,
    ]

    decoder = subprocess.Popen(decode_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    encoder = subprocess.Popen(encode_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    frame_size = width * height * 3
    frame_num = 0
    last_pct = -1

    try:
        while True:
            raw = decoder.stdout.read(frame_size)
            if len(raw) < frame_size:
                break

            t = frame_num / fps
            sub_text = _find_subtitle(subtitles, t)

            if sub_text:
                # Get or create cached overlay
                if sub_text not in overlay_cache:
                    overlay_cache[sub_text] = _render_subtitle(
                        sub_text, width, height, font
                    )
                overlay = overlay_cache[sub_text]

                # Composite subtitle onto frame
                frame_img = Image.frombytes("RGB", (width, height), raw)
                frame_img.paste(overlay, (0, 0), overlay)
                raw = frame_img.tobytes()

            encoder.stdin.write(raw)
            frame_num += 1

            # Progress every 10%
            if total_frames > 0:
                pct = (frame_num * 100) // total_frames
                if pct >= last_pct + 10:
                    last_pct = pct
                    print(f"  [Subtitle] Progress: {pct}%")
    finally:
        decoder.stdout.close()
        encoder.stdin.close()
        decoder.wait()
        encoder.wait()

    print(f"  [Subtitle] Burned subtitles → {output_path}")
    return output_path


def _render_subtitle(text: str, width: int, height: int, font: ImageFont.FreeTypeFont) -> Image.Image:
    """Render subtitle text as a transparent RGBA overlay image."""
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Measure text
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # Center horizontally, near bottom
    x = (width - tw) // 2
    y = height - th - _MARGIN_BOTTOM

    # Draw black outline
    for dx in range(-_OUTLINE_WIDTH, _OUTLINE_WIDTH + 1):
        for dy in range(-_OUTLINE_WIDTH, _OUTLINE_WIDTH + 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 255))

    # Draw white text
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    return overlay


def _parse_srt(srt_path: str) -> list:
    """Parse SRT file into list of {start, end, text} dicts (times in seconds)."""
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    subtitles = []
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            time_match = re.match(
                r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})",
                lines[1],
            )
            if time_match:
                g = [int(x) for x in time_match.groups()]
                start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
                end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
                text = " ".join(lines[2:]).strip()
                subtitles.append({"start": start, "end": end, "text": text})

    return subtitles


def _find_subtitle(subtitles: list, t: float) -> str:
    """Find subtitle text for a given timestamp. Returns None if no subtitle."""
    for sub in subtitles:
        if sub["start"] <= t <= sub["end"]:
            return sub["text"]
    return None


def _get_video_info(video_path: str) -> tuple:
    """Get video width, height, fps, and total frames."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
        "-show_entries", "format=duration",
        "-of", "json",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    import json
    info = json.loads(result.stdout)

    stream = info["streams"][0]
    width = int(stream["width"])
    height = int(stream["height"])

    # Parse fps fraction like "25/1"
    fps_parts = stream["r_frame_rate"].split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1])

    # Total frames
    duration = float(info["format"]["duration"])
    total_frames = int(duration * fps)

    return width, height, fps, total_frames


def _format_time(seconds: float) -> str:
    """Convert seconds to SRT time format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
