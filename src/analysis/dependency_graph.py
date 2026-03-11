"""
Dependency Graph Builder.

Builds a directed call graph across ALL parsed files in a repository.
Nodes  = CodeUnit qualified names (e.g. "CustomerProcessor.main").
Edges  = caller → callee  (resolved to qualified names where possible).

Uses NetworkX for graph operations.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

import networkx as nx

from src.parsers.base_parser import CodeUnit, ParseResult


class DependencyGraph:
    """Multi-file call graph with helpers for neighbour queries."""

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()
        # Both qualified ("ClassName.method") and simple ("method") names
        # map to the same CodeUnit for flexible lookup.
        self._units: Dict[str, CodeUnit] = {}

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------

    def add_parse_result(self, result: ParseResult) -> None:
        """Ingest all CodeUnits from one parsed file."""
        # First pass: register all units so callee resolution works
        for unit in result.units.values():
            self._register_unit(unit)

        # Second pass: add edges with callee name resolution
        for unit in result.units.values():
            caller_key = self._node_key(unit)
            for callee_name in unit.calls:
                callee_key = self._resolve_to_node_key(callee_name)
                self._graph.add_edge(caller_key, callee_key)

    def finalize(self) -> None:
        """Call after all files are ingested.  Stub-marks unresolved nodes."""
        for node in list(self._graph.nodes):
            if node not in self._units:
                self._graph.nodes[node]["stub"] = True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_unit(self, name: str) -> Optional[CodeUnit]:
        """Look up a unit by simple or qualified name."""
        return self._units.get(name)

    def get_all_units(self) -> Dict[str, CodeUnit]:
        """Return only units whose node key exists in the graph."""
        return {
            node: self._units[node]
            for node in self._graph.nodes
            if node in self._units
        }

    def get_callees(self, name: str) -> List[str]:
        """Direct callees of *name*. Accepts simple or qualified name."""
        node = self._resolve_to_node_key(name)
        if node not in self._graph:
            return []
        return list(self._graph.successors(node))

    def get_callers(self, name: str) -> List[str]:
        """Units that call *name*. Accepts simple or qualified name."""
        node = self._resolve_to_node_key(name)
        if node not in self._graph:
            return []
        return list(self._graph.predecessors(node))

    def get_transitive_deps(self, name: str, max_depth: int = 6) -> Set[str]:
        """BFS: all transitive callees of *name* up to *max_depth* hops."""
        start = self._resolve_to_node_key(name)
        visited: Set[str] = set()
        queue = [(start, 0)]
        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue
            visited.add(current)
            if current in self._graph:
                for callee in self._graph.successors(current):
                    if callee not in visited:
                        queue.append((callee, depth + 1))
        visited.discard(start)
        return visited

    def get_entry_points(self) -> List[str]:
        """Qualified names of units marked as entry points (deduplicated)."""
        seen: Set[str] = set()
        result: List[str] = []
        for unit in self._units.values():
            if unit.is_entry_point:
                key = self._node_key(unit)
                if key not in seen:
                    seen.add(key)
                    result.append(key)
        return result

    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    def summary(self) -> str:
        return (
            f"DependencyGraph: {self.node_count()} nodes, "
            f"{self.edge_count()} edges"
        )

    def to_dict(self) -> dict:
        """Return adjacency dict (only resolved/known nodes)."""
        return {
            node: [c for c in self._graph.successors(node)]
            for node in self._graph.nodes
            if node in self._units   # skip stubs
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register_unit(self, unit: CodeUnit) -> None:
        key = self._node_key(unit)
        self._graph.add_node(key, unit=unit)
        self._units[key] = unit
        # Simple-name alias for convenient lookup
        if unit.name not in self._units:
            self._units[unit.name] = unit

    def _resolve_to_node_key(self, name: str) -> str:
        """
        Given a simple or qualified name, return the graph node key.
        If an alias mapping exists, return its qualified key;
        otherwise return the name as-is (may be external/stub).
        """
        # Already a known node
        if name in self._graph:
            return name
        # Is it a simple-name alias for a known unit?
        unit = self._units.get(name)
        if unit is not None:
            key = self._node_key(unit)
            if key in self._graph:
                return key
        return name  # external / library call → stub node

    @staticmethod
    def _node_key(unit: CodeUnit) -> str:
        return unit.qualified_name or unit.name
