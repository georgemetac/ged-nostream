"""Metaculus bot package.

This package will gradually house refactored modules such as CLI, prompts, utils, etc.
"""

import asyncio
import os


def _patch_py314_nest_asyncio_task_api() -> None:
    """Restore a working task lookup under Python 3.14 + forecasting-tools' nest_asyncio patch.

    On Python 3.14, nest_asyncio patches the event loop in a way that leaves
    ``asyncio.current_task()`` returning ``None`` even when a coroutine is running,
    and ``asyncio.wait_for()`` then raises ``RuntimeError("Timeout should be used inside a task")``.
    The stdlib Python-level hook ``asyncio.tasks._py_current_task`` still reports the active task,
    so we restore that as the public task lookup before any forecasting_tools import triggers the broken patch.
    """
    py_current_task = getattr(asyncio.tasks, "_py_current_task", None)
    if py_current_task is None:
        return

    def _compat_current_task(loop=None):
        try:
            if loop is not None:
                return py_current_task(loop=loop)
            return py_current_task()
        except RuntimeError:
            return None

    asyncio.current_task = _compat_current_task
    asyncio.tasks.current_task = _compat_current_task


_patch_py314_nest_asyncio_task_api()

# Disable litellm's aiohttp transport (default since litellm v1.71.x). Under
# concurrent async bursts that transport raises near-instant connection failures
# that litellm re-wraps as a 1ms ``litellm.Timeout`` — the root cause behind the
# spurious instant-timeout incident (see litellm issue #14895 and
# ``scratch_docs_and_planning/transient_retry_fix.md``). Falling back to the
# httpx transport avoids the pathology. setdefault so an explicit env override
# (e.g. to re-enable aiohttp for testing) still wins. Must run BEFORE the first
# litellm import, though not because litellm reads the variable at import time — it
# re-reads it per transport construction, in
# ``AsyncHTTPHandler._should_use_aiohttp_transport``. What needs the ordering is the
# handful of handlers litellm builds during its OWN import (four, on 1.92.0), which
# freeze onto the aiohttp transport when the default arrives late. Hence this line
# precedes the submodule import below, which pulls forecasting_tools and thus litellm;
# tests/test_aiohttp_transport_flag.py asserts that source order.
os.environ.setdefault("DISABLE_AIOHTTP_TRANSPORT", "true")

from metaculus_bot.question_patches import apply_question_patches  # must follow the env setdefault above

apply_question_patches()
