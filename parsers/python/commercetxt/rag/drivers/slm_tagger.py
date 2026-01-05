"""
SLM (Small Language Model) Tagger for advanced semantic tag generation.

Uses LLMs to generate nuanced tags that rule-based systems cannot catch.
Supports multiple backends: OpenAI, Ollama, and local llama.cpp.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any

from ..core.rate_limiter import RateLimiter

# Constants
MIN_TAG_LENGTH = 3  # Minimum characters for a valid tag

# Optional dependencies - graceful degradation
try:
    from openai import OpenAI

    HAS_OPENAI = True
except ImportError:
    OpenAI = None  # type: ignore[assignment, misc]
    HAS_OPENAI = False

# =============================================================================
# Base Interface
# =============================================================================


class BaseSLMBackend(ABC):
    """Abstract base for SLM backends."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from prompt."""
        pass


# =============================================================================
# Backend Implementations
# =============================================================================


class OpenAISLMBackend(BaseSLMBackend):
    """
    OpenAI API backend (GPT-4o-mini recommended for cost efficiency).

    Includes automatic rate limiting to prevent API throttling.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
        max_tokens: int = 150,
        requests_per_second: float = 3.0,
    ):
        """
        Initialize OpenAI SLM backend.

        Args:
            api_key: OpenAI API key
            model: Model name (default: gpt-4o-mini)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            requests_per_second: Rate limit for API calls (default: 3.0)
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.rate_limiter = RateLimiter(calls_per_second=requests_per_second)
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not HAS_OPENAI:
                raise ImportError(
                    "OpenAI not installed. Install with: pip install openai"
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def generate(self, prompt: str) -> str:
        """Generate text with rate limiting."""
        self.rate_limiter.acquire()
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return response.choices[0].message.content or ""


class OllamaSLMBackend(BaseSLMBackend):
    """Ollama backend for local LLM inference (Phi-3, Mistral, Llama, etc.)."""

    def __init__(
        self,
        model: str = "phi3:mini",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.3,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature

    def generate(self, prompt: str) -> str:
        import urllib.request

        url = f"{self.base_url}/api/generate"
        data = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": self.temperature},
            }
        ).encode("utf-8")

        # S310: Validate URL scheme for security
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid URL scheme: {url}")

        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as response:  # noqa: S310
                result = json.loads(response.read().decode("utf-8"))
                response_text = result.get("response", "")
                return str(response_text) if response_text is not None else ""
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Ollama at {self.base_url}: {e}"
            ) from e


class MockSLMBackend(BaseSLMBackend):
    """Mock backend for testing without LLM dependencies."""

    def __init__(self, fixed_tags: list[str] | None = None):
        self.fixed_tags = fixed_tags or ["ai_mock_tag"]

    def generate(self, prompt: str) -> str:
        return json.dumps(self.fixed_tags)


# =============================================================================
# Main SLMTagger Class
# =============================================================================


class SLMTagger:
    """
    Uses a Small Language Model (SLM) to generate advanced semantic tags.

    Captures nuances that rule-based systems miss:
    - Style: "vintage vibe", "minimalist aesthetic"
    - Audience: "great for teenagers", "professional grade"
    - Use case: "perfect for gaming", "travel friendly"

    Example:
        # Using OpenAI (cloud)
        tagger = SLMTagger(backend="openai", api_key="sk-...")

        # Using Ollama (local)
        tagger = SLMTagger(backend="ollama", model="phi3:mini")

        # Using mock (testing)
        tagger = SLMTagger(backend="mock")

        tags = tagger.enhance_tags(
            "Sleek wireless headphones with noise cancellation", []
        )
        # Returns: ["premium_audio", "wireless", "travel_friendly", ...]
    """

    # Prompt template for tag generation
    PROMPT_TEMPLATE = """Analyze this product and extract 3-5 semantic tags.

Product: {text}

Rules:
1. Tags must be lowercase with underscores (e.g., "travel_friendly")
2. Focus on: style, target audience, use cases, quality signals
3. Avoid generic tags like "good" or "nice"
4. Return ONLY a JSON array of strings, nothing else

Example output: ["premium_quality", "business_professional", "travel_friendly"]

Tags:"""

    def __init__(
        self,
        backend: str = "mock",
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ):
        """
        Initialize SLMTagger.

        Args:
            backend: Backend type ("openai", "ollama", "mock")
            model: Model name (backend-specific)
            api_key: API key (for OpenAI)
            base_url: Base URL (for Ollama, default: http://localhost:11434)
            **kwargs: Additional backend-specific options
        """
        self.backend_type = backend
        self._backend = self._create_backend(backend, model, api_key, base_url, kwargs)

    def _create_backend(
        self,
        backend: str,
        model: str | None,
        api_key: str | None,
        base_url: str | None,
        kwargs: dict[str, Any],
    ) -> BaseSLMBackend:
        """Create the appropriate backend instance."""
        if backend == "openai":
            return OpenAISLMBackend(
                api_key=api_key,
                model=model or "gpt-4o-mini",
                **kwargs,
            )
        elif backend == "ollama":
            return OllamaSLMBackend(
                model=model or "phi3:mini",
                base_url=base_url or "http://localhost:11434",
                **kwargs,
            )
        elif backend == "mock":
            return MockSLMBackend(fixed_tags=kwargs.get("fixed_tags"))
        else:
            raise ValueError(
                f"Unknown backend: {backend}. Supported: openai, ollama, mock"
            )

    def enhance_tags(
        self,
        text: str,
        existing_tags: list[str],
        max_new_tags: int = 5,
    ) -> list[str]:
        """
        Generate AI-powered semantic tags for product text.

        Args:
            text: Product description or name
            existing_tags: Existing tags to merge with
            max_new_tags: Maximum number of new tags to add

        Returns:
            Combined list of existing and new tags (deduplicated)
        """
        if not text or not text.strip():
            return existing_tags

        try:
            prompt = self.PROMPT_TEMPLATE.format(text=text[:500])  # Limit input length
            response = self._backend.generate(prompt)
            new_tags = self._parse_tags(response, max_new_tags)
        except Exception:
            # Silently fail - AI tags are enhancement, not critical
            new_tags = []

        # Merge and deduplicate
        all_tags = list(existing_tags) + new_tags
        return list(dict.fromkeys(all_tags))  # Preserve order, remove duplicates

    def _parse_tags(self, response: str, max_tags: int) -> list[str]:
        """Parse LLM response into tag list."""
        # Try to extract JSON array from response
        response = response.strip()

        # Handle markdown code blocks
        if "```" in response:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
            if match:
                response = match.group(1)

        try:
            tags = json.loads(response)
            if isinstance(tags, list):
                # Normalize tags
                normalized = []
                for tag in tags[:max_tags]:
                    if isinstance(tag, str):
                        # Convert to lowercase with underscores
                        clean = re.sub(r"[^\w\s]", "", tag.lower())
                        clean = re.sub(r"\s+", "_", clean).strip("_")
                        if clean and len(clean) >= MIN_TAG_LENGTH:
                            normalized.append(clean)
                return normalized
        except json.JSONDecodeError:
            pass

        # Fallback: try to extract quoted strings
        matches = re.findall(r'"([^"]+)"', response)
        if matches:
            normalized = []
            for tag in matches[:max_tags]:
                clean = re.sub(r"[^\w\s]", "", tag.lower())
                clean = re.sub(r"\s+", "_", clean).strip("_")
                if clean and len(clean) >= MIN_TAG_LENGTH:
                    normalized.append(clean)
            return normalized

        return []

    def is_available(self) -> bool:
        """Check if the backend is available and responsive."""
        try:
            test_response = self._backend.generate("Test")
            return bool(test_response)
        except Exception:
            return False
