"""Phase 0 seam check: the business-logic modules must import without dragging in Telegram.

This is the invariant the Mini App plan rests on (docs/mini-app-analysis.md §1): the API
tier reuses these modules directly, so they must stay free of any `telegram` dependency.
"""

from __future__ import annotations

import importlib
import sys

REUSABLE_MODULES = [
    "writer_ai_assistant.config",
    "writer_ai_assistant.prompt_builder",
    "writer_ai_assistant.openai_service",
    "writer_ai_assistant.templates",
    "writer_ai_assistant.rate_limit",
    "writer_ai_assistant.text_utils",
    "writer_ai_assistant.preferences",
]


def test_reusable_modules_do_not_import_telegram() -> None:
    for name in list(sys.modules):
        if name == "telegram" or name.startswith("telegram."):
            del sys.modules[name]

    for module_name in REUSABLE_MODULES:
        importlib.import_module(module_name)

    leaked = [n for n in sys.modules if n == "telegram" or n.startswith("telegram.")]
    assert not leaked, f"reusable modules pulled in Telegram: {leaked}"
