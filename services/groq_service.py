"""Thin wrapper around the Groq SDK. All AI calls in the app go through here
so the API key never has to touch any other module (and never the frontend)."""
import json
from flask import current_app

_client = None

REQUEST_TIMEOUT_SECONDS = 20.0


class GroqNotConfigured(Exception):
    pass


class AIServiceError(Exception):
    """Raised when Groq is configured but the request itself fails
    (timeout, rate limit, network error, API outage, etc.) - distinct from
    GroqNotConfigured so callers can show a different, accurate message."""
    pass


def _get_client():
    global _client
    api_key = current_app.config.get("GROQ_API_KEY")
    if not api_key:
        raise GroqNotConfigured(
            "GROQ_API_KEY is not set. Add it to your .env file to enable AI features."
        )
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=api_key, timeout=REQUEST_TIMEOUT_SECONDS)
    return _client


def chat_completion(messages, json_mode=False, temperature=0.4, max_tokens=2000):
    """Run a chat completion. Raises GroqNotConfigured if no API key is set,
    and AIServiceError if the request itself fails, so callers can show a
    clean message instead of a stack trace either way."""
    client = _get_client()
    model = current_app.config.get("GROQ_MODEL", "openai/gpt-oss-120b")

    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        raise AIServiceError(f"The AI service request failed: {exc}") from exc
    return response.choices[0].message.content


def chat_completion_json(messages, temperature=0.3, max_tokens=2000):
    """Run a completion and parse the result as JSON. Returns None if the
    model returned something that isn't valid JSON (caller should handle)."""
    raw = chat_completion(messages, json_mode=True, temperature=temperature, max_tokens=max_tokens)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def is_configured():
    from flask import current_app
    return bool(current_app.config.get("GROQ_API_KEY"))
