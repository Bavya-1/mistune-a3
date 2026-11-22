"""Model client for the AutoSE agents.

One small client for both providers (ADR-006). Both Groq and Gemini offer an
OpenAI-compatible chat-completions endpoint, so the same request and response
format, including tool calls, works for both.

What it does (ADR-009):
  * stays under the provider's tokens-per-minute and requests-per-minute limits
    by waiting before it sends,
  * retries a few times on rate-limit and server errors, then fails clearly,
  * enforces a hard per-agent budget (calls and tokens),
  * logs token usage per call to a JSONL file, for the total in the report.

It never logs prompts, replies or keys, and keys are read from the
environment only at call time.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

PROVIDERS: Dict[str, Dict[str, Any]] = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        # free-tier limits observed on 2026-11-21 (ADR-006)
        "tpm": 8_000,
        "rpm": 30,
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key_env": "GEMINI_API_KEY",
        "tpm": 250_000,
        "rpm": 5,
    },
    # Vercel AI Gateway: one OpenAI-compatible endpoint for many models (ids like "google/gemini-2.5-flash-lite").
    # Added after a real run showed the direct Gemini model was closed to new accounts and its daily quota tiny.
    "gateway": {
        "url": "https://ai-gateway.vercel.sh/v1/chat/completions",
        "key_env": "AI_GATEWAY_API_KEY",
        "tpm": 250_000,
        "rpm": 30,
    },
}

CHARS_PER_TOKEN = 3.0  # deliberately pessimistic, so we over-estimate prompt size
MAX_RETRIES = 3
MAX_WAIT_SECONDS = 90  # never sleep longer than this for one rate-limit wait


class LLMError(Exception):
    """The model call failed (after retries)."""


class BudgetExceeded(LLMError):
    """The agent used up its call or token budget."""


class PromptTooLarge(LLMError):
    """One prompt alone would exceed the per-minute token limit."""


@dataclass
class Budget:
    max_calls: int
    max_tokens: int
    calls: int = 0
    tokens: int = 0

    def check(self) -> None:
        if self.calls >= self.max_calls:
            raise BudgetExceeded(f"call budget used up ({self.calls}/{self.max_calls})")
        if self.tokens >= self.max_tokens:
            raise BudgetExceeded(f"token budget used up ({self.tokens}/{self.max_tokens})")

    def record(self, tokens: int) -> None:
        self.calls += 1
        self.tokens += tokens


def estimate_tokens(messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> int:
    """Cheap, pessimistic size estimate (characters / 3)."""
    chars = len(json.dumps(messages, ensure_ascii=False))
    if tools:
        chars += len(json.dumps(tools, ensure_ascii=False))
    return int(chars / CHARS_PER_TOKEN) + 1


@dataclass
class Pacer:
    """Sliding one-minute window of requests and tokens."""

    tpm: int
    rpm: int
    window: Deque[Tuple[float, int]] = field(default_factory=deque)

    def _trim(self, now: float) -> None:
        while self.window and now - self.window[0][0] >= 60:
            self.window.popleft()

    def wait_time(self, tokens: int, now: float) -> float:
        """Seconds to wait before a request of `tokens` fits in the window."""
        self._trim(now)
        used_tokens = sum(t for _, t in self.window)
        if len(self.window) < self.rpm and used_tokens + tokens <= self.tpm:
            return 0.0
        # wait until enough old entries have left the window
        freed_tokens, freed_requests = 0, 0
        for ts, t in self.window:
            freed_tokens += t
            freed_requests += 1
            enough_tokens = used_tokens - freed_tokens + tokens <= self.tpm
            enough_requests = len(self.window) - freed_requests < self.rpm
            if enough_tokens and enough_requests:
                return max(0.0, ts + 60 - now) + 0.5
        return 60.0

    def record(self, tokens: int, now: float) -> None:
        self.window.append((now, tokens))


class LLMClient:
    def __init__(
        self,
        role: str,
        provider: str,
        model: str,
        budget: Budget,
        usage_log: Optional[str] = None,
        max_output_tokens: int = 1500,
    ) -> None:
        if provider not in PROVIDERS:
            raise ValueError(f"unknown provider {provider!r}")
        cfg = PROVIDERS[provider]
        self.role = role
        self.provider = provider
        self.model = model
        self.budget = budget
        self.max_output_tokens = max_output_tokens
        self.usage_log = usage_log or os.environ.get("AUTOSE_USAGE_LOG", "usage.jsonl")
        self._cfg = cfg
        self._pacer = Pacer(tpm=cfg["tpm"], rpm=cfg["rpm"])

    @property
    def tpm(self) -> int:
        """The provider's tokens-per-minute limit; callers size their prompts from it."""
        return int(self._cfg["tpm"])

    # ------------------------------------------------------------------
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Send one chat request. Returns {"message": {...}, "usage": {...}}."""
        self.budget.check()

        estimate = estimate_tokens(messages, tools) + self.max_output_tokens
        if estimate > self._cfg["tpm"]:
            raise PromptTooLarge(
                f"{self.role}: prompt estimated at {estimate} tokens, "
                f"limit is {self._cfg['tpm']} per minute for {self.provider}"
            )

        key = os.environ.get(self._cfg["key_env"], "")
        if not key:
            raise LLMError(f"environment variable {self._cfg['key_env']} is not set")

        body: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_output_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        payload = json.dumps(body).encode("utf-8")

        last_error = "unknown error"
        for attempt in range(MAX_RETRIES + 1):
            self._pace(estimate)
            started = time.time()
            req = urllib.request.Request(
                self._cfg["url"],
                data=payload,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    # Groq sits behind Cloudflare, which rejects Python's default user agent (HTTP 403, code 1010).
                    "User-Agent": "autose-agent/1.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                status = exc.code
                detail = _short(exc.read().decode("utf-8", errors="replace"))
                last_error = f"HTTP {status}: {detail}"
                self._pacer.record(estimate, time.time())  # a failed call still counts
                if status == 429 or status >= 500:
                    if attempt < MAX_RETRIES:
                        time.sleep(_retry_after(exc, attempt))
                        continue
                raise LLMError(f"{self.role} ({self.provider}/{self.model}): {last_error}") from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = f"network error: {type(exc).__name__}"
                if attempt < MAX_RETRIES:
                    time.sleep(_retry_after(None, attempt))
                    continue
                raise LLMError(f"{self.role} ({self.provider}/{self.model}): {last_error}") from None

            usage = data.get("usage") or {}
            total = int(usage.get("total_tokens") or estimate)
            self._pacer.record(total, time.time())
            self.budget.record(total)
            self._log(usage, total, time.time() - started)
            try:
                message = data["choices"][0]["message"]
            except (KeyError, IndexError, TypeError):
                raise LLMError(f"{self.role}: unexpected response shape from {self.provider}") from None
            return {"message": message, "usage": usage}

        raise LLMError(f"{self.role} ({self.provider}/{self.model}): {last_error}")

    # ------------------------------------------------------------------
    def _pace(self, tokens: int) -> None:
        wait = self._pacer.wait_time(tokens, time.time())
        if wait > 0:
            time.sleep(min(wait, MAX_WAIT_SECONDS))

    def _log(self, usage: Dict[str, Any], total: int, seconds: float) -> None:
        record = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "role": self.role,
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": total,
            "seconds": round(seconds, 2),
        }
        try:
            with open(self.usage_log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError:
            pass  # logging must never break a run


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text[:limit]


def _retry_after(exc: Optional[urllib.error.HTTPError], attempt: int) -> float:
    if exc is not None:
        header = exc.headers.get("Retry-After") if exc.headers else None
        if header:
            try:
                return min(float(header) + 1, MAX_WAIT_SECONDS)
            except ValueError:
                pass
    return min(5 * (2**attempt), MAX_WAIT_SECONDS)
