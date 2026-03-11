"""
Modernization Engine - Configuration
Central configuration for all components.
Set GROQ_API_KEY in a .env file or as an environment variable.
"""
import os
from pathlib import Path

# Load .env file if present (without requiring python-dotenv)
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Groq API
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"   # Best open model for code reasoning
GROQ_FALLBACK_MODEL = "llama-3.1-8b-instant"  # Fast fallback

# ---------------------------------------------------------------------------
# Context Window Limits
# ---------------------------------------------------------------------------
MAX_CONTEXT_TOKENS = 6_000   # Tokens sent to LLM (well under 32k window)
MAX_OUTPUT_TOKENS = 2_048    # Tokens allowed in LLM response
PROMPT_OVERHEAD_TOKENS = 600 # Reserved for system prompt + instructions
MAX_DEPENDENCY_DEPTH = 6     # Max BFS depth when collecting dependency chain

# ---------------------------------------------------------------------------
# Analysis Settings
# ---------------------------------------------------------------------------
DEAD_CODE_CALLER_THRESHOLD = 0  # Methods with ≤ N callers → dead code candidate
ENTRY_POINT_NAMES = {"main", "run", "start", "execute", "process", "init"}

# ---------------------------------------------------------------------------
# Supported source languages
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS = {
    ".java":  "java",
    ".cbl":   "cobol",
    ".cob":   "cobol",
    ".cobol": "cobol",
    ".jcl":   "jcl",
}

# ---------------------------------------------------------------------------
# Modernization target languages
# ---------------------------------------------------------------------------
MODERNIZATION_TARGETS = ["python", "go", "documentation"]

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUTPUT_DIR = "modernized_output"
