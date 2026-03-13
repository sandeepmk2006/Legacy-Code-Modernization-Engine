"""
Modernization Engine - Streamlit Web UI
========================================
Run with:   streamlit run app.py
"""
from __future__ import annotations

import asyncio
import os
import io
import time
import tempfile
import zipfile
import logging
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from tornado.iostream import StreamClosedError
from tornado.websocket import WebSocketClosedError


def _install_ws_disconnect_exception_filter() -> None:
    """
    Suppress noisy websocket disconnect exceptions that happen when a browser
    tab closes or refreshes during a Streamlit update.

    This keeps expected disconnect race conditions from polluting logs while
    still surfacing all unrelated asyncio exceptions.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop_policy().get_event_loop()
        except Exception:
            return

    if loop.is_closed():
        return

    default_handler = loop.get_exception_handler()

    def _handler(current_loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        if isinstance(exc, (WebSocketClosedError, StreamClosedError)):
            logging.getLogger("streamlit.runtime").debug(
                "Ignored expected websocket disconnect exception: %s", exc
            )
            return

        if default_handler is not None:
            default_handler(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)

# ---------------------------------------------------------------------------
# Page config - must be first Streamlit call
# ---------------------------------------------------------------------------
_install_ws_disconnect_exception_filter()

st.set_page_config(
    page_title="Modernization Engine",
    page_icon="M",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Lazy imports (only after page_config)
# ---------------------------------------------------------------------------
import config
from src.parsers import JavaParser, CobolParser
from src.analysis import DependencyGraph, DeadCodeDetector, ContextOptimizer
from src.preprocessing import CodeCleaner
from src.llm import GroqClient
from src.output import Modernizer


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults = {
        "graph": None,
        "detector": None,
        "optimizer": None,
        "parse_results": {},
        "selected_target": None,
        "modernization_result": None,
        "dead_report": None,
        "batch_results": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


_init_state()


# ---------------------------------------------------------------------------
# Sidebar - Configuration
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("Modernization Engine")
    st.caption("Legacy \u2192 Modern Code via Context-Optimized LLM")

    st.divider()
    st.subheader("API Configuration")
    api_key = st.text_input(
        "Groq API Key",
        value=config.GROQ_API_KEY,
        type="password",
        help="Your Groq API key (gsk_...)",
    )

    model_choice = st.selectbox(
        "Model",
        options=["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
        index=0,
    )

    st.divider()
    st.subheader("Output Language")
    target_lang = st.radio(
        "Modernize to:",
        options=["python", "go", "documentation"],
        index=0,
        horizontal=True,
    )

    st.divider()
    st.subheader("Context Settings")
    max_tokens = st.slider(
        "Max Context Tokens",
        min_value=1_000,
        max_value=12_000,
        value=config.MAX_CONTEXT_TOKENS,
        step=500,
        help="Token budget for dependency context sent to the LLM.",
    )
    max_depth = st.slider(
        "Dependency Depth",
        min_value=1,
        max_value=8,
        value=config.MAX_DEPENDENCY_DEPTH,
        help="How many call-graph hops to traverse for context.",
    )


# ---------------------------------------------------------------------------
# Main content area - Tabs
# ---------------------------------------------------------------------------
tab_upload, tab_graph, tab_modernize, tab_batch = st.tabs([
    "Upload & Parse",
    "Dependency Graph",
    "Modernize",
    "Batch Modernize",
])


# ===========================================================================
# TAB 1: Upload & Parse
# ===========================================================================
with tab_upload:
    st.header("Step 1 - Upload Legacy Source Files")
    st.info(
        "Upload **.java** or **.cbl / .cob** files from your legacy repository. "
        "You can select multiple files at once.",
    )

    uploaded_files = st.file_uploader(
        "Select legacy source files",
        type=["java", "cbl", "cob", "cobol"],
        accept_multiple_files=True,
    )

    col1, col2 = st.columns([1, 4])
    parse_btn = col1.button("Parse Files", type="primary", disabled=not uploaded_files)

    if parse_btn and uploaded_files:
        java_parser = JavaParser()
        cobol_parser = CobolParser()
        graph = DependencyGraph()
        parse_results = {}
        errors_found = []

        progress = st.progress(0, text="Parsing files...")

        with tempfile.TemporaryDirectory() as tmpdir:
            for i, uf in enumerate(uploaded_files):
                progress.progress(
                    int((i / len(uploaded_files)) * 100),
                    text=f"Parsing {uf.name}...",
                )
                tmp_path = os.path.join(tmpdir, uf.name)
                with open(tmp_path, "wb") as fh:
                    fh.write(uf.getvalue())

                ext = Path(uf.name).suffix.lower()
                try:
                    if ext == ".java":
                        result = java_parser.parse_file(tmp_path)
                    else:
                        result = cobol_parser.parse_file(tmp_path)
                    parse_results[uf.name] = result
                    graph.add_parse_result(result)
                    if result.errors:
                        errors_found.extend(result.errors)
                except Exception as exc:
                    errors_found.append(f"{uf.name}: {exc}")

        graph.finalize()
        detector = DeadCodeDetector(graph)
        optimizer = ContextOptimizer(graph, detector, max_tokens=max_tokens, max_depth=max_depth)

        st.session_state["graph"] = graph
        st.session_state["detector"] = detector
        st.session_state["optimizer"] = optimizer
        st.session_state["parse_results"] = parse_results
        st.session_state["dead_report"] = detector.report()

        progress.progress(100, text="Done!")
        time.sleep(0.3)
        progress.empty()

        st.success(
            f"Parsed **{len(parse_results)}** file(s) - "
            f"found **{graph.node_count()}** code units, "
            f"**{graph.edge_count()}** call edges.",
        )

        if errors_found:
            with st.expander("Parse warnings"):
                for e in errors_found:
                    st.warning(e)

    # Show parsed file summaries
    if st.session_state["parse_results"]:
        st.divider()
        st.subheader("Parsed Files")

        for fname, result in st.session_state["parse_results"].items():
            with st.expander(f"{fname}  ({result.language.upper()} - {len(result.units)} units)"):
                rows = []
                for uname, unit in result.units.items():
                    rows.append({
                        "Unit": unit.qualified_name or unit.name,
                        "Lines": f"{unit.start_line}-{unit.end_line}",
                        "Calls": ", ".join(unit.calls[:5]) + ("..." if len(unit.calls) > 5 else ""),
                        "Entry?": "Yes" if unit.is_entry_point else "",
                        "Public?": "Yes" if unit.is_public else "",
                    })
                if rows:
                    st.dataframe(rows, width='stretch')

        # Dead code section
        if st.session_state["dead_report"]:
            dead = st.session_state["dead_report"]["dead"]
            st.divider()
            st.subheader(f"Dead Code Detection - {len(dead)} unreachable unit(s)")
            if dead:
                st.write(
                    "These units have **zero callers** and are excluded from "
                    "the LLM context to reduce hallucinations."
                )
                cols = st.columns(3)
                for i, name in enumerate(dead):
                    cols[i % 3].markdown(f"- `{name}`")
            else:
                st.success("No dead code detected.")


# ===========================================================================
# TAB 2: Dependency Graph
# ===========================================================================
with tab_graph:
    st.header("Step 2 - Dependency Graph")

    graph: Optional[DependencyGraph] = st.session_state["graph"]

    if graph is None:
        st.info("Parse files first in the **Upload & Parse** tab.")
    else:
        st.caption(graph.summary())
        adj = graph.to_dict()

        # Visual Graph
        st.subheader("Visual Call Graph")
        try:
            import networkx as nx

            nx_graph = nx.DiGraph()
            dead_set = set(st.session_state["dead_report"]["dead"]) if st.session_state["dead_report"] else set()

            for caller, callees in adj.items():
                nx_graph.add_node(caller)
                for callee in callees:
                    nx_graph.add_edge(caller, callee)

            fig, ax = plt.subplots(figsize=(14, 8))
            fig.patch.set_facecolor("#0e1117")
            ax.set_facecolor("#0e1117")

            try:
                pos = nx.nx_agraph.graphviz_layout(nx_graph, prog="dot")
            except Exception:
                try:
                    pos = nx.planar_layout(nx_graph)
                except Exception:
                    pos = nx.spring_layout(nx_graph, seed=42, k=2.5)

            entry_pts = set(graph.get_entry_points())
            node_colors = []
            for n in nx_graph.nodes:
                if n in dead_set:
                    node_colors.append("#e74c3c")
                elif n in entry_pts:
                    node_colors.append("#2ecc71")
                else:
                    node_colors.append("#3498db")

            nx.draw_networkx_nodes(nx_graph, pos, node_color=node_colors,
                                   node_size=800, ax=ax, alpha=0.9)
            nx.draw_networkx_edges(nx_graph, pos, ax=ax,
                                   edge_color="#7f8c8d", arrows=True,
                                   arrowsize=15, width=1.2,
                                   connectionstyle="arc3,rad=0.1")
            labels = {n: n.split(".")[-1] for n in nx_graph.nodes}
            nx.draw_networkx_labels(nx_graph, pos, labels=labels,
                                    font_size=7, font_color="white", ax=ax)

            legend = [
                mpatches.Patch(color="#2ecc71", label="Entry Point"),
                mpatches.Patch(color="#3498db", label="Live Code"),
                mpatches.Patch(color="#e74c3c", label="Dead Code (excluded)"),
            ]
            ax.legend(handles=legend, loc="upper right",
                      facecolor="#1a1a2e", labelcolor="white", fontsize=9)
            ax.set_title("Call Dependency Graph", color="white", fontsize=13)
            ax.axis("off")
            plt.tight_layout()

            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                        facecolor=fig.get_facecolor())
            buf.seek(0)
            st.image(buf, width='stretch')
            plt.close(fig)

            st.download_button("Download graph image", buf.getvalue(),
                               "call_graph.png", "image/png")
        except Exception as exc:
            st.warning(f"Visual graph unavailable: {exc}. Showing table instead.")

        st.divider()

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Adjacency Table")
            rows = []
            for caller, callees in adj.items():
                for callee in callees:
                    rows.append({"Caller": caller, "Calls": callee})
            if rows:
                st.dataframe(rows, width='stretch', height=380)
            else:
                st.write("No edges found.")

        with col_b:
            st.subheader("Transitive Dependencies Explorer")
            all_units = list(graph.get_all_units().keys())
            selected = st.selectbox(
                "Select a function:",
                options=sorted(all_units),
                key="dep_explorer",
            )
            if selected:
                depth_val = st.slider("Max depth", 1, 8, max_depth, key="dep_depth_slider")
                deps = graph.get_transitive_deps(selected, max_depth=depth_val)
                callers = graph.get_callers(selected)

                st.markdown(f"**Direct callees:** {', '.join(graph.get_callees(selected)) or 'none'}")
                st.markdown(f"**Called by:** {', '.join(callers) or 'none (entry point)'}")
                st.markdown(f"**All transitive deps ({len(deps)}):**")
                if deps:
                    col1, col2, col3 = st.columns(3)
                    for i, dep in enumerate(sorted(deps)):
                        [col1, col2, col3][i % 3].markdown(f"- `{dep}`")
                else:
                    st.write("No transitive dependencies.")

        st.divider()
        with st.expander("Export as Graphviz DOT"):
            dot_lines = ["digraph CallGraph {", '  rankdir=LR;',
                         '  node [style=filled fontname="Helvetica"];']
            dead_set2 = set(st.session_state["dead_report"]["dead"]) if st.session_state["dead_report"] else set()
            entry_set2 = set(graph.get_entry_points())
            for node in graph.get_all_units():
                sn = node.replace(".", "_").replace("-", "_")
                if node in dead_set2:
                    dot_lines.append(f'  "{sn}" [fillcolor=red fontcolor=white label="{node.split(".")[-1]}"];')
                elif node in entry_set2:
                    dot_lines.append(f'  "{sn}" [fillcolor=green label="{node.split(".")[-1]}"];')
                else:
                    dot_lines.append(f'  "{sn}" [fillcolor=lightblue label="{node.split(".")[-1]}"];')
            for caller, callees in adj.items():
                for callee in callees:
                    sc = caller.replace(".", "_").replace("-", "_")
                    se = callee.replace(".", "_").replace("-", "_")
                    dot_lines.append(f'  "{sc}" -> "{se}";')
            dot_lines.append("}")
            dot_text = "\n".join(dot_lines)
            st.code(dot_text, language="dot")
            st.download_button("Download .dot file", dot_text, "call_graph.dot", "text/plain")


# ===========================================================================
# TAB 3: Modernize
# ===========================================================================
with tab_modernize:
    st.header("Step 3 - Modernize with Context Optimization")

    optimizer: Optional[ContextOptimizer] = st.session_state["optimizer"]

    if optimizer is None:
        st.info("Parse files first in the **Upload & Parse** tab.")
    else:
        graph2: DependencyGraph = st.session_state["graph"]
        all_units_list = sorted(graph2.get_all_units().keys())

        st.subheader("Select Target Function / Paragraph")
        target_name = st.selectbox(
            "Function to modernize:",
            options=all_units_list,
        )

        if target_name:
            ctx = optimizer.optimize(target_name)

            if ctx is None:
                st.error(f"Unit '{target_name}' not found in the dependency graph.")
            else:
                summary = ctx.summary()

                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Context Tokens", f"{summary['total_tokens']:,}")
                col2.metric("Dependencies Included", summary["dependencies_included"])
                col3.metric("Dead Code Excluded", summary["excluded_dead_code"])
                col4.metric("Budget-trimmed", summary["excluded_budget_limit"])

                with st.expander("Preview context block sent to LLM", expanded=False):
                    cleaner = CodeCleaner()
                    unit = ctx.target_unit
                    cleaned = cleaner.clean(unit.code, unit.language)
                    st.code(cleaned, language=unit.language if unit.language != "cobol" else "text")

                    if ctx.dependency_units:
                        for dep_unit, depth in ctx.dependency_units:
                            st.markdown(f"**{depth}-hop dep: `{dep_unit.name}`**")
                            dep_cleaned = cleaner.clean(dep_unit.code, dep_unit.language)
                            st.code(dep_cleaned, language=dep_unit.language if dep_unit.language != "cobol" else "text")

                st.divider()

                col_orig, col_modern = st.columns(2)

                with col_orig:
                    st.subheader("Original Code")
                    st.code(
                        ctx.target_unit.code,
                        language=ctx.target_unit.language if ctx.target_unit.language != "cobol" else "text",
                    )

                modernize_btn = st.button(
                    f"Modernize to {target_lang.upper()}",
                    type="primary",
                    key="modernize_btn",
                )

                if modernize_btn:
                    with st.spinner(f"Calling Groq ({model_choice})... this may take 10-30 s"):
                        try:
                            llm = GroqClient(api_key=api_key, model=model_choice)
                            modernizer = Modernizer(groq_client=llm)
                            result = modernizer.run(ctx, target_language=target_lang, save_to_disk=False)
                            st.session_state["modernization_result"] = result
                        except Exception as exc:
                            st.error(f"Error: {exc}")
                            st.session_state["modernization_result"] = None

                result = st.session_state.get("modernization_result")
                if result and result.target_name and target_name in result.target_name:
                    if result.success:
                        with col_modern:
                            lang_map = {"python": "python", "go": "go", "documentation": "markdown"}
                            st.subheader(f"Modernized ({target_lang.upper()})")
                            st.code(
                                result.modernized_code,
                                language=lang_map.get(target_lang, "text"),
                            )

                        ext = result.file_extension()
                        st.download_button(
                            f"Download modernized file ({ext})",
                            data=result.modernized_code,
                            file_name=f"{result.target_name.replace('.', '_')}{ext}",
                            mime="text/plain",
                        )
                    elif result.error:
                        st.error(f"Modernization failed: {result.error}")


# ===========================================================================
# TAB 4: Batch Modernize
# ===========================================================================
with tab_batch:
    st.header("Step 4 - Batch Modernize")

    optimizer_b: Optional[ContextOptimizer] = st.session_state["optimizer"]

    if optimizer_b is None:
        st.info("Parse files first in the **Upload & Parse** tab.")
    else:
        graph_b: DependencyGraph = st.session_state["graph"]
        entry_pts = graph_b.get_entry_points()
        all_unit_keys = list(graph_b.get_all_units().keys())

        # --- Mode toggle ---------------------------------------------------
        all_units_mode = st.toggle(
            "Modernize All Units (not just entry points)",
            value=False,
            help=(
                "When ON, every function and paragraph in the dependency graph "
                "is modernized (Full Project Mode). "
                "When OFF, only the detected entry points are modernized."
            ),
        )

        if all_units_mode:
            batch_targets = all_unit_keys
            st.info(
                f"**Full Project Mode** — {len(batch_targets)} unit(s) will be modernized. "
                "Each unit's context is independently optimized via the ContextOptimizer.",
            )
        else:
            batch_targets = entry_pts
            st.info(
                f"Found **{len(entry_pts)}** entry point(s): "
                + (", ".join(f"`{e}`" for e in entry_pts) if entry_pts else "_none_"),
            )

        col_bl, col_br = st.columns(2)
        batch_lang = col_bl.radio(
            "Batch output language:",
            options=["python", "go", "documentation"],
            index=0,
            horizontal=True,
            key="batch_lang",
        )

        mode_label = "All Units" if all_units_mode else "Entry Points"
        batch_btn = col_br.button(
            f"Modernize {mode_label} to {batch_lang.upper()}",
            type="primary",
            key="batch_btn",
            disabled=not batch_targets,
        )

        if batch_btn:
            batch_results = []
            progress_b = st.progress(0, text="Starting batch modernization...")
            llm_b = GroqClient(api_key=api_key, model=model_choice)
            modernizer_b = Modernizer(groq_client=llm_b)

            for i, ep in enumerate(batch_targets):
                progress_b.progress(
                    int((i / len(batch_targets)) * 100),
                    text=f"Modernizing {ep} ({i+1}/{len(batch_targets)})...",
                )
                ctx_b = optimizer_b.optimize(ep)
                if ctx_b:
                    try:
                        res = modernizer_b.run(ctx_b, target_language=batch_lang, save_to_disk=True)
                        batch_results.append(res)
                    except Exception as exc:
                        from src.output.modernizer import ModernizationResult
                        batch_results.append(ModernizationResult(
                            target_name=ep, source_language="unknown",
                            target_language=batch_lang, original_code="",
                            modernized_code="", error=str(exc),
                        ))

            progress_b.progress(100, text="Done!")
            time.sleep(0.3)
            progress_b.empty()
            st.session_state["batch_results"] = batch_results

        batch_results = st.session_state.get("batch_results", [])
        if batch_results:
            lang_map_b = {"python": "python", "go": "go", "documentation": "markdown"}
            successful = [r for r in batch_results if r.success]
            failed = [r for r in batch_results if not r.success]

            col_s, col_f = st.columns(2)
            col_s.metric("Successful", len(successful))
            col_f.metric("Failed", len(failed))

            for i, res in enumerate(batch_results):
                ext_b = res.file_extension()
                status = "SUCCESS" if res.success else "FAILED"
                with st.expander(f"{status} {res.target_name}{ext_b}"):
                    if res.success:
                        st.code(
                            res.modernized_code,
                            language=lang_map_b.get(batch_lang, "text"),
                        )
                        if res.output_file:
                            st.caption(f"Saved to: `{res.output_file}`")
                        st.download_button(
                            f"Download {ext_b}",
                            data=res.modernized_code,
                            file_name=f"{res.target_name.replace('.','_')}{ext_b}",
                            mime="text/plain",
                            key=f"dl_{i}_{res.target_name}",
                        )
                    else:
                        st.error(f"Error: {res.error}")

            if successful:
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for res in successful:
                        ext_b = res.file_extension()
                        fname = f"{res.target_name.replace('.','_')}{ext_b}"
                        zf.writestr(fname, res.modernized_code)
                zip_buf.seek(0)
                st.download_button(
                    "Download all as ZIP",
                    data=zip_buf.getvalue(),
                    file_name="modernized_batch.zip",
                    mime="application/zip",
                )


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.divider()
st.caption(
    "Modernization Engine  |  Context Optimization powered by Groq LLM  |  "
    "Supports Java & COBOL  |  Outputs Python, Go, or Markdown docs"
)