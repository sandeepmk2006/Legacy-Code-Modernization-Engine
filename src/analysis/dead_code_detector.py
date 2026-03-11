"""
Dead Code Detector.

A CodeUnit is "dead" if it:
  1. Has zero callers in the dependency graph, AND
  2. Is not explicitly flagged as an entry point, AND
  3. Its name is not a known framework/override method.

Detection removes distraction from the LLM context, reducing hallucinations.
"""
from __future__ import annotations

from typing import Dict, List, Set

from src.parsers.base_parser import CodeUnit
from .dependency_graph import DependencyGraph


# Framework/lifecycle method names that must NOT be treated as dead code
# even when they have no explicit callers in the project.
_FRAMEWORK_METHODS: Set[str] = {
    # Java lifecycle / override
    "toString", "hashCode", "equals", "compareTo", "clone",
    "run", "call", "execute", "handle", "doGet", "doPost",
    "doFilter", "onMessage", "onEvent", "init", "destroy",
    "afterPropertiesSet", "configure", "setUp", "tearDown",
    # JUnit
    "setUp", "tearDown", "before", "after", "beforeAll", "afterAll",
    # Spring
    "main",
    # COBOL
    "INITIALIZE", "START", "BEGIN",
}


class DeadCodeDetector:
    """Identifies callable units with no known callers (dead code)."""

    def __init__(self, graph: DependencyGraph) -> None:
        self._graph = graph

    def find_dead_units(self) -> List[CodeUnit]:
        """Return list of CodeUnits considered dead."""
        dead: List[CodeUnit] = []

        for name, unit in self._graph.get_all_units().items():
            # Skip if it's an entry point
            if unit.is_entry_point:
                continue
            # Skip known framework override methods
            if unit.name in _FRAMEWORK_METHODS:
                continue
            # Skip if it has callers
            callers = self._graph.get_callers(name)
            if callers:
                continue
            dead.append(unit)

        return dead

    def get_live_unit_names(self) -> Set[str]:
        """Return names of all units that are NOT dead."""
        dead_names = {u.name for u in self.find_dead_units()}
        dead_names |= {u.qualified_name for u in self.find_dead_units() if u.qualified_name}
        all_names = set(self._graph.get_all_units().keys())
        return all_names - dead_names

    def report(self) -> Dict[str, List[str]]:
        """Human-readable report: {'dead': [...], 'live': [...]}"""
        dead = self.find_dead_units()
        dead_names = [u.qualified_name or u.name for u in dead]
        live_names = list(self.get_live_unit_names())
        return {"dead": sorted(dead_names), "live": sorted(live_names)}
