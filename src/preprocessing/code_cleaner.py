"""
Code Cleaner — Pre-LLM noise reduction.

Removes:
  • Single-line comments  (// …  and  * …  in COBOL column 7)
  • Block comments        (/* … */)
  • Javadoc               (/** … */)
  • Blank line runs       (collapses multiple blanks to one)
  • COBOL sequence numbers (columns 1–6 fixed-format)
  • Trailing whitespace

Why this matters: LLMs spend attention tokens on irrelevant explanatory
comments in old code, often more confusing than helpful.  Stripping them
before feeding context improves modernization accuracy.
"""
from __future__ import annotations

import re


class CodeCleaner:

    # ------------------------------------------------------------------
    # Java / generic
    # ------------------------------------------------------------------

    @staticmethod
    def clean_java(code: str) -> str:
        """Remove comments and normalize whitespace from Java source."""
        # Remove block comments (includes /** Javadoc */)
        code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
        # Remove line comments
        code = re.sub(r'//[^\n]*', '', code)
        # Collapse multiple blank lines
        code = re.sub(r'\n{3,}', '\n\n', code)
        # Remove trailing whitespace per line
        code = '\n'.join(line.rstrip() for line in code.splitlines())
        return code.strip()

    # ------------------------------------------------------------------
    # COBOL
    # ------------------------------------------------------------------

    @staticmethod
    def clean_cobol(code: str) -> str:
        """
        Strip COBOL comments and fixed-format sequence numbers.

        Fixed-format COBOL:
          • Columns 1-6  = sequence number (ignored)
          • Column 7     = '*' or '/' = comment line
          • Columns 8-72 = code
        """
        cleaned_lines = []
        for line in code.splitlines():
            # Fixed-format: col 7 (index 6) == '*' or '/'  → comment
            if len(line) >= 7 and line[6] in ('*', '/'):
                continue
            # Strip leading sequence numbers (6 digits)
            if len(line) >= 6 and line[:6].strip().isdigit():
                line = '       ' + line[6:]   # preserve column alignment
            # Inline comment: *> (free format) or anything after column 72
            line = re.sub(r'\*>.*$', '', line)
            if line.strip():
                cleaned_lines.append(line.rstrip())

        code = '\n'.join(cleaned_lines)
        code = re.sub(r'\n{3,}', '\n\n', code)
        return code.strip()

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def clean(self, code: str, language: str) -> str:
        if language == 'java':
            return self.clean_java(code)
        elif language == 'cobol':
            return self.clean_cobol(code)
        return code

    def clean_unit_code(self, code: str, language: str) -> str:
        """Convenience wrapper — same as clean()."""
        return self.clean(code, language)
