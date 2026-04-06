"""TTS synthesis supporting Edge TTS (free) and Fish Audio (voice clone)."""

import asyncio
import os
import config


# === Edge TTS ===

async def _edge_synthesize(text: str, output_path: str, voice: str) -> str:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path


def edge_tts_synthesize(text: str, output_path: str) -> str:
    voice = config.TTS_VOICE
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = pool.submit(
                asyncio.run, _edge_synthesize(text, output_path, voice)
            ).result()
        return result
    except RuntimeError:
        return asyncio.run(_edge_synthesize(text, output_path, voice))


# === Fish Audio ===

def fish_audio_synthesize(text: str, output_path: str) -> str:
    from fish_audio_sdk import Session, TTSRequest

    session = Session(apikey=config.FISH_AUDIO_API_KEY)

    with open(output_path, "wb") as f:
        for chunk in session.tts(
            TTSRequest(
                reference_id=config.FISH_AUDIO_VOICE_ID,
                text=text,
                format="mp3",
            )
        ):
            f.write(chunk)

    return output_path


# === Public API ===

def synthesize_speech(text: str, output_path: str) -> str:
    """Convert text to speech using configured engine."""
    if config.TTS_ENGINE == "fish_audio":
        return fish_audio_synthesize(text, output_path)
    else:
        return edge_tts_synthesize(text, output_path)


def synthesize_slide_audio(slide_index: int, text: str, output_dir: str) -> str:
    """Synthesize audio for a single slide."""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"slide_{slide_index:03d}.mp3")
    synthesize_speech(text, output_path)
    print(f"  [TTS] Slide {slide_index}: saved {output_path}")
    return output_path
