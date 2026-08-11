"""Dependency Checker — 检测ML依赖可用性"""
import importlib
from typing import Dict


def check_dependencies() -> Dict[str, bool]:
    """检测ML库可用性"""
    libs = {
        "sklearn": "sklearn",
        "xgboost": "xgboost",
        "lightgbm": "lightgbm",
        "numpy": "numpy",
        "pandas": "pandas",
    }
    result = {}
    for name, module in libs.items():
        try:
            importlib.import_module(module)
            result[name] = True
        except ImportError:
            result[name] = False
    return result


def get_best_model_class():
    """返回最佳可用的模型类"""
    deps = check_dependencies()

    if deps.get("xgboost"):
        from xgboost import XGBRegressor
        return XGBRegressor, "xgboost"

    if deps.get("sklearn"):
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor, "sklearn_gradient_boosting"

    if deps.get("sklearn"):
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor, "sklearn_random_forest"

    return None, "numpy_fallback"
