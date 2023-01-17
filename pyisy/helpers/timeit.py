"""Helpers for testing performance during development."""

from functools import wraps
import logging
import time

_LOGGER = logging.getLogger(__name__)


def timeit(func):
    """Time the execution of a function."""

    @wraps(func)
    def timeit_wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        total_time = end_time - start_time
        output = f"Function {func.__qualname__} Took {total_time:.8f} seconds"
        _LOGGER.debug(output)
        return result

    return timeit_wrapper
