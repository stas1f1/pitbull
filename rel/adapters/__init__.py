"""Адаптеры баз. Новая база = один файл здесь. Шаблон: _template.py."""
import importlib

def get(name):
    m = importlib.import_module(f"adapters.{name}")
    return m.Adapter()
