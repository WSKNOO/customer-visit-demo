"""
AI summarizer using OpenAI-compatible API.

Supports any OpenAI-compatible chat endpoint (OpenAI, Azure, vLLM, Ollama, etc.).
Configurable via config.yaml or environment variables.
"""

import sys
from typing import Optional

from openai import APIError, OpenAI


def summarize(
    text: str,
    api_base: str = "https://api.openai.com/v1",
    api_key: str = "",
    model: str = "gpt-4o-mini",
    temperature: float = 0.3,
    max_tokens: int = 2048,
    max_input_chars: int = 100000,
) -> str:
    """
    Summarize text using an OpenAI-compatible chat API.

    Args:
        text: Text content to summarize.
        api_base: API base URL (supports any OpenAI-compatible endpoint).
        api_key: API key.
        model: Model name.
        temperature: Generation temperature (0.0-1.0).
        max_tokens: Maximum tokens in the summary.
        max_input_chars: Truncate input to this many characters.

    Returns:
        Summary text, or truncated original text if summarization fails.
    """
    if not api_key:
        return _truncate_text(text, max_input_chars)

    # Truncate input if needed
    input_text = _truncate_text(text, max_input_chars)

    try:
        client = OpenAI(base_url=api_base, api_key=api_key)

        system_prompt = (
            "You are a helpful assistant specialized in summarizing content. "
            "Please summarize the following content concisely, preserving key facts, "
            "data, conclusions, and important details. "
            "If the content contains tables or structured data, keep the important numbers "
            "and relationships. Maintain the original language of the content. "
            "Output in Chinese if the content is primarily in Chinese, otherwise in English."
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Please summarize this content:\n\n{input_text}"},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if response.choices and len(response.choices) > 0:
            summary = response.choices[0].message.content.strip()
            if summary:
                return summary

        return input_text

    except APIError as exc:
        print(f"[summarizer] API error: {exc}", file=sys.stderr)
        return input_text
    except Exception as exc:
        print(f"[summarizer] Error: {exc}", file=sys.stderr)
        return input_text


def _truncate_text(text: str, max_chars: int) -> str:
    """Truncate long text from the middle, keeping head and tail."""
    if len(text) <= max_chars:
        return text

    half = max_chars // 2
    head = text[:half]
    tail = text[-(max_chars - half):]
    return f"{head}\n\n[... content truncated by summarizer ({len(text)} chars total) ...]\n\n{tail}"