"""Path shim — makes the hyphenated `ai-models/` dir importable under the
Python-legal names `ai_models` and `ai_model_interfaces`.

The repo deliberately keeps AI model code under a top-level `ai-models/` folder
(a hyphenated name Python cannot import directly). Phase 1's interface ABCs live
in `ai-models/interfaces/detector.py` and the concrete `OpenCVInpainter` lives
in `ai-models/inpainting/opencv_inpainter.py`; both import `from
ai_model_interfaces.detector import ...`. This shim honours that contract by
registering the real folders under the alias names so the worker task can do
`from ai_models.inpainting.opencv_inpainter import OpenCVInpainter` and the
inpainter's own `ai_model_interfaces` import resolves.

Importing this module is idempotent. Heavy deps inside the registered submodules
(opencv, numpy) are imported lazily by the leaf files, so installing the alias
on a 32-bit box without those wheels still succeeds.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_AI_MODELS = _REPO_ROOT / "ai-models"


def _register(alias: str, path: Path) -> None:
    if alias in sys.modules:
        return
    init = path / "__init__.py"
    if not init.exists():
        return
    spec = importlib.util.spec_from_file_location(
        alias, init, submodule_search_locations=[str(path)]
    )
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)  # __init__ re-exports are seed-only; no heavy deps here


def install() -> None:
    _register("ai_models", _AI_MODELS)
    _register("ai_model_interfaces", _AI_MODELS / "interfaces")
    _register("ai_models.inpainting", _AI_MODELS / "inpainting")
    _register("ai_models.interfaces", _AI_MODELS / "interfaces")
    _register("ai_models.detection", _AI_MODELS / "detection")
    _register("ai_models.tracking", _AI_MODELS / "tracking")
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))


install()
