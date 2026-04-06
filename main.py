"""
Video Generator Pipeline
========================
Input: An idea or topic
Output: A complete video with AI-generated script, slides, and narration

Pipeline:
  Step 1: Idea → Script (Claude Opus)
  Step 2: Script → Indexed sentences
  Step 3: Sentences → PPT structure JSON (Claude Sonnet)
  Step 4: TTS text cleaning (Claude Haiku)
  Step 5: Parallel slide processing:
          - Image prompt (Claude) → Image (Nano Banana Pro) × 2 per slide
          - Image → Video clip (Veo drawing animation)
          - TTS audio (Fish Audio)
          - Clips + Audio → Slide video (ffmpeg)
  Step 6: Verify assets
  Step 7: Merge all slide videos → Final video (ffmpeg)
  Step 8: Generate SRT subtitles (faster-whisper)
  Step 9: Burn subtitles into final video (ffmpeg)
"""

import os
import sys
import json
import time
import concurrent.futures

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from agents.script_writer import generate_script, split_sentences
from agents.ppt_structure import (
    generate_ppt_structure,
    reconstruct_with_text,
    validate_structure_indices,
)
from agents.image_prompt import generate_image_prompt
from agents.tts_cleaner import clean_for_tts
from tools.image_generator import generate_image
from tools.tts_engine import synthesize_slide_audio
from tools.video_composer import compose_slide_video, merge_videos, extract_full_audio
from tools.subtitle_generator import generate_srt, burn_subtitles


def ensure_dirs():
    """Create all output directories."""
    for d in [config.OUTPUT_DIR, config.DRAFT_DIR, config.SLIDES_DIR,
              config.AUDIO_DIR, config.VIDEO_DIR]:
        os.makedirs(d, exist_ok=True)


def save_json(data, filename):
    """Save data as JSON to the draft directory."""
    path = os.path.join(config.DRAFT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def save_text(text, filename):
    """Save text to the draft directory."""
    path = os.path.join(config.DRAFT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def process_single_slide(slide: dict, cleaned_map: dict) -> dict:
    """
    Process a single slide:
      1. Generate diverse image prompts (variant directives + previous prompt context)
      2. Generate images
      3. Synthesize TTS audio
      4. Compose slide video (Ken Burns + cross-fade + audio)
    """
    idx = slide["index"]
    num_images = config.IMAGES_PER_SLIDE
    result = {"index": idx, "images": [], "audio": None, "video": None}

    # --- 1. Generate images with diverse prompts ---
    image_paths = []
    previous_prompts = []
    for img_num in range(num_images):
        print(f"\n  [Slide {idx}] Generating image prompt ({img_num + 1}/{num_images})...")
        img_prompt = generate_image_prompt(
            slide,
            variant=img_num,
            total_variants=num_images,
            previous_prompts=previous_prompts if previous_prompts else None,
        )
        previous_prompts.append(img_prompt)

        print(f"  [Slide {idx}] Generating image ({img_num + 1}/{num_images})...")
        img_path = os.path.join(config.SLIDES_DIR, f"slide_{idx:03d}_{img_num}.png")
        generate_image(img_prompt, img_path)
        image_paths.append(img_path)
    result["images"] = image_paths

    # --- 2. Get TTS text and generate audio ---
    start, end = slide["voice_over_narrative"]
    tts_parts = []
    for i in range(start, end + 1):
        tts_parts.append(cleaned_map.get(i, ""))
    tts_text = "".join(tts_parts)

    print(f"  [Slide {idx}] Synthesizing audio...")
    audio_path = synthesize_slide_audio(idx, tts_text, config.AUDIO_DIR)
    result["audio"] = audio_path

    # --- 3. Compose slide video (Ken Burns + cross-fade + audio) ---
    print(f"  [Slide {idx}] Composing video...")
    video_path = os.path.join(config.VIDEO_DIR, f"slide_{idx:03d}.mp4")
    compose_slide_video(image_paths, audio_path, video_path)
    result["video"] = video_path

    return result


def run_pipeline(idea: str, skip_script: bool = False, script_path: str = None, resume: bool = False):
    """
    Run the full video generation pipeline.

    Args:
        idea: The topic or idea for the video.
        skip_script: If True, read script from script_path instead of generating.
        script_path: Path to an existing script file (used when skip_script=True).
        resume: If True, load cached drafts and skip Steps 1-4.
    """
    ensure_dirs()
    start_time = time.time()

    if resume:
        # Load cached data from previous run
        print("\n[Resume] Loading cached data from previous run...")
        with open(os.path.join(config.DRAFT_DIR, "script.md"), "r", encoding="utf-8") as f:
            full_text = f.read()
        lines = full_text.split("\n", 1)
        title = lines[0].strip()
        body = lines[1].strip() if len(lines) > 1 else full_text
        script = {"title": title, "body": body, "full_text": full_text}

        with open(os.path.join(config.DRAFT_DIR, "sentences.json"), "r", encoding="utf-8") as f:
            sentences = json.load(f)

        with open(os.path.join(config.DRAFT_DIR, "ppt_structure_full.json"), "r", encoding="utf-8") as f:
            structure_with_text = json.load(f)

        with open(os.path.join(config.DRAFT_DIR, "ppt_structure.json"), "r", encoding="utf-8") as f:
            structure = json.load(f)

        with open(os.path.join(config.DRAFT_DIR, "tts_cleaned.json"), "r", encoding="utf-8") as f:
            cleaned = json.load(f)

        cleaned_map = {}
        for item in cleaned:
            cleaned_map[item["index"]] = item["cleaned_text"]

        print(f"  Title: {script['title']}")
        print(f"  Sentences: {len(sentences)}, Slides: {len(structure)}")
    else:
        # =====================================================
        # STEP 1: Script Generation
        # =====================================================
        if skip_script and script_path:
            print("\n[Step 1] Loading existing script...")
            with open(script_path, "r", encoding="utf-8") as f:
                full_text = f.read()
            lines = full_text.split("\n", 1)
            title = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else full_text
            script = {"title": title, "body": body, "full_text": full_text}
        else:
            print("\n[Step 1] Generating script from idea...")
            script = generate_script(idea)

        save_text(script["full_text"], "script.md")
        print(f"  Title: {script['title']}")
        print(f"  Length: {len(script['body'])} characters")

        # =====================================================
        # STEP 2: Split into indexed sentences
        # =====================================================
        print("\n[Step 2] Splitting script into sentences...")
        sentences = split_sentences(script["body"])
        save_json(sentences, "sentences.json")
        print(f"  Total sentences: {len(sentences)}")

        # =====================================================
        # STEP 3: Generate PPT structure
        # =====================================================
        print("\n[Step 3] Designing PPT structure...")
        structure = generate_ppt_structure(sentences)
        save_json(structure, "ppt_structure.json")

        # Reconstruct with actual text
        structure_with_text = reconstruct_with_text(structure, sentences)
        save_json(structure_with_text, "ppt_structure_full.json")
        print(f"  Slides: {len(structure)}")

        # =====================================================
        # STEP 4: TTS text cleaning
        # =====================================================
        print("\n[Step 4] Cleaning text for TTS...")
        cleaned = clean_for_tts(sentences)
        save_json(cleaned, "tts_cleaned.json")

        # Build lookup: index → cleaned_text
        cleaned_map = {}
        for item in cleaned:
            cleaned_map[item["index"]] = item["cleaned_text"]

    # =====================================================
    # STEP 5: Parallel slide processing (image + audio + video)
    # =====================================================
    print(f"\n[Step 5] Processing {len(structure_with_text)} slides in parallel...")

    slide_results = []
    max_workers = min(4, len(structure_with_text))

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_slide = {
            executor.submit(process_single_slide, slide, cleaned_map): slide
            for slide in structure_with_text
        }
        for future in concurrent.futures.as_completed(future_to_slide):
            slide = future_to_slide[future]
            try:
                result = future.result()
                slide_results.append(result)
                print(f"  [Slide {result['index']}] ✓ Complete")
            except Exception as e:
                print(f"  [Slide {slide['index']}] ✗ Failed: {e}")
                slide_results.append({
                    "index": slide["index"],
                    "image": None, "audio": None, "video": None,
                    "error": str(e),
                })

    # Sort by index
    slide_results.sort(key=lambda x: x["index"])
    save_json(slide_results, "slide_results.json")

    # =====================================================
    # STEP 6: Verify assets
    # =====================================================
    print("\n[Step 6] Verifying assets...")
    failed_slides = [r for r in slide_results if r.get("video") is None]
    if failed_slides:
        print(f"  Warning: {len(failed_slides)} slides failed: {[r['index'] for r in failed_slides]}")

    successful_videos = [r["video"] for r in slide_results if r.get("video")]

    if not successful_videos:
        print("  ERROR: No videos generated. Aborting.")
        return

    # =====================================================
    # STEP 7: Merge all slide videos
    # =====================================================
    print(f"\n[Step 7] Merging {len(successful_videos)} video clips...")
    final_video_path = os.path.join(config.OUTPUT_DIR, "final_video.mp4")
    merge_videos(successful_videos, final_video_path)

    # Extract full audio
    final_audio_path = os.path.join(config.OUTPUT_DIR, "final_audio.mp3")
    extract_full_audio(final_video_path, final_audio_path)

    # =====================================================
    # STEP 8: Generate subtitles (SRT) from audio
    # =====================================================
    print("\n[Step 8] Generating subtitles from audio...")
    srt_path = os.path.join(config.OUTPUT_DIR, "subtitles.srt")
    generate_srt(final_audio_path, srt_path)

    # =====================================================
    # STEP 9: Burn subtitles into video
    # =====================================================
    print("\n[Step 9] Burning subtitles into video...")
    final_video_with_subs = os.path.join(config.OUTPUT_DIR, "final_video_subtitled.mp4")
    burn_subtitles(final_video_path, srt_path, final_video_with_subs)

    # =====================================================
    # Done
    # =====================================================
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print("\n" + "=" * 60)
    print("Pipeline Complete!")
    print("=" * 60)
    print(f"  Title:       {script['title']}")
    print(f"  Slides:      {len(structure)}")
    print(f"  Sentences:   {len(sentences)}")
    print(f"  Duration:    {minutes}m {seconds}s")
    print(f"  Final Video: {final_video_with_subs}")
    print(f"  No-Sub Video:{final_video_path}")
    print(f"  Final Audio: {final_audio_path}")
    print(f"  Subtitles:   {srt_path}")
    print(f"  Script:      {os.path.join(config.DRAFT_DIR, 'script.md')}")
    print("=" * 60)

    return {
        "title": script["title"],
        "video": final_video_with_subs,
        "video_no_subs": final_video_path,
        "audio": final_audio_path,
        "subtitles": srt_path,
        "slides": len(structure),
        "sentences": len(sentences),
        "elapsed_seconds": elapsed,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python main.py \"your idea or topic here\"")
        print("  python main.py --script path/to/script.md")
        print("  python main.py --resume  (re-run from cached drafts, skip Steps 1-4)")
        sys.exit(1)

    if sys.argv[1] == "--subtitle":
        # Only run subtitle steps on existing final video
        final_video_path = os.path.join(config.OUTPUT_DIR, "final_video.mp4")
        final_audio_path = os.path.join(config.OUTPUT_DIR, "final_audio.mp3")
        if not os.path.exists(final_video_path) or not os.path.exists(final_audio_path):
            print("Error: final_video.mp4 or final_audio.mp3 not found in output/")
            sys.exit(1)
        print("\n[Subtitle Only] Generating subtitles from existing video...")
        srt_path = os.path.join(config.OUTPUT_DIR, "subtitles.srt")
        generate_srt(final_audio_path, srt_path)
        print("\n[Subtitle Only] Burning subtitles into video...")
        final_video_with_subs = os.path.join(config.OUTPUT_DIR, "final_video_subtitled.mp4")
        burn_subtitles(final_video_path, srt_path, final_video_with_subs)
        print(f"\nDone! → {final_video_with_subs}")
    elif sys.argv[1] == "--resume":
        run_pipeline(idea="", resume=True)
    elif sys.argv[1] == "--script":
        # Use existing script
        if len(sys.argv) < 3:
            print("Error: --script requires a file path")
            sys.exit(1)
        run_pipeline(idea="", skip_script=True, script_path=sys.argv[2])
    else:
        # Generate from idea
        idea = " ".join(sys.argv[1:])
        run_pipeline(idea=idea)
