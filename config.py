import os

# === API Keys ===
# Set these as environment variables or fill in directly (not recommended for production)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
FISH_AUDIO_API_KEY = os.getenv("FISH_AUDIO_API_KEY", "")

# === Model Settings ===
SCRIPT_MODEL = "claude-opus-4-6"          # Step 1: Script generation
PPT_STRUCTURE_MODEL = "claude-sonnet-4-6"  # Step 2: PPT structure design
IMAGE_PROMPT_MODEL = "claude-sonnet-4-6"   # Step 3: Image prompt generation
TTS_CLEAN_MODEL = "claude-haiku-4-5-20251001"  # Step 4: TTS text cleaning

# === Image Generation ===
IMAGE_MODEL = "gemini-3-pro-image-preview"
IMAGE_SIZE = "1920x1080"  # 16:9 landscape for slides

# === TTS Settings ===
TTS_ENGINE = "fish_audio"  # "edge_tts" (free) or "fish_audio" (voice clone)
TTS_VOICE = "zh-CN-YunxiNeural"  # Edge TTS fallback voice
FISH_AUDIO_VOICE_ID = "402da75e86024de79a93992845076658"  # Fish Audio cloned voice

# === Video Settings ===
VIDEO_FPS = 25
IMAGES_PER_SLIDE = 3  # Number of images per slide
CROSSFADE_DURATION = 0.8  # Seconds for cross-fade transition between images
KEN_BURNS_ZOOM = 1.15  # Max zoom factor for Ken Burns effect (1.0 = no zoom)
VIDEO_RESOLUTION = (1920, 1080)
FFMPEG_PATH = "ffmpeg"  # Assumes ffmpeg is in PATH

# === Pipeline Settings ===
MAX_SLIDES = 10
MAX_RETRIES = 5
TARGET_SCRIPT_WORDS = 1250  # Target word count for script (~5 min at 250 words/min)
TARGET_LANGUAGE = "zh"  # zh or en

# === Output Paths ===
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
DRAFT_DIR = os.path.join(OUTPUT_DIR, "draft")
SLIDES_DIR = os.path.join(OUTPUT_DIR, "slides")
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")
VIDEO_DIR = os.path.join(OUTPUT_DIR, "video")
