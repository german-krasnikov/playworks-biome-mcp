"""F14: Transpiled Code Explainer tools."""
from __future__ import annotations

from ..code_explainer.explainer import CodeExplainer
from . import maybe_expose


def register_explainer_tools(mcp, call_fn, *, typemap, sampling, exposed: set = frozenset()):
    """Register explain_code (exposed) and explain_function (batch-only)."""
    _explainer = CodeExplainer(call_fn=call_fn, typemap=typemap, sampling=sampling)

    async def explain_code(class_name: str) -> str:
        """Explain a transpiled Luna class in human-readable C#-style pseudocode."""
        return await _explainer.explain(class_name)
    maybe_expose(mcp, explain_code, exposed)

    async def explain_function(class_name: str, method_name: str) -> str:
        """Explain a single method of a transpiled Luna class."""
        return await _explainer.explain(class_name, method_name=method_name)
    maybe_expose(mcp, explain_function, exposed)

    return {
        "explain_code": (explain_code, None),
        "explain_function": (explain_function, None),
    }
