"""
Context Optimizer — the core technique of the Modernization Engine.

Problem: sending an entire legacy repository to an LLM exceeds context windows
and injects irrelevant "noise", causing hallucinations.

Solution (Context Optimization):
  1. Start from the *target* function the user wants modernized.
  2. BFS through the call graph to collect its transitive dependencies.
  3. Strip dead code & comments from each dependency (reduces token count).
  4. Greedily pack dependencies into the budget, prioritising:
       direct callees > 2-hop > 3-hop > ...
  5. Return the minimal, ranked context that fits within MAX_CONTEXT_TOKENS.

Token counting uses a character heuristic (1 token ≈ 4 chars) when tiktoken
is unavailable, or tiktoken's cl100k_base encoding when available.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from src.parsers.base_parser import CodeUnit
from .dependency_graph import DependencyGraph
from .dead_code_detector import DeadCodeDetector

def _count_tokens(text: str) -> int:
    """
    Count tokens using tiktoken when available and pre-cached,
    otherwise fall back to a character-based heuristic (1 token ≈ 4 chars).
    tiktoken is tried lazily to avoid network downloads at import time.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return max(1, math.ceil(len(text) / 4))


class OptimizedContext:
    """Result object returned by ContextOptimizer."""

    def __init__(
        self,
        target_unit: CodeUnit,
        dependency_units: List[Tuple[CodeUnit, int]],   # (unit, depth)
        total_tokens: int,
        excluded_dead: List[str],
        excluded_budget: List[str],
    ) -> None:
        self.target_unit = target_unit
        self.dependency_units = dependency_units   # ordered by BFS depth
        self.total_tokens = total_tokens
        self.excluded_dead = excluded_dead          # dropped: dead code
        self.excluded_budget = excluded_budget      # dropped: token budget

    def get_context_block(self) -> str:
        """Return all code concatenated, ready to embed in the LLM prompt."""
        parts = [
            f"// === TARGET: {self.target_unit.qualified_name or self.target_unit.name} ===",
            self.target_unit.code,
        ]
        if self.dependency_units:
            parts.append("\n// === DEPENDENCIES (in call order) ===")
            for unit, depth in self.dependency_units:
                label = unit.qualified_name or unit.name
                parts.append(f"\n// --- [{depth}-hop dependency] {label} ---")
                parts.append(unit.code)
        return "\n".join(parts)

    def summary(self) -> dict:
        return {
            "target": self.target_unit.qualified_name or self.target_unit.name,
            "dependencies_included": len(self.dependency_units),
            "total_tokens": self.total_tokens,
            "excluded_dead_code": len(self.excluded_dead),
            "excluded_budget_limit": len(self.excluded_budget),
        }


class ContextOptimizer:
    """
    Produces a token-budget-aware context slice for one target CodeUnit.

    Parameters
    ----------
    graph      : Fully built DependencyGraph (multi-file).
    detector   : DeadCodeDetector pre-built on the same graph.
    max_tokens : Hard token ceiling (default from config).
    max_depth  : Maximum BFS depth for transitive deps.
    """

    def __init__(
        self,
        graph: DependencyGraph,
        detector: DeadCodeDetector,
        max_tokens: int = 6_000,
        max_depth: int = 6,
    ) -> None:
        self._graph = graph
        self._detector = detector
        self._max_tokens = max_tokens
        self._max_depth = max_depth

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(self, target_name: str) -> Optional[OptimizedContext]:
        """
        Build the optimized context for *target_name*.

        Returns None if the target unit is not found in the graph.
        """
        target_unit = self._graph.get_unit(target_name)
        if target_unit is None:
            return None

        # Always use the qualified graph node key for lookups
        target_key = target_unit.qualified_name or target_unit.name

        live_names = self._detector.get_live_unit_names()
        dead_names = set(self._graph.get_all_units().keys()) - live_names

        # Reserve budget for the target itself
        target_tokens = _count_tokens(target_unit.code)
        remaining_budget = self._max_tokens - target_tokens

        # BFS to collect dependency chain (breadth-first = closest first)
        included: List[Tuple[CodeUnit, int]] = []
        excluded_dead: List[str] = []
        excluded_budget: List[str] = []

        visited: Set[str] = {target_key, target_name}
        if target_unit.qualified_name:
            visited.add(target_unit.qualified_name)

        queue: deque[Tuple[str, int]] = deque()
        for callee in self._graph.get_callees(target_key):
            queue.append((callee, 1))

        while queue:
            current_name, depth = queue.popleft()

            if depth > self._max_depth:
                continue
            if current_name in visited:
                continue
            visited.add(current_name)

            unit = self._graph.get_unit(current_name)
            if unit is None:
                continue   # external/library symbol

            # Drop dead code — it confuses the LLM
            if (current_name in dead_names or
                    (unit.qualified_name and unit.qualified_name in dead_names)):
                excluded_dead.append(current_name)
                continue

            tokens = _count_tokens(unit.code)
            if tokens > remaining_budget:
                excluded_budget.append(current_name)
                # Still explore its callees in case shallower ones fit
            else:
                remaining_budget -= tokens
                included.append((unit, depth))

            # Enqueue next hop
            for callee in self._graph.get_callees(current_name):
                if callee not in visited:
                    queue.append((callee, depth + 1))

        total_tokens = self._max_tokens - remaining_budget

        return OptimizedContext(
            target_unit=target_unit,
            dependency_units=included,
            total_tokens=total_tokens,
            excluded_dead=excluded_dead,
            excluded_budget=excluded_budget,
        )

    def optimize_batch(self, target_names: List[str]) -> Dict[str, OptimizedContext]:
        """Optimize multiple targets at once."""
        results = {}
        for name in target_names:
            ctx = self.optimize(name)
            if ctx:
                results[name] = ctx
        return results
