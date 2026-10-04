"""GraphQL calls used by the workflow actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Workflow date fields arrive as epoch milliseconds, often already stringified
# in scientific notation (``1.793275843419E12``). The engine ``date`` filter
# leaves that string unchanged, and a date property rejects anything but YYYY-MM-DD.
_EPOCH_MILLIS_MIN = 1e11
_EPOCH_MILLIS_MAX = 1e14

_CREATE_DATA_PRODUCT = """
mutation createDataProduct($input: CreateDataProductInput!) {
  createDataProduct(input: $input) {
    urn
  }
}
"""

_UPSERT_STRUCTURED_PROPERTIES = """
mutation upsertStructuredProperties($input: UpsertStructuredPropertiesInput!) {
  upsertStructuredProperties(input: $input) {
    properties {
      structuredProperty {
        urn
      }
    }
  }
}
"""


def create_data_product(graph: Any, params: dict[str, Any]) -> str:
    name = _required(params, "name", "name_field", "fields.name")
    domain_urn = _required(params, "domain", "domain_urn", "domainUrn")
    description = _optional(params, "description")
    product_id = _optional(params, "id", "product_id")

    properties: dict[str, Any] = {"name": name}
    if description:
        properties["description"] = description
    parent = _optional(params, "parent_data_product", "parentDataProduct")
    if parent:
        properties["parentDataProduct"] = parent

    variables: dict[str, Any] = {
        "input": {"domainUrn": domain_urn, "properties": properties}
    }
    if product_id:
        variables["input"]["id"] = product_id

    result = graph.execute_graphql(
        query=_CREATE_DATA_PRODUCT,
        variables=variables,
        operation_name="createDataProduct",
    )
    created = (result or {}).get("createDataProduct") or {}
    urn = created.get("urn")
    if not urn:
        raise RuntimeError(f"createDataProduct returned no urn: {result}")
    return str(urn)


_ADD_OWNERS = """
mutation batchAddOwners($input: BatchAddOwnersInput!) {
  batchAddOwners(input: $input)
}
"""


def set_structured_property(graph: Any, params: dict[str, Any]) -> str:
    """Upsert every structured property in the params onto the entity."""
    entity_urn = _required(params, "entity", "entity_urn", "urn")
    assignments = property_assignments(params)
    graph.execute_graphql(
        query=_UPSERT_STRUCTURED_PROPERTIES,
        variables={
            "input": {
                "assetUrn": entity_urn,
                "structuredPropertyInputParams": [
                    {
                        "structuredPropertyUrn": property_urn,
                        "values": property_values(raw_value),
                    }
                    for property_urn, raw_value in assignments
                ],
            }
        },
        operation_name="upsertStructuredProperties",
    )
    return entity_urn


def add_owners(graph: Any, params: dict[str, Any]) -> str:
    entity_urn = _required(params, "entity", "entity_urn", "urn")
    raw_owner = params.get("owner")
    if raw_owner is None or raw_owner == "" or raw_owner == []:
        raise ValueError("Missing owner. Set owner to a user or group URN")
    owner_urns = raw_owner if isinstance(raw_owner, list) else [str(raw_owner)]
    ownership_type = str(params.get("ownership_type") or "TECHNICAL_OWNER")
    custom = ownership_type.startswith("urn:")
    owners = []
    for owner_urn in owner_urns:
        entry: dict[str, Any] = {
            "ownerUrn": owner_urn,
            "ownerEntityType": (
                "CORP_GROUP" if str(owner_urn).startswith("urn:li:corpGroup:") else "CORP_USER"
            ),
        }
        if custom:
            entry["ownershipTypeUrn"] = ownership_type
        else:
            entry["type"] = ownership_type
        owners.append(entry)
    graph.execute_graphql(
        query=_ADD_OWNERS,
        variables={
            "input": {
                "owners": owners,
                "resources": [{"resourceUrn": entity_urn}],
            }
        },
        operation_name="batchAddOwners",
    )
    return entity_urn


def property_assignments(params: dict[str, Any]) -> list[tuple[str, Any]]:
    """Read ``structured_properties: [{urn, value}, ...]``.

    A single ``structured_property: {urn, value}`` is accepted too, so the
    create step can keep passing one property.
    """
    items: list[Any] = []
    raw_list = params.get("structured_properties")
    if isinstance(raw_list, list):
        items.extend(raw_list)
    single = params.get("structured_property")
    if single:
        items.append(single)
    if not items and (params.get("property") or params.get("value") is not None):
        items.append(
            {
                "urn": params.get("property") or "",
                "value": params.get(
                    "value", params.get("values", params.get("structured_property_value"))
                ),
            }
        )
    if not items:
        raise ValueError(
            "Missing structured properties. Set structured_properties to a list of {urn, value}"
        )
    assignments: list[tuple[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(
                "Each structured property must be an object with urn and value"
            )
        urn = str(item.get("urn") or item.get("property") or "")
        if not urn:
            raise ValueError("Missing structured property URN. Set urn under each entry")
        assignments.append((urn, item.get("value", item.get("values"))))
    return assignments


def property_assignment(params: dict[str, Any]) -> tuple[str, Any]:
    """First structured property in ``params``."""
    return property_assignments(params)[0]


def property_values(raw: Any) -> list[dict[str, Any]]:
    """Turn a step value into GraphQL property values.

    A number is sent as ``numberValue``. Text is sent as ``stringValue``.
    Epoch milliseconds, including a scientific-notation string from a date
    form field, are sent as ``YYYY-MM-DD``. A list sets every entry.
    """
    if raw is None or raw == "" or raw == []:
        raise ValueError(
            "Missing structured property value. Set value or structured_property_value"
        )
    items = raw if isinstance(raw, list) else [raw]
    encoded: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, bool) or item is None or item == "":
            raise ValueError(f"Unsupported structured property value: {item!r}")
        date_text = _date_from_epoch_millis(item)
        if date_text is not None:
            encoded.append({"stringValue": date_text})
            continue
        if isinstance(item, (int, float)):
            encoded.append({"numberValue": float(item)})
            continue
        text = str(item).strip()
        if not text:
            raise ValueError("Structured property value is blank")
        encoded.append({"stringValue": text})
    return encoded


def _date_from_epoch_millis(item: Any) -> str | None:
    if isinstance(item, bool):
        return None
    if isinstance(item, (int, float)):
        number = float(item)
    elif isinstance(item, str):
        try:
            number = float(item.strip())
        except ValueError:
            return None
    else:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    if not (_EPOCH_MILLIS_MIN <= abs(number) < _EPOCH_MILLIS_MAX):
        return None
    return datetime.fromtimestamp(number / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _required(params: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = params.get(key)
        if value:
            return str(value)
    raise ValueError(f"Missing required parameter. Set one of: {', '.join(keys)}")


def _optional(params: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = params.get(key)
        if value:
            return str(value)
    return ""
