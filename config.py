"""
Modernization Engine - Configuration
Central configuration for all components.
Set GROQ_API_KEY in a .env file or as an environment variable.
"""
import os
from pathlib import Path


def _load_env_file(env_file: Path) -> None:
    """Load KEY=VALUE pairs from an env file without external deps."""
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


# Load .env first; if absent, allow .env.example as a fallback for local runs.
_project_root = Path(__file__).parent
_load_env_file(_project_root / ".env")
_load_env_file(_project_root / ".env.example")

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
