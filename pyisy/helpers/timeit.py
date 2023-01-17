"""Helpers for testing performance during development."""

from collections.abc import Callable
from functools import wraps
import logging
import time
from typing import TypeVar

_LOGGER = logging.getLogger(__name__)

RT = TypeVar("RT")  # return type


def timeit(func: Callable[..., RT]) -> Callable[..., RT]:
    """Time the execution of a function."""

    @wraps(func)
    def timeit_wrapper(*args, **kwargs) -> RT:  # type: ignore[no-untyped-def]
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        output = f"Function {func.__qualname__} Took {total_time:.8f} seconds"
        _LOGGER.debug(output)
        return result

    return timeit_wrapper
