"""Starter patch templates for common build size reductions."""
from typing import Optional

from .patch_dsl import PatchOp

TEMPLATE_LOWER_JPEG = PatchOp(
    id="lower_jpeg_quality",
    intent="lower JPEG quality from 85 to 65",
    search="quality: 85",
    replace="quality: 65",
    expected_count=1,
    anchor_before="jpeg",
    max_distance=300,
)

TEMPLATE_DISABLE_PC_MODULES = PatchOp(
    id="disable_pc_modules_default",
    intent="disable particle, audio, xr modules",
    search='"pc.ParticleEmitter"',
    replace='"pc.ParticleEmitterStub"',
    expected_count=1,
    anchor_before="engine/scripts",
    max_distance=500,
)

TEMPLATE_COMPRESS_WEBP = PatchOp(
    id="compress_textures_webp",
    intent="enable WebP texture compression",
    search="useWebP: false",
    replace="useWebP: true",
    expected_count=1,
    anchor_before="texture",
    max_distance=300,
)

TEMPLATE_ASYNC_ASSETS = PatchOp(
    id="enable_async_assets",
    intent="enable async asset loading",
    search="asyncLoad: false",
    replace="asyncLoad: true",
    expected_count=1,
    anchor_before="assets",
    max_distance=300,
)

TEMPLATES: dict = {
    "lower_jpeg_quality": TEMPLATE_LOWER_JPEG,
    "disable_pc_modules_default": TEMPLATE_DISABLE_PC_MODULES,
    "compress_textures_webp": TEMPLATE_COMPRESS_WEBP,
    "enable_async_assets": TEMPLATE_ASYNC_ASSETS,
}


def get_template(name: str) -> Optional[PatchOp]:
    return TEMPLATES.get(name)


def list_templates() -> list:
    return sorted(TEMPLATES.keys())
