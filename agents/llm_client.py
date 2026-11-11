"""
LLM Client Module
Provides optional hybrid LLM augmentation (Gemini / OpenAI) with automatic
fallback to deterministic specialist engines when offline, sandboxed, or unconfigured.

Security Note: API keys are strictly kept server-side and never exposed in logs or UI.
"""

import json
import os
import re
import urllib.request
import urllib.error
from typing import Any, Dict, Optional, Tuple


def load_dotenv(env_path: Optional[str] = None) -> Dict[str, str]:
    """Lightweight .env loader (zero external dependencies)."""
    if env_path is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(base_dir, ".env")

    env_vars: Dict[str, str] = {}
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        env_vars[key] = val
                        if key not in os.environ:
                            os.environ[key] = val
        except Exception:
            pass
    return env_vars


# Load .env upon module import
load_dotenv()


class LLMClient:
    """Manages LLM provider connectivity, structured execution, and fallback handling."""

    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

        # Determine configured provider
        if self.gemini_key:
            self.provider = "gemini"
            self.model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
            self.has_key = True
        elif self.openai_key:
            self.provider = "openai"
            self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            self.has_key = True
        else:
            self.provider = "none"
            self.model = "none"
            self.has_key = False

        self._is_online = False
        self._status_checked = False
        self._status_message = "Not checked"

    def _mask_key(self, key: str) -> str:
        """Returns a safe masked version of the key (e.g. sk-...a1b2)."""
        if not key or len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"

    def check_connectivity(self, timeout_sec: float = 2.0) -> Tuple[bool, str]:
        """Probes whether external LLM endpoints are reachable."""
        if not self.has_key:
            self._is_online = False
            self._status_checked = True
            self._status_message = "No external LLM API key configured in environment or .env."
            return False, self._status_message

        # Test external DNS / HTTPS connectivity
        test_url = (
            "https://generativelanguage.googleapis.com"
            if self.provider == "gemini"
            else "https://api.openai.com"
        )

        try:
            req = urllib.request.Request(
                test_url,
                headers={"User-Agent": "ShopSmart-Agent/1.0"},
                method="HEAD",
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                self._is_online = True
                self._status_message = f"Connected to {self.provider.upper()} API ({self.model})."
        except urllib.error.HTTPError:
            # An HTTP error (e.g. 404/403) still means the endpoint is reachable over network
            self._is_online = True
            self._status_message = f"Endpoint reachable for {self.provider.upper()}."
        except Exception as e:
            self._is_online = False
            self._status_message = (
                f"External {self.provider.upper()} API is currently unreachable over network "
                f"({type(e).__name__}). Using high-precision deterministic local specialist engine."
            )

        self._status_checked = True
        return self._is_online, self._status_message

    def get_status(self) -> Dict[str, Any]:
        """Returns provider status information for health checks and UI display."""
        if not self._status_checked:
            self.check_connectivity(timeout_sec=1.0)

        active_key = self.gemini_key if self.provider == "gemini" else self.openai_key

        return {
            "provider": self.provider,
            "model": self.model,
            "has_key": self.has_key,
            "masked_key": self._mask_key(active_key) if self.has_key else None,
            "is_online": self._is_online,
            "status_message": self._status_message,
            "engine_mode": "Hybrid (LLM + Local Fallback)" if self._is_online else "Deterministic Local Specialist Engine (Zero Latency)",
        }


# Global singleton instance
llm_client = LLMClient()
