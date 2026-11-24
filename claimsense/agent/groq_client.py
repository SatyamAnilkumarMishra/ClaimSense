"""Resilient Groq Client with Model Routing, Caching, and Quota Guard."""

import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional

from claimsense.config import Settings, get_settings

logger = logging.getLogger(__name__)


class GroqClientWrapper:
    """Manages Groq LLM calls with tier routing, prompt caching, and quota protection."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._cache: Dict[str, str] = {}
        self._tokens_used_today = 0
        self.last_llm_mode: str = "deterministic_fallback"
        self.last_model_name: str = "offline_heuristic"

    def _hash_messages(self, model: str, messages: List[Dict[str, str]]) -> str:
        serialized = json.dumps({"model": model, "messages": messages}, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def generate_json_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model_tier: str = "reasoning",
    ) -> Dict[str, Any]:
        """Calls Groq API to produce structured JSON with caching and offline fallback."""
        model = (
            self.settings.GROQ_REASONING_MODEL
            if model_tier == "reasoning"
            else self.settings.GROQ_FAST_MODEL
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        cache_key = self._hash_messages(model, messages)

        # Check Cache
        if cache_key in self._cache:
            cached_data = json.loads(self._cache[cache_key])
            self.last_llm_mode = cached_data.get("_llm_mode", "deterministic_fallback")
            self.last_model_name = cached_data.get("_model_name", model)
            return cached_data

        # If Groq is not configured or quota exceeded, use deterministic mock fallback
        if not self.settings.is_groq_configured or self._tokens_used_today >= self.settings.GROQ_DAILY_TOKEN_LIMIT:
            self.last_llm_mode = "deterministic_fallback"
            self.last_model_name = "offline_heuristic"
            mock_result = self._mock_triage_decision(user_prompt)
            mock_result["_llm_mode"] = "deterministic_fallback"
            mock_result["_model_name"] = "offline_heuristic"
            self._cache[cache_key] = json.dumps(mock_result)
            return mock_result

        # Live Groq API Execution
        try:
            from groq import Groq
            client = Groq(api_key=self.settings.GROQ_API_KEY)

            # Retry with exponential backoff for rate limits
            last_exc = None
            for attempt in range(1, 4):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0,
                        response_format={"type": "json_object"},
                    )
                    content = response.choices[0].message.content
                    if response.usage:
                        self._tokens_used_today += response.usage.total_tokens

                    data = json.loads(content)
                    data["_llm_mode"] = "live_groq"
                    data["_model_name"] = model
                    self.last_llm_mode = "live_groq"
                    self.last_model_name = model
                    self._cache[cache_key] = json.dumps(data)
                    return data
                except Exception as exc:
                    last_exc = exc
                    if "429" in str(exc):
                        time.sleep(1.0 * (2 ** (attempt - 1)))
                    else:
                        break

            logger.warning(f"Live Groq call failed ({last_exc}). Falling back to deterministic agent reasoning.")
            self.last_llm_mode = "deterministic_fallback"
            self.last_model_name = "offline_heuristic"
            mock_res = self._mock_triage_decision(user_prompt)
            mock_res["_llm_mode"] = "deterministic_fallback"
            mock_res["_model_name"] = "offline_heuristic"
            return mock_res

        except Exception as exc:
            logger.warning(f"Groq invocation failed ({exc}). Using offline reasoning fallback.")
            self.last_llm_mode = "deterministic_fallback"
            self.last_model_name = "offline_heuristic"
            mock_res = self._mock_triage_decision(user_prompt)
            mock_res["_llm_mode"] = "deterministic_fallback"
            mock_res["_model_name"] = "offline_heuristic"
            return mock_res

    def _mock_triage_decision(self, user_prompt: str) -> Dict[str, Any]:
        """Deterministic offline fallback reasoning based on rule check facts in prompt."""
        import re

        # Extract available valid clause IDs from prompt
        available_clauses = re.findall(r"- \[([A-Z0-9\-]+)\] \([A-Z]+\):", user_prompt)
        primary_clause = available_clauses[0] if available_clauses else "AUTO-COV-01"

        # Detect prompt injection attempts
        if "ignore previous instructions" in user_prompt.lower() or "override" in user_prompt.lower():
            return {
                "decision": "NEEDS_REVIEW",
                "confidence": 0.99,
                "reasons": ["Prompt injection attempt detected inside untrusted claimant data. Escalated for safety."],
                "cited_clause_ids": [primary_clause],
            }

        # Check for fraud risk rule failure using regex to handle descriptions between ID and outcome
        has_fraud_fail = bool(re.search(r"RULE-05-FRAUD-RISK.*?->\s*FAIL", user_prompt))
        if has_fraud_fail or "flag_high_risk_customer" in user_prompt.lower():
            return {
                "decision": "ESCALATE_SIU",
                "confidence": 0.95,
                "reasons": ["Customer behavioral risk score is elevated above allowable limits."],
                "cited_clause_ids": [primary_clause],
            }
        elif "FAIL" in user_prompt:
            return {
                "decision": "NEEDS_REVIEW",
                "confidence": 0.90,
                "reasons": ["One or more deterministic coverage or reporting rules failed."],
                "cited_clause_ids": [primary_clause],
            }
        else:
            return {
                "decision": "FAST_TRACK",
                "confidence": 0.96,
                "reasons": ["All deterministic policy checks passed. Eligible for straight-through processing."],
                "cited_clause_ids": [primary_clause],
            }


_groq_client_wrapper_instance: Optional[GroqClientWrapper] = None


def get_groq_client_wrapper() -> GroqClientWrapper:
    """Singleton getter for GroqClientWrapper."""
    global _groq_client_wrapper_instance
    if _groq_client_wrapper_instance is None:
        _groq_client_wrapper_instance = GroqClientWrapper()
    return _groq_client_wrapper_instance
