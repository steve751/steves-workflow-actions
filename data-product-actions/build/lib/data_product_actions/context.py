"""Read workflow completion events and render {{ }} templates."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping

_TEMPLATE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def context_from_event(event: Any) -> dict[str, Any]:
    """Build a template context from an EntityChangeEvent."""
    parameters = _parameters(event)
    fields = _flatten_fields(parameters.get("fields"))
    entity_urn = _text(getattr(event, "entityUrn", None)) or _text(
        parameters.get("entityUrn")
    )
    return {
        "entity": {"urn": entity_urn},
        "fields": fields,
        "workflowUrn": _text(parameters.get("workflowUrn")),
        "result": _text(parameters.get("result")),
        "operation": _text(getattr(event, "operation", None))
        or _text(parameters.get("operation")),
    }


def should_handle(config: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    """True when this event is the workflow completion the action is for."""
    expected_workflow = _text(config.get("workflow_urn"))
    actual_workflow = _text(context.get("workflowUrn"))
    if expected_workflow and actual_workflow and expected_workflow != actual_workflow:
        return False

    result = _text(context.get("result"))
    if result and result.upper() != "ACCEPTED":
        return False

    operation = _text(context.get("operation"))
    if operation and operation.upper() not in {"COMPLETED", "COMPLETE"}:
        return False
    return True


def render(value: Any, context: Mapping[str, Any]) -> Any:
    """Replace {{ a.b }} templates. A value that is only a template keeps its raw lookup."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    match = _TEMPLATE.fullmatch(stripped)
    if match:
        return _lookup(match.group(1), context)
    return _TEMPLATE.sub(
        lambda found: _text(_lookup(found.group(1), context)),
        value,
    )


def render_mapping(
    values: Mapping[str, Any], context: Mapping[str, Any]
) -> dict[str, Any]:
    return {key: render(value, context) for key, value in values.items()}


def _parameters(event: Any) -> dict[str, Any]:
    raw = getattr(event, "safe_parameters", None)
    if raw is None:
        inner = getattr(event, "_inner_dict", None) or {}
        raw = inner.get("__parameters_json")
    if isinstance(raw, str):
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    if isinstance(raw, Mapping):
        return dict(raw)
    return {}


def _flatten_fields(raw: Any) -> dict[str, str]:
    if isinstance(raw, str) and raw.strip():
        parsed = json.loads(raw)
    elif isinstance(raw, Mapping):
        parsed = raw
    else:
        return {}
    flat: dict[str, str] = {}
    for key, value in parsed.items():
        if isinstance(value, list):
            flat[str(key)] = _text(value[0]) if value else ""
        else:
            flat[str(key)] = _text(value)
    return flat


def _lookup(path: str, context: Mapping[str, Any]) -> Any:
    current: Any = context
    for part in path.strip().split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return ""
    return current


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
