__all__ = ["api", "create_app", "register_routes"]


def __getattr__(name):
    """Avoid importing Flask when callers only need a pure backend helper."""
    if name in __all__:
        from .backend import api, create_app, register_routes

        return {"api": api, "create_app": create_app, "register_routes": register_routes}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
