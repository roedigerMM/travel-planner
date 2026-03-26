import json
from typing import Any

import requests


class AIProviderError(RuntimeError):
    """Raised when an upstream AI provider is unavailable or returns invalid data."""


class OpenAINormalizer:
    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model

    def normalize_search_payload(self, free_text: str) -> dict[str, Any]:
        if not self.api_key:
            raise AIProviderError("OpenAI API key is not configured.")

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You normalize travel search requests into JSON with keys "
                        "origins, travel_month, duration_days, max_price, currency_code, "
                        "non_stop, and trip_type."
                    ),
                },
                {"role": "user", "content": free_text},
            ],
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as exc:
            raise AIProviderError("OpenAI normalization is temporarily unavailable.") from exc


class AnthropicEnricher:
    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model

    def enrich_destination(
        self,
        destination_iata: str,
        trip_type: str,
        travel_month: str | None,
        duration_days: int | None,
        max_price: float | None,
        currency_code: str | None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise AIProviderError("Anthropic API key is not configured.")

        url = f"{self.api_base}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 200,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Return only JSON with keys fit_score and rationale. "
                        "fit_score must be an integer from 0 to 100. "
                        "rationale must be a single short sentence. "
                        "Do not wrap the JSON in markdown fences. "
                        "Evaluate this destination match: "
                        + json.dumps(
                            {
                                "destination_iata": destination_iata,
                                "trip_type": trip_type,
                                "travel_month": travel_month,
                                "duration_days": duration_days,
                                "max_price": max_price,
                                "currency_code": currency_code,
                            }
                        )
                    ),
                }
            ],
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            text = "".join(
                item.get("text", "")
                for item in resp.json().get("content", [])
                if item.get("type") == "text"
            )
            return json.loads(extract_json_object(text))
        except (requests.RequestException, json.JSONDecodeError) as exc:
            raise AIProviderError("Anthropic enrichment is temporarily unavailable.") from exc


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped
