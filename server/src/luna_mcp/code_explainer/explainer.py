"""F14: Transpiled Code Explainer — demangler + Haiku explanation."""
from __future__ import annotations

import re
from typing import Optional

_INTERNAL_RE = re.compile(r'__p__(\w+)')
_DOUBLE_DOLLAR_RE = re.compile(r'\$\$(\w+)\$(\w+)')
_SINGLE_DOLLAR_RE = re.compile(r'\$\w+\$(\w+)')

_UNITY_CALLS = {
    "GetComponent", "Instantiate", "Destroy", "SetActive",
    "GetComponentInChildren", "FindObjectOfType", "AddComponent",
}

_SYS_PROMPT = (
    "You are a C# senior developer. Given demangled Luna JS (Unity-to-JS transpiler output), "
    "produce a clean C#-style pseudocode explanation. Be concise. Focus on intent, not syntax."
)


def demangle(js_source: str, typemap) -> str:
    """Apply Tier-1 regex demangling: strip __p__ prefixes, $$ markers."""
    result = _DOUBLE_DOLLAR_RE.sub(r'\1.\2', js_source)
    result = _SINGLE_DOLLAR_RE.sub(r'\1', result)
    result = _INTERNAL_RE.sub(r'\1', result)
    return result


def explain_js(
    source: str,
    *,
    class_name: str,
    typemap,
    llm_result: Optional[str],
    method_name: Optional[str] = None,
) -> str:
    """Build explanation text from demangled JS + optional LLM output."""
    if not source or not source.strip():
        return f"No source found for class {class_name}"

    demangled = demangle(source, typemap)

    # Scope to method if requested
    if method_name:
        lines = demangled.splitlines()
        kept, in_block, depth = [], False, 0
        for line in lines:
            if method_name.lower() in line.lower() and "function" in line.lower():
                in_block = True
            if in_block:
                kept.append(line)
                depth += line.count("{") - line.count("}")
                if in_block and depth <= 0 and kept:
                    break
        if kept:
            demangled = "\n".join(kept)

    typemap_note = ""
    if typemap is None or not getattr(typemap, "available", False):
        typemap_note = "// note: no typemap — demangled with regex only\n"

    parts = [f"// Class: {class_name}"]
    if method_name:
        parts.append(f"// Method: {method_name}")
    parts.append(typemap_note + demangled)

    if llm_result:
        parts.append("\n// C# pseudocode explanation:\n" + llm_result)

    return "\n".join(parts)


class CodeExplainer:
    """Async orchestrator: fetch JS source → demangle → optional Haiku explanation."""

    def __init__(self, *, call_fn, typemap, sampling):
        self._call = call_fn
        self._typemap = typemap
        self._sampling = sampling

    async def explain(self, class_name: str, method_name: Optional[str] = None) -> str:
        js_name = None
        if self._typemap and getattr(self._typemap, "available", False):
            js_name = self._typemap.get_js_class_name(class_name)

        source = await self._call("getSourceForClass", js_name or class_name)

        if not source or not source.strip():
            return f"No source found for class {class_name}"

        demangled = demangle(source, self._typemap)

        llm_result = None
        if self._sampling and self._sampling.enabled:
            ctx = f"Class: {class_name}"
            if method_name:
                ctx += f"\nMethod: {method_name}"
            ctx += f"\n\nDemangled JS:\n{demangled[:2000]}"
            llm_result = await self._sampling.plan(demangled[:2000], _SYS_PROMPT, ctx=ctx)

        return explain_js(
            source,
            class_name=class_name,
            typemap=self._typemap,
            llm_result=llm_result,
            method_name=method_name,
        )
