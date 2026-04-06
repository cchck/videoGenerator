"""Step 3: Slide info → Image generation prompt using Claude."""

import os
import anthropic
import config


# Predefined camera/composition directives for each variant
_VARIANT_DIRECTIVES = [
    "Wide establishing shot — show the full scene from a distance, emphasizing environment and atmosphere.",
    "Medium close-up — focus on a person or central subject, showing emotion and expression.",
    "Detail close-up — zoom into a specific object, texture, or small element that symbolizes the theme.",
    "Symbolic/abstract composition — use visual metaphor, silhouette, or abstract shapes to convey the mood.",
]


def load_prompt() -> str:
    prompt_path = os.path.join(config.PROJECT_ROOT, "prompts", "image_prompt_creator.md")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_image_prompt(
    slide: dict,
    variant: int = 0,
    total_variants: int = 1,
    previous_prompts: list = None,
) -> str:
    """
    Generate an image prompt for a slide.
    Each variant gets a different camera directive and narration segment.
    Previous prompts are passed to ensure diversity.
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    system_prompt = load_prompt()

    voice_text = slide.get("voice_over_text", "N/A")

    # Split narration for different image variants
    if total_variants > 1 and voice_text != "N/A":
        sentences = [s for s in voice_text.replace("。", "。|").replace("？", "？|").replace("！", "！|").split("|") if s.strip()]
        chunk_size = max(1, len(sentences) // total_variants)
        start = variant * chunk_size
        end = start + chunk_size if variant < total_variants - 1 else len(sentences)
        voice_text = "".join(sentences[start:end])

    # Camera/composition directive
    directive = _VARIANT_DIRECTIVES[variant % len(_VARIANT_DIRECTIVES)]

    # Build variant instructions
    variant_hint = ""
    if total_variants > 1:
        variant_hint = (
            f"\n\n## Composition Directive (MUST follow)\n"
            f"This is image {variant + 1} of {total_variants} for this slide.\n"
            f"Required composition: {directive}\n"
        )

        # Include previous prompts to avoid duplication
        if previous_prompts:
            prev_list = "\n".join(f"  - Image {i+1}: {p[:120]}..." for i, p in enumerate(previous_prompts))
            variant_hint += (
                f"\n## Already generated prompts (DO NOT repeat similar scenes)\n"
                f"{prev_list}\n"
                f"Your prompt MUST depict a completely different scene, angle, and subject matter from the above."
            )

    user_content = (
        f"Slide {slide['index']}:\n"
        f"- Elements: {slide['elements']}\n"
        f"- Layout: {slide['layout']}\n"
        f"- Visual Details: {slide['visual_details']}\n"
        f"- Voice Over Text: {voice_text}"
        f"{variant_hint}"
    )

    message = client.messages.create(
        model=config.IMAGE_PROMPT_MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    return message.content[0].text.strip()
