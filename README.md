# ⚙️ Modernization Engine

A developer tool that ingests **legacy Java & COBOL repositories** and suggests modern **Python / Go** equivalents or **Markdown documentation**, powered by the **Groq LLM API**.

The core innovation is **Context Optimization** — instead of sending entire codebases to the LLM (which causes hallucinations), the engine surgically extracts only the relevant call chain for each function, strips dead code and comments, and fits everything within a tight token budget before calling the model.

---

## Architecture

```
sample_legacy/                  ← Drop your .java / .cbl files here
src/
├── parsers/
│   ├── base_parser.py          ← CodeUnit & ParseResult dataclasses
│   ├── java_parser.py          ← Regex + brace-matching Java method extractor
│   └── cobol_parser.py         ← COBOL paragraph extractor
├── analysis/
│   ├── dependency_graph.py     ← NetworkX multi-file directed call graph
│   ├── dead_code_detector.py   ← Zero-caller unit identification
│   └── context_optimizer.py   ← ★ BFS token-budget dependency slicer
├── preprocessing/
│   └── code_cleaner.py         ← Strip comments, COBOL sequence numbers
├── llm/
│   └── groq_client.py          ← Groq API wrapper (retry + fallback model)
└── output/
    └── modernizer.py           ← Full pipeline orchestrator
app.py                          ← Streamlit 4-tab web UI
main.py                         ← Click CLI
config.py                       ← Central configuration
```

---

## Context Optimization Pipeline

```
Legacy Source Files
       │
       ▼
  [1] Parse (Java / COBOL)
       │  Extract CodeUnits (methods / paragraphs)
       │  Map call relationships
       ▼
  [2] Build Dependency Graph (NetworkX DiGraph)
       │  Nodes = qualified method names
       │  Edges = caller → callee
       ▼
  [3] Dead Code Detection
       │  Units with ZERO callers → flagged & excluded
       │  (reduces LLM distraction / hallucination)
       ▼
  [4] Context Optimizer (BFS token budget)
       │  Start from target function
       │  BFS traverse call graph (max depth = 6 hops)
       │  Greedily pack dependencies within 6,000 token budget
       │  Closest dependencies packed first
       ▼
  [5] Code Cleaner
       │  Strip all comments, Javadoc, COBOL sequence numbers
       │  Collapse blank lines
       ▼
  [6] Groq LLM (llama-3.3-70b-versatile)
       │  System prompt: strict code-only output, preserve logic
       │  Temperature: 0.1 (near-deterministic)
       │  Fallback: llama-3.1-8b-instant on context errors
       ▼
  Modernized Python / Go / Markdown Documentation
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Web UI (recommended)

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser.

**Tabs:**
| Tab | What it does |
|-----|-------------|
| 📁 Upload & Parse | Upload `.java` / `.cbl` files, see parsed units and dead code |
| 🕸️ Dependency Graph | Visual call graph (colour-coded: green=entry, blue=live, red=dead) |
| 🚀 Modernize | Select any function → see optimized context → one-click modernize |
| ⚡ Batch Modernize | Modernize all entry points at once → ZIP download |

### 3. CLI

```bash
# Modernize a specific Java method to Python
python main.py modernize --path sample_legacy/ --target main --to python

# Modernize a COBOL paragraph to Go
python main.py modernize --path sample_legacy/ --target MAIN-PARA --to go

# Generate documentation for a function
python main.py modernize --path sample_legacy/ --target calculateInterest --to documentation

# Modernize ALL entry points at once
python main.py modernize --path sample_legacy/ --to python --all-entry-points

# Show the dependency graph
python main.py graph --path sample_legacy/

# Detect dead code
python main.py dead-code --path sample_legacy/

# List all parsed code units
python main.py list-units --path sample_legacy/
```

---

## Supported Languages

| Input | Extensions |
|-------|-----------|
| Java (1.4–17) | `.java` |
| COBOL | `.cbl`, `.cob`, `.cobol` |

| Output | |
|--------|--|
| Python | Modern idiomatic Python 3.10+ |
| Go | Standard library Go |
| Documentation | Markdown with business logic explanation |

---

## Configuration (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `GROQ_API_KEY` | *(set in config)* | Your Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Primary LLM model |
| `MAX_CONTEXT_TOKENS` | `6,000` | Token budget for dependency context |
| `MAX_DEPENDENCY_DEPTH` | `6` | BFS hops through call graph |
| `OUTPUT_DIR` | `modernized_output/` | Where generated files are saved |

You can also set `GROQ_API_KEY` as an environment variable:
```bash
set GROQ_API_KEY=gsk_...
```

---

## How Hallucinations Are Minimised

| Technique | How it helps |
|-----------|-------------|
| **Dead code exclusion** | Methods never called anywhere are not shown to the LLM; stale code with misleading names or logic is filtered out |
| **Comment stripping** | Old Javadoc / COBOL inline comments often contain outdated info that contradicts actual logic; removing them forces the model to reason from code only |
| **Token budget packing** | Only the closest call-chain dependencies fit within the context window; deeply irrelevant helper code is excluded |
| **Low temperature (0.1)** | Near-deterministic output; reduces creative "invention" of non-existent APIs |
| **Structured system prompt** | Explicitly forbids the model from adding new logic or removing existing behaviour |

---

## Sample Output

**Input** (Legacy Java, `calculateInterest`):
```java
private double calculateInterest(double principal, double rate) {
    return principal * rate;
}
```

**Output** (Python):
```python
def calculate_interest(principal: float, rate: float) -> float:
    return principal * rate
```

**Output** (Go):
```go
func calculateInterest(principal, rate float64) float64 {
    return principal * rate
}
```

---

## Project Constraints Met

- ✅ Handles **multi-file dependencies** without exceeding context windows
- ✅ Minimises hallucinations via **dead code removal + comment stripping**
- ✅ Uses **Context Optimization** (BFS dependency slicing) as required
- ✅ Groq API with `llama-3.3-70b-versatile` for accurate code reasoning
- ✅ Supports both **Java** and **COBOL** legacy code
- ✅ Outputs **Python**, **Go**, or **Markdown documentation**
