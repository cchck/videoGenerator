"""Video composition: images with Ken Burns + cross-fade → slide video, then merge."""

import os
import subprocess
import random
import numpy as np
from PIL import Image
import config


def get_audio_duration(audio_path: str) -> float:
    """Get duration of an audio file in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return float(result.stdout.strip())


def _ken_burns_frame(pil_img: Image.Image, progress: float,
                     zoom_start: float, zoom_end: float,
                     pan_x_start: float, pan_x_end: float,
                     pan_y_start: float, pan_y_end: float,
                     out_w: int, out_h: int) -> np.ndarray:
    """
    Apply Ken Burns (zoom + pan) to a single frame using affine transform.
    All coordinates stay in float — PIL handles sub-pixel interpolation,
    eliminating the 1-pixel jitter from integer rounding.
    """
    w, h = pil_img.size

    # Interpolate zoom and pan (smooth float values)
    zoom = zoom_start + (zoom_end - zoom_start) * progress
    pan_x = pan_x_start + (pan_x_end - pan_x_start) * progress
    pan_y = pan_y_start + (pan_y_end - pan_y_start) * progress

    # Crop region size in source pixels (float)
    crop_w = w / zoom
    crop_h = h / zoom

    # Center + pan offset (float)
    cx = w / 2.0 + pan_x * (w - crop_w) / 2.0
    cy = h / 2.0 + pan_y * (h - crop_h) / 2.0

    # Clamp center so crop stays within image bounds
    cx = max(crop_w / 2.0, min(w - crop_w / 2.0, cx))
    cy = max(crop_h / 2.0, min(h - crop_h / 2.0, cy))

    # Affine transform: maps output pixel (ox, oy) → source pixel (sx, sy)
    # sx = scale_x * ox + offset_x,  sy = scale_y * oy + offset_y
    scale_x = crop_w / out_w
    scale_y = crop_h / out_h
    offset_x = cx - crop_w / 2.0
    offset_y = cy - crop_h / 2.0

    result = pil_img.transform(
        (out_w, out_h),
        Image.AFFINE,
        (scale_x, 0, offset_x, 0, scale_y, offset_y),
        resample=Image.BICUBIC,
    )
    return np.array(result)


def _random_ken_burns_params():
    """Generate random Ken Burns parameters (zoom direction + pan)."""
    patterns = [
        # zoom in, pan right
        (1.0, config.KEN_BURNS_ZOOM,
         random.uniform(-0.3, 0.0), random.uniform(0.0, 0.3),
         random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2)),
        # zoom out, pan left
        (config.KEN_BURNS_ZOOM, 1.0,
         random.uniform(0.0, 0.3), random.uniform(-0.3, 0.0),
         random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2)),
        # zoom in, pan up
        (1.0, config.KEN_BURNS_ZOOM,
         random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2),
         random.uniform(0.0, 0.3), random.uniform(-0.3, 0.0)),
        # zoom out, pan down
        (config.KEN_BURNS_ZOOM, 1.0,
         random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2),
         random.uniform(-0.3, 0.0), random.uniform(0.0, 0.3)),
    ]
    return random.choice(patterns)


def compose_slide_video(image_paths: list, audio_path: str, output_path: str) -> str:
    """
    Compose a slide video from multiple images with Ken Burns + cross-fade transitions.
    """
    audio_duration = get_audio_duration(audio_path)
    fps = config.VIDEO_FPS
    num_images = len(image_paths)
    fade_dur = config.CROSSFADE_DURATION
    fade_frames = int(fade_dur * fps)

    # Time per image (with overlap for cross-fade)
    total_fade_time = fade_dur * max(0, num_images - 1)
    display_time = (audio_duration + total_fade_time) / num_images
    frames_per_image = int(display_time * fps)

    # Load and prepare images
    # Use first image to determine output size
    first_img = Image.open(image_paths[0]).convert("RGB")
    out_w, out_h = first_img.size
    # Ensure even dimensions
    out_w = out_w if out_w % 2 == 0 else out_w - 1
    out_h = out_h if out_h % 2 == 0 else out_h - 1
    first_img.close()

    # Upscale images slightly for Ken Burns crop room
    scale = config.KEN_BURNS_ZOOM + 0.05
    load_w, load_h = int(out_w * scale), int(out_h * scale)

    images = []
    kb_params = []
    for path in image_paths:
        img = Image.open(path).convert("RGB").resize((load_w, load_h), Image.LANCZOS)
        images.append(img)
        kb_params.append(_random_ken_burns_params())

    # Set up ffmpeg encoder
    encode_cmd = [
        config.FFMPEG_PATH, "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{out_w}x{out_h}", "-r", str(fps),
        "-i", "-",
        "-i", audio_path,
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-v", "quiet",
        output_path,
    ]

    encoder = subprocess.Popen(encode_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    total_frames = int(audio_duration * fps)
    frame_count = 0

    for img_idx in range(num_images):
        zs, ze, pxs, pxe, pys, pye = kb_params[img_idx]

        # How many frames for this image
        if img_idx < num_images - 1:
            n_frames = frames_per_image
        else:
            # Last image: fill remaining frames
            n_frames = total_frames - frame_count

        for f in range(n_frames):
            if frame_count >= total_frames:
                break

            progress = f / max(1, n_frames - 1)

            # Ken Burns on current image
            frame = _ken_burns_frame(
                images[img_idx], progress,
                zs, ze, pxs, pxe, pys, pye,
                out_w, out_h,
            )

            # Cross-fade: blend with next image during last fade_frames
            frames_until_end = n_frames - f
            if img_idx < num_images - 1 and frames_until_end <= fade_frames:
                fade_progress = 1.0 - (frames_until_end / fade_frames)
                next_zs, next_ze, next_pxs, next_pxe, next_pys, next_pye = kb_params[img_idx + 1]
                next_frame = _ken_burns_frame(
                    images[img_idx + 1], 0.0,
                    next_zs, next_ze, next_pxs, next_pxe, next_pys, next_pye,
                    out_w, out_h,
                )
                frame = (frame * (1 - fade_progress) + next_frame * fade_progress).astype(np.uint8)

            encoder.stdin.write(frame.tobytes())
            frame_count += 1

    encoder.stdin.close()
    encoder.wait()

    print(f"  [Video] Composed: {output_path} ({audio_duration:.1f}s, {num_images} images)")
    return output_path


def merge_videos(video_paths: list, output_path: str) -> str:
    """Merge multiple slide videos into a single final video."""
    list_path = output_path + ".txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")

    subprocess.run([
        config.FFMPEG_PATH, "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path,
    ], capture_output=True, check=True)
    os.remove(list_path)

    print(f"  [Video] Merged {len(video_paths)} clips → {output_path}")
    return output_path


def extract_full_audio(video_path: str, output_path: str) -> str:
    """Extract the audio track from a video file."""
    cmd = [
        config.FFMPEG_PATH, "-y",
        "-i", video_path,
        "-vn", "-acodec", "libmp3lame", "-b:a", "192k",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"  [Audio] Extracted: {output_path}")
    return output_path
