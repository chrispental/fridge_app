"""OpenRouter client wrapper.

OpenRouter exposes an OpenAI-compatible API and routes to many providers whose
support for structured output varies. `call_structured` therefore uses a
fallback ladder: json_schema -> json_object -> plain -> one repair retry.
"""
import json
import logging

from openai import OpenAI

from ..config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set — add it to your .env file."
            )
        _client = OpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            timeout=settings.ai_request_timeout,
        )
    return _client


def _strip_fences(text: str) -> str:
    """Remove a leading/trailing markdown code fence if present."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _extract_json(text: str) -> dict:
    """Parse JSON from a model response, tolerating fences and surrounding prose."""
    cleaned = _strip_fences(text or "")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def call_structured(
    *,
    model: str,
    system_prompt: str,
    user_content,  # str, or a list of content parts (for vision)
    json_schema: dict,
    schema_name: str = "response",
    max_tokens: int = 4096,
    temperature: float = 0.4,
) -> dict:
    """Call a model and return parsed JSON, trying progressively looser modes."""
    client = get_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    response_formats = [
        {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        },
        {"type": "json_object"},
        None,
    ]

    last_error: Exception | None = None
    last_raw: str | None = None

    for response_format in response_formats:
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if response_format is not None:
                kwargs["response_format"] = response_format
            resp = client.chat.completions.create(**kwargs)
            last_raw = resp.choices[0].message.content or ""
            return _extract_json(last_raw)
        except Exception as exc:  # noqa: BLE001 - resilient by design
            last_error = exc
            logger.warning(
                "AI call failed (response_format=%s): %s",
                response_format.get("type") if response_format else "none",
                exc,
            )

    # Last resort: ask the model to repair its own output into valid JSON.
    if last_raw:
        try:
            repair = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "Output ONLY valid minified JSON. No prose, no fences.",
                    },
                    {
                        "role": "user",
                        "content": f"Fix this into valid JSON:\n\n{last_raw}",
                    },
                ],
                max_tokens=max_tokens,
                temperature=0,
            )
            return _extract_json(repair.choices[0].message.content or "")
        except Exception as exc:  # noqa: BLE001
            last_error = exc

    raise RuntimeError(f"AI request failed after all attempts: {last_error}")
