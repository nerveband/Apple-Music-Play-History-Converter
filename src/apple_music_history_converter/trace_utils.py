"""Utility helpers for runtime tracing of Toga UI and backend calls.

Set the environment variable ``APPLE_MUSIC_TRACE=1`` to enable tracing.
Optional environment variables:
    * ``APPLE_MUSIC_TRACE_FILE`` - path to the trace log file

These helpers can wrap synchronous and asynchronous callables, capturing
entry/exit timing and arguments without altering the underlying logic.
"""

from __future__ import annotations

import functools
import inspect
import logging
import os
import threading
import time
from typing import Any, Callable, Optional, Tuple


TRACE_ENABLED: bool = os.environ.get("APPLE_MUSIC_TRACE", "0") not in {"", "0", "false", "False"}
TRACE_LOG_PATH: str = os.environ.get("APPLE_MUSIC_TRACE_FILE", "app_trace.log")


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("apple_music.trace")

    if TRACE_ENABLED:
        if not logger.handlers:
            handler = logging.FileHandler(TRACE_LOG_PATH, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s [TRACE] %(message)s"))
            logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    else:
        # Ensure the logger exists but discard output silently.
        if not any(isinstance(h, logging.NullHandler) for h in logger.handlers):
            logger.addHandler(logging.NullHandler())

    return logger


trace_log: logging.Logger = _build_logger()


def trace_call(label: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that logs function entry/exit and execution time when tracing is enabled."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if not TRACE_ENABLED:
            return func

        if isinstance(func, (staticmethod, classmethod)):
            wrapped_target = func.__func__
        else:
            wrapped_target = func

        if inspect.iscoroutinefunction(wrapped_target):

            @functools.wraps(wrapped_target)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start = time.perf_counter()
                trace_log.debug("-> %s thread=%s args=%s kwargs=%s", label, threading.current_thread().name, _trim_args(args), kwargs)
                call_args, call_kwargs = _prepare_args(wrapped_target, args, kwargs)
                try:
                    result = wrapped_target(*call_args, **call_kwargs)
                    return await result
                finally:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    trace_log.debug("<- %s (%.2f ms)", label, elapsed_ms)

            async_wrapper._trace_wrapped = True  # type: ignore[attr-defined]
            return async_wrapper

        @functools.wraps(wrapped_target)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            trace_log.debug("-> %s thread=%s args=%s kwargs=%s", label, threading.current_thread().name, _trim_args(args), kwargs)
            call_args, call_kwargs = _prepare_args(wrapped_target, args, kwargs)
            try:
                return wrapped_target(*call_args, **call_kwargs)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                trace_log.debug("<- %s (%.2f ms)", label, elapsed_ms)

        sync_wrapper._trace_wrapped = True  # type: ignore[attr-defined]
        if func is wrapped_target:
            return sync_wrapper
        # Maintain descriptor type (staticmethod/classmethod)
        if isinstance(func, staticmethod):
            return staticmethod(sync_wrapper)
        if isinstance(func, classmethod):
            return classmethod(sync_wrapper)
        return sync_wrapper

    return decorator


def _trim_args(args: tuple[Any, ...], max_items: int = 4) -> tuple[Any, ...]:
    """Remove the self/cls argument and trim long sequences for readability."""

    if not args:
        return args

    # Drop implicit self/cls from logging - usually the first argument.
    trimmed = args[1:] if len(args) > 0 else args

    if len(trimmed) <= max_items:
        return trimmed

    head = trimmed[: max_items - 1]
    tail = (f"...(+{len(trimmed) - len(head)} more)",)
    return head + tail


def _prepare_args(func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> Tuple[tuple[Any, ...], dict[str, Any]]:
    """Adjust positional arguments to match the callable signature if needed."""

    if not args:
        return args, kwargs

    try:
        inspect.signature(func).bind_partial(*args, **kwargs)
        return args, kwargs
    except TypeError:
        pass

    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    accepts_var_positional = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
    if accepts_var_positional:
        # Function already accepts *args; use original arguments.
        return args, kwargs

    positional_params = [
        p for p in params if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]

    expected = len(positional_params)
    if inspect.ismethod(func) and expected > 0:
        expected -= 1  # drop implicit self/cls

    expected = max(expected, 0)
    trimmed = args[:expected]

    try:
        sig.bind_partial(*trimmed, **kwargs)
    except TypeError:
        # If binding still fails, fall back to original arguments to surface the error.
        return args, kwargs

    return trimmed, kwargs


def instrument_widget(widget: Any, name: str, events: Optional[list[str]] = None) -> Any:
    """Wrap common Toga widget callbacks (on_press/on_change/...) in trace decorators."""

    if not TRACE_ENABLED or widget is None:
        return widget

    event_names = events or [
        "on_press",
        "on_change",
        "on_select",
        "on_toggle",
        "on_click",
        "on_submit",
    ]

    for attr in event_names:
        handler = getattr(widget, attr, None)
        if callable(handler) and not getattr(handler, "_trace_wrapped", False):
            wrapped = trace_call(f"{name}.{attr}")(handler)
            wrapped._trace_wrapped = True  # type: ignore[attr-defined]
            setattr(widget, attr, wrapped)

    return widget


__all__ = [
    "TRACE_ENABLED",
    "TRACE_LOG_PATH",
    "trace_call",
    "trace_log",
    "instrument_widget",
]
