"""Thin wrapper around the Google Gen AI SDK."""

import time
from typing import Callable, Iterator, List, TypeVar

from google import genai
from google.genai import types

from app.config import settings
from app.prompts import SYSTEM_PROMPT

client = genai.Client(api_key=settings.gemini_api_key)

_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    temperature=0.4,
    max_output_tokens=2048,
)


# Gemini returns 429 (rate limited) and 503 (model busy) for load that usually
# clears in a second or two, so those are retried instead of surfaced.
_RETRY_MARKERS = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE")
_MAX_ATTEMPTS = 4
_BASE_DELAY_SECONDS = 1.0

T = TypeVar("T")


class GeminiError(RuntimeError):
    """Raised when the Gemini API call fails; carries a readable message."""


def _is_retryable(exc: Exception) -> bool:
    return any(marker in str(exc) for marker in _RETRY_MARKERS)


def _with_retries(call: Callable[[], T]) -> T:
    """Run `call`, retrying transient load errors with exponential backoff."""
    last: Exception
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return call()
        except Exception as exc:
            last = exc
            if attempt == _MAX_ATTEMPTS - 1 or not _is_retryable(exc):
                break
            time.sleep(_BASE_DELAY_SECONDS * (2**attempt))
    raise GeminiError(str(last)) from last


def _build_contents(history: List[dict], message: str) -> List[types.Content]:
    contents = [
        types.Content(role=turn["role"], parts=[types.Part(text=turn["text"])])
        for turn in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    return contents


def ask(history: List[dict], message: str) -> str:
    """Single-shot answer."""
    response = _with_retries(
        lambda: client.models.generate_content(
            model=settings.gemini_model,
            contents=_build_contents(history, message),
            config=_CONFIG,
        )
    )

    text = (response.text or "").strip()
    if not text:
        raise GeminiError("Gemini returned an empty response (possibly filtered).")
    return text


def ask_stream(history: List[dict], message: str) -> Iterator[str]:
    """Yield answer chunks as they are generated."""
    # Only the call that opens the stream is retried; once chunks have been sent
    # to the client a retry would duplicate text, so mid-stream errors propagate.
    stream = _with_retries(
        lambda: client.models.generate_content_stream(
            model=settings.gemini_model,
            contents=_build_contents(history, message),
            config=_CONFIG,
        )
    )
    try:
        for chunk in stream:
            if chunk.text:
                yield chunk.text
    except Exception as exc:
        raise GeminiError(str(exc)) from exc
