"""Step 2: Sentence list → PPT structure JSON using Claude."""

import os
import json
import anthropic
import config


def load_prompt() -> str:
    prompt_path = os.path.join(config.PROJECT_ROOT, "prompts", "ppt_structure_creator.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def load_schema() -> dict:
    schema_path = os.path.join(config.PROJECT_ROOT, "schemas", "ppt_structure_schema.json")
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def repair_structure_indices(structure: list, total_sentences: int) -> list:
    """
    Fix common index issues: gaps, overlaps, out-of-range.
    Ensures every sentence from 0 to total_sentences-1 is covered exactly once.
    """
    # Sort by voice_over_narrative start
    structure.sort(key=lambda s: s["voice_over_narrative"][0])

    repaired = []
    expected_start = 0

    for i, slide in enumerate(structure):
        start, end = slide["voice_over_narrative"]

        # Clamp to valid range
        start = max(0, min(start, total_sentences - 1))
        end = max(start, min(end, total_sentences - 1))

        # Fix gap: extend start back to expected
        if start > expected_start:
            start = expected_start
        # Fix overlap: push start forward
        elif start < expected_start:
            start = expected_start
            if end < start:
                end = start

        slide["voice_over_narrative"] = [start, end]
        slide["index"] = i + 1
        expected_start = end + 1
        repaired.append(slide)

    # If last slide doesn't reach the end, extend it
    if repaired and repaired[-1]["voice_over_narrative"][1] < total_sentences - 1:
        repaired[-1]["voice_over_narrative"][1] = total_sentences - 1

    return repaired


def validate_structure_indices(structure: list, total_sentences: int) -> tuple[bool, str]:
    """Check that every sentence index is used exactly once."""
    used = set()
    for slide in structure:
        start, end = slide["voice_over_narrative"]
        for idx in range(start, end + 1):
            if idx in used:
                return False, f"Sentence {idx} used more than once"
            used.add(idx)

    expected = set(range(total_sentences))
    missing = expected - used
    if missing:
        return False, f"Missing sentences: {sorted(missing)}"

    extra = used - expected
    if extra:
        return False, f"Out-of-range sentences: {sorted(extra)}"

    return True, "OK"


def reconstruct_with_text(structure: list, sentences: list[dict]) -> list:
    """Replace voice_over_narrative indices with actual sentence text."""
    result = []
    for slide in structure:
        slide_copy = dict(slide)
        start, end = slide_copy["voice_over_narrative"]
        text_sentences = []
        for idx in range(start, end + 1):
            if idx < len(sentences):
                text_sentences.append(sentences[idx]["sentence"])
        slide_copy["voice_over_text"] = "".join(text_sentences)
        result.append(slide_copy)
    return result


def generate_ppt_structure(sentences: list[dict]) -> list:
    """
    Takes indexed sentence list and returns PPT structure JSON.
    Includes retry logic up to MAX_RETRIES times.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system_prompt = load_prompt()
    total = len(sentences)

    user_content = (
        f"以下是带索引的句子列表，共 {total} 句（索引 0 到 {total - 1}）。\n"
        f"请将它们分配到约 {config.MAX_SLIDES} 页幻灯片中。\n\n"
        f"```json\n{json.dumps(sentences, ensure_ascii=False, indent=2)}\n```"
    )

    for attempt in range(1, config.MAX_RETRIES + 1):
        print(f"  [PPT Structure] Attempt {attempt}/{config.MAX_RETRIES}...")

        message = client.messages.create(
            model=config.PPT_STRUCTURE_MODEL,
            max_tokens=8192,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )

        raw_text = message.content[0].text.strip()

        # Extract JSON from response (handle potential markdown wrapping)
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
            structure = json.loads(raw_text)
        except json.JSONDecodeError as e:
            print(f"  [PPT Structure] JSON parse error: {e}")
            # Try to fix common JSON issues
            try:
                import re
                fixed = raw_text
                # Fix trailing commas before ] or }
                fixed = re.sub(r',\s*([}\]])', r'\1', fixed)
                # Fix unescaped quotes inside strings by finding problematic lines
                # Try replacing smart quotes
                fixed = fixed.replace('\u201c', '\\"').replace('\u201d', '\\"')
                fixed = fixed.replace('\u2018', "\\'").replace('\u2019', "\\'")
                structure = json.loads(fixed)
                print(f"  [PPT Structure] Fixed JSON and parsed successfully")
            except (json.JSONDecodeError, Exception):
                if attempt < config.MAX_RETRIES:
                    user_content = (
                        f"以下是带索引的句子列表，共 {total} 句（索引 0 到 {total - 1}）。\n"
                        f"请将它们分配到约 {config.MAX_SLIDES} 页幻灯片中。\n\n"
                        f"```json\n{json.dumps(sentences, ensure_ascii=False, indent=2)}\n```\n\n"
                        f"重要：你的输出必须是合法的 JSON 数组。不要在 JSON 字符串值中使用未转义的双引号。"
                        f"所有字符串值中的双引号必须用 \\\" 转义。只输出 JSON，不要任何其他文字。"
                    )
                    continue
                raise

        # Repair and validate
        structure = repair_structure_indices(structure, total)
        valid, msg = validate_structure_indices(structure, total)

        if valid:
            print(f"  [PPT Structure] Validation passed: {len(structure)} slides")
            return structure
        else:
            print(f"  [PPT Structure] Validation failed: {msg}")
            if attempt < config.MAX_RETRIES:
                user_content += f"\n\n上次生成的结构有问题：{msg}。请修正后重新输出完整的 JSON 数组。"

    # Return best effort after all retries
    print("  [PPT Structure] Warning: returning best-effort structure after all retries")
    return structure
