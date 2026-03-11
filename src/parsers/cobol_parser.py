"""
COBOL source parser (regex-based).

Extracts PROCEDURE DIVISION paragraphs as CodeUnits and maps PERFORM calls
to build the inter-paragraph dependency graph.

Supports fixed-format and free-format COBOL.
"""
import re
import os
from typing import Dict, List, Optional, Tuple

from .base_parser import BaseParser, CodeUnit, ParseResult


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# COBOL is case-insensitive; compile with re.IGNORECASE
_FLAGS = re.IGNORECASE | re.MULTILINE

# Fixed-format: columns 1-6 sequence, 7 indicator, 8-72 area A/B
# We ignore column constraints for simplicity.

# Division headers
_PROC_DIV_RE  = re.compile(r'^\s*PROCEDURE\s+DIVISION', _FLAGS)
_DATA_DIV_RE  = re.compile(r'^\s*DATA\s+DIVISION',       _FLAGS)
_IDENT_DIV_RE = re.compile(r'^\s*IDENTIFICATION\s+DIVISION', _FLAGS)

# Paragraph name = word at beginning of a line in Area-A followed by period
# A paragraph ends when the next paragraph starts OR STOP RUN / END PROGRAM
_PARA_HEADER_RE = re.compile(
    r'^[ \t]{0,8}([A-Z0-9][A-Z0-9\-]*)\s*\.\s*$',
    _FLAGS,
)

# PERFORM (inline or out-of-line)
_PERFORM_RE = re.compile(
    r'\bPERFORM\s+([\w\-]+)(?:\s+THRU\s+([\w\-]+))?',
    _FLAGS,
)

# CALL literal (for subprogram calls)
_CALL_RE = re.compile(r'\bCALL\s+["\']?([\w\-]+)["\']?', _FLAGS)

# Program-ID (entry point)
_PROGRAM_ID_RE = re.compile(r'PROGRAM-ID\s*\.\s*([\w\-]+)', _FLAGS)

# Section names
_SECTION_RE = re.compile(
    r'^[ \t]{0,8}([A-Z0-9][A-Z0-9\-]*)\s+SECTION\s*\.',
    _FLAGS,
)


class CobolParser(BaseParser):
    """Regex-based COBOL parser that extracts paragraphs as CodeUnits."""

    def supports(self, file_extension: str) -> bool:
        return file_extension.lower() in {".cbl", ".cob", ".cobol"}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, file_path: str) -> ParseResult:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()

        program_id = self._extract_program_id(content)
        proc_content, proc_start_line = self._extract_procedure_division(content)

        units: Dict[str, CodeUnit] = {}
        errors: List[str] = []

        if proc_content:
            units = self._extract_paragraphs(
                proc_content, file_path, proc_start_line
            )
        else:
            errors.append("PROCEDURE DIVISION not found.")

        # Mark entry-point paragraphs (first paragraph or known names)
        entry_names = {"MAIN-PARA", "000-MAIN", "START", "BEGIN", "INITIALIZE"}
        for name, unit in units.items():
            if name.upper() in entry_names:
                unit.is_entry_point = True
        if units:
            first_name = next(iter(units))
            units[first_name].is_entry_point = True

        return ParseResult(
            file_path=file_path,
            language="cobol",
            units=units,
            imports=[],
            package=program_id,
            raw_content=content,
            errors=errors,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_program_id(self, content: str) -> Optional[str]:
        m = _PROGRAM_ID_RE.search(content)
        return m.group(1).strip() if m else None

    def _extract_procedure_division(
        self, content: str
    ) -> Tuple[Optional[str], int]:
        """Return the text of PROCEDURE DIVISION and its starting line number."""
        m = _PROC_DIV_RE.search(content)
        if not m:
            return None, 0

        start_pos = m.start()
        start_line = content[:start_pos].count("\n") + 1

        # Look for subsequent division (DATA, ENVIRONMENT, IDENTIFICATION) to
        # know where PROCEDURE ends — rarely happens but be safe.
        end_m = re.search(
            r'^\s*(DATA|ENVIRONMENT|IDENTIFICATION)\s+DIVISION',
            content[m.end():],
            re.IGNORECASE | re.MULTILINE,
        )
        if end_m:
            proc_text = content[start_pos : m.end() + end_m.start()]
        else:
            proc_text = content[start_pos:]

        return proc_text, start_line

    def _extract_paragraphs(
        self, proc_text: str, file_path: str, base_line: int
    ) -> Dict[str, CodeUnit]:
        """Split PROCEDURE DIVISION text into paragraph CodeUnits."""
        lines = proc_text.split("\n")

        # Collect (line_index, para_name) for each paragraph header
        para_positions: List[Tuple[int, str]] = []
        for idx, line in enumerate(lines):
            # Skip comment lines (* or / in column 7 in fixed format)
            stripped = line.strip()
            if stripped.startswith("*") or stripped.startswith("/"):
                continue
            m = _PARA_HEADER_RE.match(line)
            if m:
                name = m.group(1).upper()
                # Skip DIVISION / SECTION lines caught by simpler regex
                if "DIVISION" in name or "SECTION" in name:
                    continue
                para_positions.append((idx, name))

        units: Dict[str, CodeUnit] = {}

        for i, (line_idx, para_name) in enumerate(para_positions):
            next_line_idx = (
                para_positions[i + 1][0] if i + 1 < len(para_positions) else len(lines)
            )
            para_lines = lines[line_idx:next_line_idx]
            para_code = "\n".join(para_lines)

            calls = self._extract_calls(para_code, para_name)

            unit = CodeUnit(
                name=para_name,
                code=para_code,
                language="cobol",
                file_path=file_path,
                start_line=base_line + line_idx,
                end_line=base_line + next_line_idx - 1,
                calls=calls,
                is_entry_point=False,
                is_public=True,       # All paragraphs are "public" in COBOL
                class_name=None,
                qualified_name=para_name,
            )
            units[para_name] = unit

        return units

    def _extract_calls(self, code: str, current_name: str) -> List[str]:
        calls: List[str] = []

        for m in _PERFORM_RE.finditer(code):
            target = m.group(1).upper()
            if target != current_name and target not in {"VARYING", "UNTIL", "TIMES"}:
                calls.append(target)
            thru = m.group(2)
            if thru:
                calls.append(thru.upper())

        for m in _CALL_RE.finditer(code):
            target = m.group(1).upper()
            if target != current_name:
                calls.append(target)

        return list(dict.fromkeys(calls))
