"""
This is a suprise tool that will help us later.
"""

import functools
import gc
from collections.abc import Callable  # noqa: TC003


def get_lru_cache_inputs(func: Callable[..., object]) -> list[tuple[object, ...]] | None:
    # The lru cache __dict__ doesn't actually have a corresponding parameter, so we have to use gc to find it
    for referent in gc.get_referents(func):  # pyright: ignore[reportAny]
        # We know we've found it if it has a value of type functools._lru_cache_wrapper
        if isinstance(referent, dict) and isinstance(next(iter(referent.values()), None), functools._lru_cache_wrapper):  # pyright: ignore[reportPrivateUsage, reportUnknownArgumentType]  # noqa: SLF001
            return [*referent.keys()]
    return None
