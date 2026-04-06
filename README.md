# VideoGenerator

AI-powered video generation pipeline — turn a simple idea into a complete narrated video with images, voice, and subtitles.

AI 驱动的视频生成流水线 —— 输入一个想法，自动生成带配图、配音和字幕的完整视频。

---

## Pipeline / 流水线

```
Idea → Script → PPT Structure → Images + Audio → Video + Subtitles
想法  →  文稿  →   PPT结构    →  配图 + 配音  →  视频 + 字幕
```

| Step | Description | Model |
|------|-------------|-------|
| 1 | Script generation / 生成文稿 | Claude Opus |
| 2 | Split into indexed sentences / 拆分成编号句子 | Local |
| 3 | PPT slide structure design / 设计PPT结构 | Claude Sonnet |
| 4 | TTS text cleaning / TTS文本清洗 | Claude Haiku |
| 5 | Parallel per-slide processing / 并行处理每张幻灯片: | |
|   | - Image prompt generation / 图片提示词生成 | Claude Sonnet |
|   | - Image generation (3 per slide) / 图片生成（每张3图） | Nano Banana Pro (Gemini) |
|   | - TTS audio synthesis / 语音合成 | Fish Audio / Edge TTS |
|   | - Ken Burns animation + cross-fade / 推拉动画+淡入淡出 | Local (PIL + ffmpeg) |
| 6 | Merge all slides into final video / 合并为完整视频 | ffmpeg |
| 7 | Generate subtitles / 生成字幕 | faster-whisper |
| 8 | Burn subtitles into video / 烧录字幕 | PIL + ffmpeg |

## Features / 特性

- **Multi-agent AI pipeline** / 多智能体流水线: Different models for different tasks (Opus for writing, Sonnet for structure, Haiku for cleaning)
- **3 images per slide with diversity** / 每张幻灯片3张差异化配图: Each image uses a different camera directive (wide shot, close-up, detail, symbolic) + previous prompt context to avoid repetition
- **Ken Burns + cross-fade** / 推拉动画+交叉淡入淡出: Static images come alive with slow zoom/pan effects and smooth transitions
- **Voice cloning TTS** / 声音克隆: Fish Audio for cloned voice, Edge TTS as free fallback
- **Chinese subtitles** / 中文字幕: Real-time subtitle generation via faster-whisper, burned into video
- **Banned phrases filter** / 禁用词过滤: Automatically removes unwanted phrases (e.g., "很多人问我") from generated scripts
- **Resume capability** / 断点续跑: `--resume` flag skips expensive LLM steps and reuses cached data
- **Parallel processing** / 并行处理: Slides are processed concurrently with ThreadPoolExecutor

## Requirements / 依赖

- Python 3.9+
- ffmpeg (`brew install ffmpeg`)
- API keys:
  - `ANTHROPIC_API_KEY` — [Anthropic Console](https://console.anthropic.com/)
  - `GOOGLE_API_KEY` — [Google AI Studio](https://aistudio.google.com/)
  - `FISH_AUDIO_API_KEY` (optional) — [Fish Audio](https://fish.audio/)

## Setup / 安装

```bash
git clone https://github.com/cchck/videoGenerator.git
cd videoGenerator
pip install -r requirements.txt
brew install ffmpeg  # macOS
```

Set environment variables / 设置环境变量:

```bash
export ANTHROPIC_API_KEY="your-key"
export GOOGLE_API_KEY="your-key"
export FISH_AUDIO_API_KEY="your-key"  # optional, for voice cloning
```

## Usage / 使用

```bash
# Generate video from an idea / 从想法生成视频
python main.py "你的主题或想法"

# Use an existing script / 使用已有文稿
python main.py --script path/to/script.md

# Resume from cached data (skip LLM steps) / 断点续跑（跳过LLM步骤）
python main.py --resume

# Only generate/burn subtitles on existing video / 仅生成字幕
python main.py --subtitle
```

## Output / 输出

```
output/
├── final_video_subtitled.mp4  # Final video with subtitles / 带字幕的最终视频
├── final_video.mp4            # Video without subtitles / 无字幕视频
├── final_audio.mp3            # Extracted audio / 提取的音频
├── subtitles.srt              # SRT subtitle file / 字幕文件
├── draft/                     # Cached intermediate data / 缓存的中间数据
│   ├── script.md
│   ├── sentences.json
│   ├── ppt_structure.json
│   ├── ppt_structure_full.json
│   └── tts_cleaned.json
├── slides/                    # Generated images / 生成的图片
├── audio/                     # Per-slide audio / 每张幻灯片的音频
└── video/                     # Per-slide video / 每张幻灯片的视频
```

## Configuration / 配置

All settings are in `config.py` / 所有配置项在 `config.py` 中:

| Setting | Default | Description |
|---------|---------|-------------|
| `TTS_ENGINE` | `fish_audio` | `fish_audio` (voice clone) or `edge_tts` (free) |
| `IMAGES_PER_SLIDE` | `3` | Number of images generated per slide |
| `MAX_SLIDES` | `10` | Maximum number of slides |
| `TARGET_SCRIPT_WORDS` | `1250` | Target script length (~5 min video) |
| `TARGET_LANGUAGE` | `zh` | `zh` (Chinese) or `en` (English) |
| `KEN_BURNS_ZOOM` | `1.15` | Zoom factor for Ken Burns effect |
| `CROSSFADE_DURATION` | `0.8` | Cross-fade transition duration (seconds) |

## Cost Estimate / 成本估算

Per video (~5 min) / 每个视频（约5分钟）:

| Service | Cost |
|---------|------|
| Claude (script + structure + prompts) | ~$0.50 |
| Nano Banana Pro (30 images) | ~$0.60 |
| Fish Audio TTS | ~$0.30 |
| **Total** | **~$1.40** |

Using Edge TTS instead of Fish Audio reduces cost to ~$1.10 / 使用 Edge TTS 替代 Fish Audio 可降至约 $1.10。

## Project Structure / 项目结构

```
agents/          # LLM agents (script, PPT structure, image prompts, TTS cleaning)
tools/           # Tool modules (image gen, TTS, video composition, subtitles)
prompts/         # System prompts for each agent
schemas/         # JSON schemas for structured output validation
config.py        # All configuration
main.py          # Pipeline orchestrator
banned_phrases.txt  # Phrases to filter from generated scripts
```
