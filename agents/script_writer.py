"""Step 1: Idea → Script generation using Claude."""

import os
import anthropic
import config


def load_prompt() -> str:
    prompt_path = os.path.join(config.PROJECT_ROOT, "prompts", "script_writer.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_script(idea: str) -> dict:
    """
    Takes a raw idea/topic and generates a full spoken script.
    Returns {"title": str, "body": str, "full_text": str}.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system_prompt = load_prompt()

    message = client.messages.create(
        model=config.SCRIPT_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"请根据以下主题/想法，写一篇约{config.TARGET_SCRIPT_WORDS}字的视频演讲稿：\n\n{idea}",
            }
        ],
    )

    full_text = message.content[0].text.strip()

    # First line is title, rest is body
    lines = full_text.split("\n", 1)
    title = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else ""

    # Filter banned phrases
    body = _filter_banned_phrases(body)
    full_text = title + "\n" + body

    return {"title": title, "body": body, "full_text": full_text}


def _filter_banned_phrases(text: str) -> str:
    """Remove sentences containing banned phrases."""
    import re
    banned_path = os.path.join(config.PROJECT_ROOT, "banned_phrases.txt")
    if not os.path.exists(banned_path):
        return text

    with open(banned_path, "r", encoding="utf-8") as f:
        banned = [line.strip() for line in f if line.strip()]

    # Split into sentences, filter out any containing banned phrases
    raw_sentences = re.split(r"(?<=[。？！])", text)
    filtered = []
    removed = 0
    for s in raw_sentences:
        if any(phrase in s for phrase in banned):
            removed += 1
            continue
        filtered.append(s)

    if removed > 0:
        print(f"  [Script] Removed {removed} sentences with banned phrases")
    return "".join(filtered)


def split_sentences(text: str) -> list[dict]:
    """
    Split script body into indexed sentences.
    Returns [{"list_index": 0, "sentence": "..."}, ...]
    """
    import re

    # Split on Chinese period, question mark, exclamation mark
    raw_sentences = re.split(r"(?<=[。？！])", text)
    sentences = []
    idx = 0
    for s in raw_sentences:
        s = s.strip()
        if s:
            sentences.append({"list_index": idx, "sentence": s})
            idx += 1
    return sentences
