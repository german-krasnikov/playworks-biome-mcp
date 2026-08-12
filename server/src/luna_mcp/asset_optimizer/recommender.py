"""Heuristic asset recommender — no external deps."""
from __future__ import annotations

from dataclasses import dataclass

from .catalog import Asset
from .texture_analyzer import TextureAnalyzer, TextureInfo


@dataclass
class AssetAction:
    asset_path: str
    action: str            # compress_jpeg|compress_webp|keep
    reason: str
    est_save_kb: int
    risk: str              # low|med|high
    webp_estimate_bytes: int = 0   # C2(c): Pillow in-process WEBP size
    real_probe_bytes: int = 0      # C2(b): ground-truth from cwebp/pngquant


class Recommender:
    def __init__(self, analyzer: TextureAnalyzer, probe=None):
        self._analyzer = analyzer
        self._probe = probe  # CompressionProbe | None

    def recommend_textures(self, assets: list[Asset], target_size_kb: int) -> list[AssetAction]:
        candidates: list[AssetAction] = []
        for a in assets:
            if a.kind != "texture":
                continue
            info = self._analyzer.analyze(a.abs_path)
            candidates.extend(self._actions_for(a, info))
        # greedy: biggest save first, stop when target reached
        candidates.sort(key=lambda x: x.est_save_kb, reverse=True)
        plan: list[AssetAction] = []
        running = 0
        for act in candidates:
            plan.append(act)
            running += act.est_save_kb
            if running >= target_size_kb:
                break
        return plan

    def _actions_for(self, asset: Asset, info: TextureInfo) -> list[AssetAction]:
        """Return all applicable actions for a texture asset."""
        size_kb = asset.size // 1024
        actions: list[AssetAction] = []
        if info.classification == "glyph":
            return actions
        # Downscale gate: emit before compress so caller sees both
        if max(info.width, info.height) > 1024:
            scale = 1024 / max(info.width, info.height)
            new_pixels = max(1, int(info.width * scale) * int(info.height * scale))
            area_ratio = new_pixels / max(info.pixels, 1)
            ds_save = max(1, int(size_kb * (1.0 - area_ratio)))
            actions.append(AssetAction(asset.path, "downscale",
                                       f"max dim {max(info.width, info.height)}px > 1024",
                                       ds_save, "med"))
        compress = self._compress_action(asset, info, size_kb)
        if compress:
            actions.append(self._enrich(compress, asset.abs_path))
        return actions

    def _compress_action(self, asset: Asset, info: TextureInfo, size_kb: int) -> AssetAction | None:
        if info.classification == "photo" and size_kb > 50:
            return AssetAction(asset.path, "compress_jpeg",
                               "photo: lossy 70% acceptable",
                               int(size_kb * 0.6), "low")
        if info.classification == "sprite" and size_kb > 30:
            return AssetAction(asset.path, "compress_webp",
                               "sprite: webp lossless",
                               int(size_kb * 0.3), "low")
        if info.classification == "ui" and size_kb > 20:
            return AssetAction(asset.path, "compress_webp",
                               "ui: webp lossless",
                               int(size_kb * 0.2), "med")
        return None

    def _enrich(self, act: AssetAction, abs_path: str) -> AssetAction:
        """Add Pillow cheap-tier estimate and real probe bytes when available."""
        act.webp_estimate_bytes = self._analyzer.estimate_webp_size(abs_path)
        if self._probe is not None:
            if act.action in ("compress_webp", "compress_jpeg"):
                act.real_probe_bytes = self._probe.probe_webp(abs_path)
        return act
