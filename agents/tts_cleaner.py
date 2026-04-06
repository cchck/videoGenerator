"""Step 4: Clean text for TTS engine using Claude."""

import os
import json
import anthropic
import config


def load_prompt() -> str:
    prompt_path = os.path.join(config.PROJECT_ROOT, "prompts", "tts_cleaner.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def clean_for_tts(sentences: list[dict]) -> list[dict]:
    """
    Takes sentence dicts [{"list_index": 0, "sentence": "..."}]
    Returns [{"index": 0, "cleaned_text": "..."}]
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system_prompt = load_prompt()

    user_content = (
        "请清理以下句子，使其适合 TTS 引擎朗读：\n\n"
        f"```json\n{json.dumps(sentences, ensure_ascii=False, indent=2)}\n```"
    )

    message = client.messages.create(
        model=config.TTS_CLEAN_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = message.content[0].text.strip()

    # Extract JSON
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        json_lines = []
        inside = False
        for line in lines:
            if line.startswith("```") and not inside:
                inside = True
                continue
            elif line.startswith("```") and inside:
                break
            elif inside:
                json_lines.append(line)
        raw_text = "\n".join(json_lines)

    try:
        result = json.loads(raw_text)
        if isinstance(result, dict) and "cleaned_sentences" in result:
            return result["cleaned_sentences"]
        elif isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Fallback: return original sentences as-is
    print("  [TTS Cleaner] Warning: failed to parse, using original text")
    return [{"index": s["list_index"], "cleaned_text": s["sentence"]} for s in sentences]
