"""
Groq LLM Client.

Wraps the official `groq` Python SDK with:
  • Structured system prompts tailored for code modernization.
  • Low temperature (0.1) for deterministic code output.
  • Automatic retry with exponential back-off on rate-limit errors.
  • Safe fallback to a smaller model on 413/context-too-large errors.
"""
from __future__ import annotations

import time
from typing import Optional

from groq import Groq, RateLimitError, APIStatusError

import config


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert software modernization engineer specializing in migrating \
legacy enterprise code to modern {target_language}.

STRICT RULES:
1. Output ONLY clean, working {target_language} code (or Markdown documentation).
2. Preserve ALL business logic exactly — do not add, remove, or change behavior.
3. Use idiomatic {target_language} patterns and standard library where possible.
4. Add brief inline comments ONLY where the original logic is non-obvious.
5. Do NOT explain what you are doing — output the modernized code directly.
6. If the provided context contains dependency functions, use them to understand \
   the full behavior before modernizing.
"""

_DOC_SYSTEM_PROMPT = """\
You are a technical writer specializing in documenting legacy enterprise code.

STRICT RULES:
1. Write clear Markdown documentation explaining what this code does.
2. Include: Purpose, Parameters (if any), Return value, Business rules, \
   Side effects, Dependencies.
3. Be concise — no padding or filler text.
4. Infer intent from variable names and logic, not from potentially stale comments.
"""

_USER_PROMPT_TEMPLATE = """\
Modernize the following {source_language} code to {target_language}.

The TARGET function to modernize is marked "=== TARGET ===".
The DEPENDENCIES section shows the helper functions it calls \
(already cleaned, no dead code, within your context window).

{context_block}

Provide the complete modernized {target_language} equivalent:
"""

_DOC_USER_PROMPT_TEMPLATE = """\
Generate comprehensive documentation for the following {source_language} function.

{context_block}

Write the Markdown documentation:
"""


class GroqClient:
    """Thread-safe Groq API wrapper for code modernization tasks."""

    def __init__(
        self,
        api_key: str = config.GROQ_API_KEY,
        model: str = config.GROQ_MODEL,
        max_retries: int = 3,
    ) -> None:
        self._client = Groq(api_key=api_key)
        self._model = model
        self._fallback_model = config.GROQ_FALLBACK_MODEL
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def modernize(
        self,
        context_block: str,
        source_language: str,
        target_language: str,
        max_tokens: int = config.MAX_OUTPUT_TOKENS,
    ) -> str:
        """
        Ask the LLM to modernize the code in *context_block*.

        Returns the raw LLM response text (modernized code / docs).
        """
        if target_language == "documentation":
            system_prompt = _DOC_SYSTEM_PROMPT
            user_prompt = _DOC_USER_PROMPT_TEMPLATE.format(
                source_language=source_language,
                context_block=context_block,
            )
        else:
            system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
                target_language=target_language
            )
            user_prompt = _USER_PROMPT_TEMPLATE.format(
                source_language=source_language,
                target_language=target_language,
                context_block=context_block,
            )

        return self._call_with_retry(
            system_prompt, user_prompt, max_tokens, self._model
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _call_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int,
        model: str,
    ) -> str:
        last_error: Optional[Exception] = None

        for attempt in range(self._max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.1,     # near-deterministic for code
                    top_p=0.9,
                )
                return response.choices[0].message.content or ""

            except RateLimitError as exc:
                last_error = exc
                wait = 2 ** attempt       # exponential back-off: 1s, 2s, 4s
                time.sleep(wait)

            except APIStatusError as exc:
                # 413 = context too large → retry with smaller/fallback model
                if exc.status_code in (413, 400) and model != self._fallback_model:
                    return self._call_with_retry(
                        system_prompt, user_prompt, max_tokens, self._fallback_model
                    )
                last_error = exc
                break

        raise RuntimeError(
            f"Groq API failed after {self._max_retries} attempts: {last_error}"
        )
