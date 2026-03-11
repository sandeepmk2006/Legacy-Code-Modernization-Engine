"""
Base parser abstractions shared by all language parsers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CodeUnit:
    """Represents one discrete callable unit: a Java method or COBOL paragraph."""

    name: str                        # Simple name  (e.g. "calculateInterest")
    code: str                        # Raw source text
    language: str                    # 'java' | 'cobol'
    file_path: str
    start_line: int = 0
    end_line: int = 0
    calls: List[str] = field(default_factory=list)   # Names of units this unit calls
    is_entry_point: bool = False     # main(), public COBOL entry, etc.
    is_public: bool = False
    class_name: Optional[str] = None # Owning Java class (if applicable)
    qualified_name: Optional[str] = None  # e.g. "CustomerProcessor.calculateInterest"


@dataclass
class ParseResult:
    """Aggregated output from parsing a single source file."""

    file_path: str
    language: str
    units: Dict[str, CodeUnit]       # simple_name -> CodeUnit
    imports: List[str] = field(default_factory=list)
    package: Optional[str] = None
    raw_content: str = ""
    errors: List[str] = field(default_factory=list)


class BaseParser(ABC):
    """All language parsers must implement this interface."""

    @abstractmethod
    def parse_file(self, file_path: str) -> ParseResult:
        """Parse a source file and return structured CodeUnits."""

    @abstractmethod
    def supports(self, file_extension: str) -> bool:
        """Return True if this parser handles the given file extension."""
