# Modernization Engine

Modernization Engine analyzes legacy Java and COBOL code, builds a dependency-aware context, and generates modern output with Groq LLMs.

Supported targets:
- Python
- Go
- Markdown documentation

The key idea is context optimization: instead of sending the entire codebase to the LLM, it sends only the most relevant units (target + nearby dependencies) within a token budget.

## Features

- Java and COBOL parsing
- Multi-file call graph generation
- Dead-code detection (zero-caller units)
- Token-budget context slicing (BFS by dependency depth)
- Comment/format cleanup before LLM calls
- Streamlit web app and Click CLI

## Project Structure

```text
sample_legacy/                  # Sample input files
src/
  parsers/                      # Java/COBOL parsing into code units
  analysis/                     # Graph, dead-code detection, context optimization
  preprocessing/                # Comment and noise cleanup
  llm/                          # Groq client wrapper
  output/                       # Orchestration and output writing
app.py                          # Streamlit UI
main.py                         # CLI entry point
config.py                       # Configuration
```

## Requirements

- Python 3.10+
- A Groq API key

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure API Key

Use one of the following:

1. Environment variable (Linux/macOS):

```bash
export GROQ_API_KEY="gsk_..."
```

2. Local `.env` file in the project root:

```env
GROQ_API_KEY=gsk_...
```

## Run the Web UI

```bash
streamlit run app.py
```

Open `http://localhost:8501`.

Main tabs:
- `Upload & Parse`: inspect parsed units and dead-code candidates
- `Dependency Graph`: visualize caller/callee relationships
- `Modernize`: modernize a selected target with optimized context
- `Batch Modernize`: modernize multiple entry points and download results

## Run the CLI

```bash
# Modernize one target
python main.py modernize --path sample_legacy/ --target calculateInterest --to python

# Modernize all entry points
python main.py modernize --path sample_legacy/ --to go --all-entry-points

# Full-project mode: modernize all discovered units
python main.py modernize --path sample_legacy/ --to python --all-units

# Generate documentation
python main.py modernize --path sample_legacy/ --target MAIN-PARA --to documentation

# Show dependency graph
python main.py graph --path sample_legacy/

# Detect dead code
python main.py dead-code --path sample_legacy/

# List parsed units
python main.py list-units --path sample_legacy/
```

## Supported Inputs and Outputs

Input extensions:
- `.java`
- `.cbl`, `.cob`, `.cobol`
- `.jcl` (treated as COBOL-family input by current parser pipeline)

Output types:
- Python source
- Go source
- Markdown documentation

## How Context Optimization Works

1. Parse source files into code units (methods/paragraphs).
2. Build a directed call graph.
3. Detect and mark dead units.
4. Start from the target and collect nearest dependencies by BFS depth.
5. Fit context into token budget (`MAX_CONTEXT_TOKENS`).
6. Clean code snippets and send optimized context to Groq.

This reduces irrelevant prompt noise and helps lower hallucination risk.

## Configuration Reference

Key settings in `config.py`:
- `GROQ_MODEL`, `GROQ_FALLBACK_MODEL`
- `MAX_CONTEXT_TOKENS`, `MAX_DEPENDENCY_DEPTH`
- `SUPPORTED_EXTENSIONS`
- `OUTPUT_DIR`

## Output Location

Generated files are written to `modernized_output/` by default.

## Troubleshooting

- `No supported files found`: verify `--path` and file extensions.
- API/auth errors: confirm `GROQ_API_KEY` is set.
- Empty graph or missing target: run `list-units` to confirm parsed names.
