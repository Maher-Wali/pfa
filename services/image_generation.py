from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from agents.llm import invoke_text


IMAGE_GENERATION_MODEL = "black-forest-labs/FLUX.1-dev"

_GENERATION_VERBS = {
    "generate", "create", "make", "draw", "produce", "design",
    "illustrate", "render", "build", "craft", "need", "get",
}
_IMAGE_NOUNS = {
    "image", "images", "photo", "photos", "picture", "pictures",
    "visual", "visuals", "illustration", "illustrations",
    "graphic", "graphics", "banner", "thumbnail", "poster",
}


def is_image_request(text: str) -> bool:
    tokens = text.lower().split()
    if not tokens:
        return False
    words = set(tokens)
    if words & _GENERATION_VERBS and words & _IMAGE_NOUNS:
        return True
    # noun-first pattern: "an image where...", "a photo where..."
    # strip leading articles then check the word isn't used as a verb ("picture this")
    idx = 0
    if tokens[idx] in {"a", "an", "the"} and len(tokens) > 1:
        idx = 1
    first = tokens[idx]
    next_word = tokens[idx + 1].strip(",:;!?") if idx + 1 < len(tokens) else ""
    return first in _IMAGE_NOUNS and next_word != "this"


_PLATFORM_DIMENSIONS: list[tuple[set[str], int, int]] = [
    ({"instagram", "story", "stories", "reel", "reels", "tiktok"}, 1088, 1920),
    ({"instagram"}, 1088, 1088),
    ({"facebook", "fb"}, 1216, 640),
    ({"twitter", "tweet", "x"}, 1216, 704),
    ({"blog", "header", "banner", "article"}, 1600, 896),
    ({"thumbnail", "youtube"}, 1280, 720),
]
_DEFAULT_DIMENSIONS = (1024, 1024)


PROMPT_OPTIMIZER_SYSTEM = (
    "Rewrite the user's image request into a complete, high-quality image "
    "generation prompt. Preserve the user's intent exactly. Use conversation "
    "context only to resolve ambiguity or missing details. Add visual details "
    "such as composition, style, lighting, mood, background, and aspect ratio. "
    "Do not invent unrelated elements. Output ONLY the final image-generation "
    "prompt. Do not include explanation, markdown, or JSON."
)


class ImagePromptOptimizationError(Exception):
    pass


class ImageGenerationError(Exception):
    pass


@dataclass(frozen=True)
class GeneratedImage:
    data_url: str
    prompt: str
    model: str = IMAGE_GENERATION_MODEL


def optimize_image_prompt(
    llm: Any,
    recent_messages: list[dict[str, Any]],
    user_image_request: str,
) -> str:
    context = _format_recent_context(recent_messages)
    prompt = f"""
Recent conversation context:
{context or "(none)"}

User image request:
{user_image_request}
""".strip()

    try:
        optimized = invoke_text(llm, PROMPT_OPTIMIZER_SYSTEM, prompt).strip()
    except Exception as exc:
        raise ImagePromptOptimizationError(
            "I could not prepare the image prompt. Please try again in a moment."
        ) from exc

    optimized = _strip_code_fence(optimized)
    if not optimized:
        raise ImagePromptOptimizationError(
            "I could not prepare the image prompt. Please try again with a little more detail."
        )

    return optimized


def generate_image(prompt: str) -> GeneratedImage:
    api_key = os.getenv("IMAGE_GENERATION_KEY")
    if not api_key:
        raise ImageGenerationError(
            "Image generation is not configured yet. Add IMAGE_GENERATION_KEY to the server .env file and restart the app."
        )

    try:
        from huggingface_hub import InferenceClient
        from huggingface_hub.errors import HfHubHTTPError
    except Exception as exc:
        raise ImageGenerationError(
            "Image generation dependencies are not installed. Install huggingface_hub and restart the app."
        ) from exc

    client = InferenceClient(api_key=api_key)

    try:
        image = client.text_to_image(
            prompt=prompt,
            model=IMAGE_GENERATION_MODEL,
        )
    except HfHubHTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in {401, 403}:
            message = (
                "Hugging Face rejected the image request. Check that IMAGE_GENERATION_KEY "
                f"is valid and has access to {IMAGE_GENERATION_MODEL}."
            )
        elif status_code == 404:
            message = (
                "The Hugging Face image model could not be found or is not available "
                "to this token."
            )
        else:
            message = (
                "Hugging Face could not generate the image right now. Please try again in a bit."
            )
        raise ImageGenerationError(message) from exc
    except Exception as exc:
        raise ImageGenerationError(
            "Hugging Face could not generate the image right now. Please try again in a bit."
        ) from exc

    return GeneratedImage(data_url=_image_to_data_url(image), prompt=prompt)


def _format_recent_context(recent_messages: list[dict[str, Any]]) -> str:
    lines = []
    for message in recent_messages:
        role = message.get("role", "message")
        content = str(message.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _image_to_data_url(image: Any) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
