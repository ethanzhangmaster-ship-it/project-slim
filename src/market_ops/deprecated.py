"""Deprecation 辅助工具"""
import warnings
import functools


def deprecated(since: str, use_instead: str):
    """标记函数/类为 deprecated"""
    def decorator(obj):
        msg = f"{obj.__name__} is deprecated since {since}. Use {use_instead} instead."
        if isinstance(obj, type):
            orig_init = obj.__init__
            @functools.wraps(orig_init)
            def new_init(self, *args, **kwargs):
                warnings.warn(msg, DeprecationWarning, stacklevel=2)
                orig_init(self, *args, **kwargs)
            obj.__init__ = new_init
            return obj
        else:
            @functools.wraps(obj)
            def wrapper(*args, **kwargs):
                warnings.warn(msg, DeprecationWarning, stacklevel=2)
                return obj(*args, **kwargs)
            return wrapper
    return decorator


def module_deprecated(since: str, use_instead: str):
    """用于模块级别的 deprecation warning，import 时触发"""
    warnings.warn(
        f"This module is deprecated since {since}. Use {use_instead} instead.",
        DeprecationWarning,
        stacklevel=2,
    )
