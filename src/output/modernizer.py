"""
Modernizer — Orchestrates the full pipeline for a single target unit.

Pipeline:
  1. Clean the optimized context (strip comments / dead code noise).
  2. Build context block string.
  3. Call GroqClient.modernize().
  4. Wrap result in a ModernizationResult.
  5. Optionally write output file.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from src.analysis.context_optimizer import OptimizedContext
from src.preprocessing.code_cleaner import CodeCleaner
from src.llm.groq_client import GroqClient
import config


@dataclass
class ModernizationResult:
    """Holds the output of modernizing one CodeUnit."""

    target_name: str
    source_language: str
    target_language: str
    original_code: str
    modernized_code: str
    context_summary: dict = field(default_factory=dict)
    output_file: Optional[str] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and bool(self.modernized_code)

    def file_extension(self) -> str:
        if self.target_language == "python":
            return ".py"
        elif self.target_language == "go":
            return ".go"
        return ".md"


class Modernizer:
    """
    High-level orchestrator.

    Usage::

        modernizer = Modernizer()
        result = modernizer.run(optimized_ctx, target_language="python")
    """

    def __init__(
        self,
        groq_client: Optional[GroqClient] = None,
        cleaner: Optional[CodeCleaner] = None,
        output_dir: str = config.OUTPUT_DIR,
    ) -> None:
        self._llm = groq_client or GroqClient()
        self._cleaner = cleaner or CodeCleaner()
        self._output_dir = output_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        ctx: OptimizedContext,
        target_language: str = "python",
        save_to_disk: bool = True,
    ) -> ModernizationResult:
        """
        Modernize the target unit referenced by *ctx*.

        Parameters
        ----------
        ctx             : OptimizedContext from ContextOptimizer.optimize()
        target_language : 'python', 'go', or 'documentation'
        save_to_disk    : Write output file into OUTPUT_DIR.
        """
        target_unit = ctx.target_unit
        source_lang = target_unit.language

        # 1. Clean each code unit in the context
        cleaned_target = self._cleaner.clean(target_unit.code, source_lang)

        cleaned_deps: List[Tuple[str, int]] = []
        for dep_unit, depth in ctx.dependency_units:
            cleaned = self._cleaner.clean(dep_unit.code, dep_unit.language)
            label = dep_unit.qualified_name or dep_unit.name
            cleaned_deps.append((f"// --- [{depth}-hop dep] {label} ---\n{cleaned}", depth))

        # 2. Assemble context block
        parts = [
            f"// === TARGET: {target_unit.qualified_name or target_unit.name} ===",
            cleaned_target,
        ]
        if cleaned_deps:
            parts.append("\n// === DEPENDENCIES (call chain) ===")
            for code_block, _ in cleaned_deps:
                parts.append(code_block)
        context_block = "\n\n".join(parts)

        # 3. Call LLM
        try:
            modernized = self._llm.modernize(
                context_block=context_block,
                source_language=source_lang,
                target_language=target_language,
            )
            error = None
        except Exception as exc:
            modernized = ""
            error = str(exc)

        # 4. Optionally save
        output_file = None
        if save_to_disk and modernized:
            output_file = self._save(target_unit, target_language, modernized)

        result = ModernizationResult(
            target_name=target_unit.qualified_name or target_unit.name,
            source_language=source_lang,
            target_language=target_language,
            original_code=target_unit.code,
            modernized_code=modernized,
            context_summary=ctx.summary(),
            output_file=output_file,
            error=error,
        )
        return result

    def run_batch(
        self,
        contexts: dict,         # {name: OptimizedContext}
        target_language: str = "python",
        save_to_disk: bool = True,
    ) -> List[ModernizationResult]:
        results = []
        for name, ctx in contexts.items():
            result = self.run(ctx, target_language=target_language, save_to_disk=save_to_disk)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _save(
        self, unit, target_language: str, content: str
    ) -> str:
        os.makedirs(self._output_dir, exist_ok=True)
        safe_name = (unit.qualified_name or unit.name).replace(".", "_").replace("/", "_")
        ext = ModernizationResult(
            target_name=safe_name,
            source_language=unit.language,
            target_language=target_language,
            original_code="",
            modernized_code="",
        ).file_extension()
        path = os.path.join(self._output_dir, f"{safe_name}{ext}")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        return path
