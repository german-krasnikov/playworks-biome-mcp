"""PhysicsDiagnostic orchestrator: detect → classify → query lessons → report."""
from .backend_detector import detect_backend
from .knowledge_query import PhysicsKnowledge
from .symptom_classifier import SymptomClassifier


class PhysicsDiagnostic:
    def __init__(self, call_fn, sampling, store):
        self._call_fn = call_fn
        self._classifier = SymptomClassifier(sampling)
        self._knowledge = PhysicsKnowledge(store)

    async def detect(self) -> str:
        info = await detect_backend(self._call_fn)
        return info.summary()

    async def diagnose(self, symptom: str, deep: bool = False) -> str:
        info = await detect_backend(self._call_fn)
        backends = info.active_backends()
        if not backends:
            return "no physics detected — playable may not use physics"
        category, conf, keywords = await self._classifier.classify(symptom, backends)
        lines = [info.summary(), f"category={category} conf={conf:.2f}"]
        lessons_found = False
        for backend in backends:
            lessons = self._knowledge.query(backend, symptom)
            if lessons:
                lessons_found = True
                top = lessons[0]
                lines.append(f"\n[{backend}] {top.action}")
                if len(lessons) > 1:
                    lines.append(f"  ({len(lessons)} more lessons available)")
        if not lessons_found:
            lines.append("\nNo matching lessons. Try: get_console + multi-frame motion_summary")
        return "\n".join(lines)

    async def health_check(self) -> str:
        info = await detect_backend(self._call_fn)
        if not info.active_backends():
            return "OK no physics in scene"
        backends = info.active_backends()
        warnings = []
        if len(backends) > 1:
            warnings.append(f"WARNING: multiple backends active: {backends}")
        if info.goblin_bodies > 50:
            warnings.append(f"INFO: {info.goblin_bodies} Goblin bodies — review perf")
        if info.verlet_particles > 200:
            warnings.append(f"INFO: {info.verlet_particles} Verlet particles — review iterations")
        out = [info.summary()]
        out.extend(warnings)
        return "\n".join(out) if warnings else f"OK {info.summary()}"
