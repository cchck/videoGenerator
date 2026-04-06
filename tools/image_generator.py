"""Image generation using Google Nano Banana Pro (Gemini 3 Pro Image)."""

from google import genai
from google.genai import types
import config


def generate_image(prompt: str, output_path: str) -> str:
    """
    Generate an image from a text prompt using Nano Banana Pro and save it locally.
    Returns the output file path.
    """
    client = genai.Client(api_key=config.GOOGLE_API_KEY)

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = client.models.generate_content(
                model=config.IMAGE_MODEL,
                contents=f"Generate a high-quality 16:9 landscape image: {prompt}",
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            # Find the image part in the response
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    with open(output_path, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"  [Image] Saved: {output_path}")
                    return output_path

            raise RuntimeError("No image in response")

        except Exception as e:
            print(f"  [Image] Attempt {attempt} failed: {e}")
            if attempt == config.MAX_RETRIES:
                raise

    return output_path
