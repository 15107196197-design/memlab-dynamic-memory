"""Implementation registry: one axis, one name, one class (02-architecture 2.7.1).

Every switchable implementation registers itself on import::

    @register("graph.repr", "entity_triple")
    class EntityTripleGraph:
        ...

Configs then select it with ``{"graph.repr": {"impl": "entity_triple", "params": {...}}}``.
Duplicate registrations are an error: silently replacing an implementation is how
two experiments end up believing they ran different code.
"""
from __future__ import annotations

from typing import Any, Mapping

REGISTRY: dict[tuple[str, str], type] = {}


class UnknownImplementation(KeyError):
    """Raised for an axis/name that was never registered; lists what is available."""

    def __init__(self, axis: str, name: str, available):
        self.axis = axis
        self.name = name
        self.available = tuple(available)
        super().__init__(f"unknown {axis}:{name}; available={list(self.available)}")

    def __str__(self) -> str:  # KeyError would otherwise wrap the message in quotes
        return str(self.args[0])


def register(axis: str, name: str):
    """Class decorator that binds ``cls`` to ``(axis, name)``."""
    if not isinstance(axis, str) or not axis:
        raise ValueError("axis must be a non-empty string")
    if not isinstance(name, str) or not name:
        raise ValueError("name must be a non-empty string")

    def decorator(cls):
        key = (axis, name)
        existing = REGISTRY.get(key)
        if existing is not None:
            raise ValueError(
                f"{axis}:{name} is already registered to "
                f"{existing.__module__}.{existing.__qualname__}"
            )
        cls.axis = axis
        cls.name = name
        REGISTRY[key] = cls
        return cls

    return decorator


def available(axis: str) -> list[str]:
    """Registered implementation names for one axis, sorted."""
    return sorted(name for (registered_axis, name) in REGISTRY if registered_axis == axis)


def get(axis: str, name: str) -> type:
    """The class registered for ``(axis, name)``."""
    entry = REGISTRY.get((axis, name))
    if entry is None:
        raise UnknownImplementation(axis, name, available(axis))
    return entry


def build(axis: str, name: str, params: Mapping[str, Any] | None = None):
    """Instantiate an implementation, validating its parameters first."""
    cls = get(axis, name)
    payload = dict(params or {})
    validator = getattr(cls, "validate_params", None)
    if validator is not None:
        validator(payload)
    elif payload:
        raise TypeError(f"{axis}:{name} accepts no parameters; got {sorted(payload)}")
    return cls(**payload)


def list_implementations(axis: str | None = None) -> dict[str, list[str]] | list[str]:
    """All axes with their implementations, or just one axis' names."""
    if axis is not None:
        return available(axis)
    axes = sorted({registered_axis for (registered_axis, _) in REGISTRY})
    return {name: available(name) for name in axes}
