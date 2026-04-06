"""Video clip generation from static images using Google Veo (image-to-video)."""

import os
import time
import threading
import urllib.request
from google import genai
from google.genai import types
import config


# Global rate limiter: only allow 1 Veo request at a time, with spacing
_veo_lock = threading.Lock()
_last_veo_request = 0.0
_VEO_MIN_INTERVAL = 15  # Minimum seconds between Veo requests


def generate_video_from_image(
    image_path: str,
    output_path: str,
    prompt: str = "This is an image. Generate a short video that draws this image from nothing, stroke by stroke, in a line art style. Starting from a blank white canvas, the lines and strokes appear on their own, gradually building up the complete illustration. No hands, no tools, no artist visible — just the lines emerging organically.",
    duration_seconds: int = 4,
) -> str:
    """
    Generate a short video clip from a static image using Veo.
    Includes global rate limiting to avoid 429 errors.
    Returns the output video path.
    """
    global _last_veo_request
    client = genai.Client(api_key=config.GOOGLE_API_KEY)
    img = types.Image.from_file(location=image_path)

    max_attempts = config.MAX_RETRIES + 3  # Extra retries for rate limits

    for attempt in range(1, max_attempts + 1):
        try:
            # Rate limit: wait for minimum interval between requests
            with _veo_lock:
                now = time.time()
                wait = _VEO_MIN_INTERVAL - (now - _last_veo_request)
                if wait > 0:
                    time.sleep(wait)
                _last_veo_request = time.time()

            operation = client.models.generate_videos(
                model=config.VIDEO_GEN_MODEL,
                prompt=prompt,
                image=img,
                config=types.GenerateVideosConfig(
                    aspect_ratio="16:9",
                    number_of_videos=1,
                    duration_seconds=duration_seconds,
                ),
            )

            # Poll until done
            while not operation.done:
                time.sleep(5)
                operation = client.operations.get(operation)

            if operation.result and operation.result.generated_videos:
                vid = operation.result.generated_videos[0]
                uri = vid.video.uri + "&key=" + config.GOOGLE_API_KEY
                urllib.request.urlretrieve(uri, output_path)
                print(f"  [VideoGen] Saved: {output_path}")
                return output_path

            raise RuntimeError("No video in Veo response")

        except Exception as e:
            is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
            if is_rate_limit and attempt < max_attempts:
                backoff = min(30 * attempt, 120)
                print(f"  [VideoGen] Rate limited, waiting {backoff}s...")
                time.sleep(backoff)
                continue
            print(f"  [VideoGen] Attempt {attempt} failed: {e}")
            if attempt == max_attempts:
                raise

    return output_path
