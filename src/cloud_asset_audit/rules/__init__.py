from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml


@lru_cache(maxsize=1)
def critical_events() -> dict[str, frozenset[str]]:
    text = resources.files(__package__).joinpath("critical_events.yaml").read_text(encoding="utf-8")
    return {cloud.upper(): frozenset(names) for cloud, names in yaml.safe_load(text).items()}


def is_critical(cloud: str, action: str) -> bool:
    return action in critical_events().get(cloud.upper(), frozenset())
