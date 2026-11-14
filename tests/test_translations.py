"""Keep the shipped translations in step with strings.json, the core-style source."""

import json
from pathlib import Path
import re
from typing import Any

import homeassistant

COMPONENT = Path(__file__).parent.parent / "custom_components" / "amb_bellinzona"
COMMON = json.loads((Path(homeassistant.__file__).parent / "strings.json").read_text())


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _resolve(node: Any) -> Any:
    """Resolve [%key:a::b%] references against HA's own strings.json, like core's translation script."""
    if isinstance(node, dict):
        return {key: _resolve(value) for key, value in node.items()}

    def lookup(match: re.Match[str]) -> str:
        value: Any = COMMON
        for part in match.group(1).split("::"):
            value = value[part]
        return value

    return re.sub(r"\[%key:([^%]+)%\]", lookup, node)


def _keys(node: Any, prefix: str = "") -> set[str]:
    if not isinstance(node, dict):
        return {prefix}
    return {key for name, value in node.items() for key in _keys(value, f"{prefix}/{name}")}


def test_en_is_generated_from_strings() -> None:
    assert _load(COMPONENT / "translations" / "en.json") == _resolve(_load(COMPONENT / "strings.json"))


def test_it_has_the_same_keys() -> None:
    assert _keys(_load(COMPONENT / "translations" / "it.json")) == _keys(_load(COMPONENT / "strings.json"))
