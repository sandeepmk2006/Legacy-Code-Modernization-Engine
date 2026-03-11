"""
Java source parser.

Uses regex + brace-matching to extract methods from .java files without
requiring a full JVM or tree-sitter native binary. Handles legacy Java 1.4–8.
"""
import re
import os
from typing import Dict, List, Optional, Tuple

from .base_parser import BaseParser, CodeUnit, ParseResult


# Keywords that look like method calls but are control-flow constructs
_CONTROL_KEYWORDS = frozenset({
    "if", "for", "while", "switch", "catch", "try", "else", "new",
    "return", "throw", "assert", "synchronized", "finally", "super",
    "this", "do", "case", "default", "instanceof", "import", "package",
    "class", "interface", "enum", "extends", "implements", "throws",
})

# Regex: matches a method/constructor signature up to its opening brace
_METHOD_RE = re.compile(
    r'(?:(?:(?:public|private|protected|static|final|synchronized|'
    r'abstract|native|default|transient|volatile)\s+)*)'   # modifiers
    r'(?:(?:void|int|long|double|float|boolean|char|byte|short'
    r'|String|List|Map|Set|Optional|Object|[\w<>\[\],\s]+?)\s+)?'  # return type (optional for constructors)
    r'(\b[a-zA-Z_]\w*)\s*'                                 # method/ctor name  (group 1)
    r'\([^)]{0,300}\)\s*'                                   # parameter list (up to 300 chars)
    r'(?:throws\s+[\w,\s]+\s*)?'                            # optional throws
    r'\{',                                                  # opening brace
    re.MULTILINE,
)

_PACKAGE_RE  = re.compile(r'^\s*package\s+([\w.]+)\s*;',   re.MULTILINE)
_IMPORT_RE   = re.compile(r'^\s*import\s+([\w.*]+)\s*;',   re.MULTILINE)
_CLASS_RE    = re.compile(r'\b(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+([A-Z]\w+)')
_CALL_RE     = re.compile(r'\b([a-z_]\w*)\s*\(')            # lower-case = method call heuristic


class JavaParser(BaseParser):
    """Regex-based Java parser that extracts method CodeUnits."""

    def supports(self, file_extension: str) -> bool:
        return file_extension.lower() == ".java"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, file_path: str) -> ParseResult:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()

        package = None
        pkg_m = _PACKAGE_RE.search(content)
        if pkg_m:
            package = pkg_m.group(1)

        imports = _IMPORT_RE.findall(content)
        class_name = self._extract_class_name(content)
        units = self._extract_methods(content, file_path, class_name)

        return ParseResult(
            file_path=file_path,
            language="java",
            units=units,
            imports=imports,
            package=package,
            raw_content=content,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_class_name(self, content: str) -> Optional[str]:
        m = _CLASS_RE.search(content)
        return m.group(1) if m else None

    def _extract_methods(
        self, content: str, file_path: str, class_name: Optional[str]
    ) -> Dict[str, CodeUnit]:
        units: Dict[str, CodeUnit] = {}

        for match in _METHOD_RE.finditer(content):
            method_name = match.group(1)
            if method_name in _CONTROL_KEYWORDS:
                continue

            open_brace = match.end() - 1
            close_brace = self._find_matching_brace(content, open_brace)
            if close_brace == -1:
                continue

            sig_start = match.start()
            method_code = content[sig_start : close_brace + 1]
            start_line = content[:sig_start].count("\n") + 1
            end_line = content[:close_brace].count("\n") + 1

            sig_text = match.group(0)
            is_public = bool(re.search(r"\bpublic\b",  sig_text))
            is_static = bool(re.search(r"\bstatic\b",  sig_text))
            is_main   = (
                method_name == "main" and is_public and is_static
            )

            calls = self._extract_calls(method_code, method_name)

            qualified = (
                f"{class_name}.{method_name}" if class_name else method_name
            )

            unit = CodeUnit(
                name=method_name,
                code=method_code,
                language="java",
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                calls=calls,
                is_entry_point=is_main,
                is_public=is_public,
                class_name=class_name,
                qualified_name=qualified,
            )
            # Avoid overwriting earlier occurrence with same simple name
            units.setdefault(method_name, unit)

        return units

    def _find_matching_brace(self, content: str, open_pos: int) -> int:
        """Walk forward from `open_pos` (which must be '{') and return the
        index of the matching '}'.  Respects strings, chars, and comments."""
        depth = 0
        i = open_pos
        in_string = in_char = in_line_comment = in_block_comment = False
        n = len(content)

        while i < n:
            ch = content[i]

            if in_line_comment:
                if ch == "\n":
                    in_line_comment = False
            elif in_block_comment:
                if ch == "*" and i + 1 < n and content[i + 1] == "/":
                    in_block_comment = False
                    i += 1
            elif in_string:
                if ch == "\\" :
                    i += 1          # skip escaped char
                elif ch == '"':
                    in_string = False
            elif in_char:
                if ch == "\\":
                    i += 1
                elif ch == "'":
                    in_char = False
            else:
                if ch == "/" and i + 1 < n:
                    nxt = content[i + 1]
                    if nxt == "/":
                        in_line_comment = True; i += 1
                    elif nxt == "*":
                        in_block_comment = True; i += 1
                elif ch == '"':
                    in_string = True
                elif ch == "'":
                    in_char = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return i
            i += 1

        return -1   # unmatched

    def _extract_calls(self, code: str, current_name: str) -> List[str]:
        """Return list of (lower-case-starting) method names called in *code*."""
        calls = [
            m.group(1) for m in _CALL_RE.finditer(code)
            if m.group(1) not in _CONTROL_KEYWORDS
            and m.group(1) != current_name
        ]
        return list(dict.fromkeys(calls))   # deduplicate while preserving order
