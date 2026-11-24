"""Test script for Groq API connectivity and model response.

Verifies fast model (llama-3.1-8b-instant) inference, latency, and token efficiency.
"""

import sys
import time
from claimsense.config import get_settings


def test_groq_connectivity() -> bool:
    settings = get_settings()

    print("=" * 60)
    print("ClaimSense: Groq LLM API Connectivity Test")
    print("=" * 60)

    if not settings.is_groq_configured:
        print("[INFO] GROQ_API_KEY is not set in your .env file.")
        print("Required variable: GROQ_API_KEY")
        print("Mock / offline agent mode will be used for testing until an API key is provided.")
        print("Get a free key anytime from https://console.groq.com")
        print("=" * 60)
        return False

    print(f"Testing model: {settings.GROQ_FAST_MODEL}")
    print("Sending test inference prompt...")

    start_time = time.time()
    try:
        from groq import Groq

        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_FAST_MODEL,
            messages=[
                {"role": "system", "content": "You are a concise assistant verifying API connectivity."},
                {"role": "user", "content": "Reply with 'Groq connected successfully' and the current year."},
            ],
            temperature=0,
            max_tokens=30,
        )

        latency = time.time() - start_time
        reply = response.choices[0].message.content.strip()
        tokens = response.usage.total_tokens if response.usage else "N/A"

        print(f"\n[SUCCESS] Groq API responded in {latency:.2f}s!")
        print(f"Model Output: {reply}")
        print(f"Tokens Used:  {tokens}")
        print("=" * 60)
        return True

    except Exception as exc:
        print(f"\n[ERROR] Groq API test failed: {exc}")
        return False


if __name__ == "__main__":
    success = test_groq_connectivity()
    sys.exit(0 if success else 1)
