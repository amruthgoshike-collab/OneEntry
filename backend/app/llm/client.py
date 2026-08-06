"""ALL Gemini calls go through this module.

PDFs and images are sent to the model natively — there is deliberately no OCR
library in this project, because handing Gemini the raw file keeps the document
layout as context instead of flattening it to a line of text.

Every call asks for JSON. Malformed output is stripped of markdown fences,
retried exactly once with a sterner instruction, and on the second failure
raises `GeminiError` with the raw response logged at ERROR.
"""
import json
import logging
import re
from functools import lru_cache

from google import genai
from google.genai import types

from app.config import get_settings

logger = logging.getLogger(__name__)

# Gemini reads these natively. Anything else is rejected before we spend a call.
SUPPORTED_MIME_TYPES = frozenset({
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
})

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

_RETRY_NUDGE = (
    "\n\nYour previous reply could not be parsed as JSON. Reply with the JSON "
    "object ONLY — no prose, no markdown fences, no trailing commas."
)


class GeminiError(RuntimeError):
    """A Gemini call failed, or returned output we could not use."""


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    api_key = get_settings().GEMINI_API_KEY
    if not api_key:
        raise GeminiError("GEMINI_API_KEY is not set — add it to .env")
    return genai.Client(api_key=api_key)


def strip_fences(text: str) -> str:
    """Pull the payload out of a ```json ... ``` wrapper, if there is one."""
    match = _FENCE_RE.search(text)
    return (match.group(1) if match else text).strip()


def _generate_raw(
    prompt: str,
    file_bytes: bytes | None,
    mime_type: str | None,
    model: str | None,
) -> str:
    if file_bytes is not None:
        if not mime_type:
            raise GeminiError("mime_type is required when sending file bytes")
        if mime_type not in SUPPORTED_MIME_TYPES:
            raise GeminiError(f"Gemini cannot read {mime_type} natively")

    parts = []
    if file_bytes is not None:
        parts.append(types.Part.from_bytes(data=file_bytes, mime_type=mime_type))
    parts.append(types.Part.from_text(text=prompt))

    model_name = model or get_settings().GEMINI_MODEL
    try:
        response = _client().models.generate_content(
            model=model_name,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except GeminiError:
        raise
    except Exception as exc:  # SDK/transport/quota errors
        raise GeminiError(f"Gemini call to {model_name} failed: {exc}") from exc

    text = (response.text or "").strip()
    if not text:
        # Usually a safety block or an exhausted token budget.
        raise GeminiError(
            f"Gemini returned an empty response from {model_name}. "
            f"candidates={response.candidates}"
        )
    return text


def generate_json(
    prompt: str,
    *,
    file_bytes: bytes | None = None,
    mime_type: str | None = None,
    model: str | None = None,
) -> dict:
    """Send a prompt (and optionally a PDF or image) and return parsed JSON.

    Retries once if the first reply will not parse. Raises GeminiError on the
    second failure, having logged the raw response.
    """
    active_prompt = prompt
    for attempt in (1, 2):
        raw = _generate_raw(active_prompt, file_bytes, mime_type, model)
        try:
            data = json.loads(strip_fences(raw))
            if not isinstance(data, dict):
                raise ValueError(f"expected a JSON object, got {type(data).__name__}")
            return data
        except ValueError as exc:  # covers json.JSONDecodeError
            if attempt == 1:
                logger.warning("Gemini returned unparseable JSON (%s); retrying once.", exc)
                active_prompt = prompt + _RETRY_NUDGE
                continue
            logger.error(
                "Gemini returned unparseable JSON twice (%s). Raw response was:\n%s",
                exc,
                raw,
            )
            raise GeminiError(f"Gemini did not return valid JSON after a retry: {exc}") from exc
