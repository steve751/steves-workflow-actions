"""GraphQL calls used by the workflow actions."""

from __future__ import annotations

from typing import Any

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
    entity_urn = _required(params, "entity", "entity_urn", "urn")
    property_urn, raw_value = property_assignment(params)
    if not property_urn:
        raise ValueError(
            "Missing structured property URN. Set structured_property.urn"
        )
    values = property_values(raw_value)
    graph.execute_graphql(
        query=_UPSERT_STRUCTURED_PROPERTIES,
        variables={
            "input": {
                "assetUrn": entity_urn,
                "structuredPropertyInputParams": [
                    {"structuredPropertyUrn": property_urn, "values": values}
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


def property_assignment(params: dict[str, Any]) -> tuple[str, Any]:
    """Read ``structured_property: {urn, value}``. A bare URN plus ``value`` still works."""
    raw = params.get("structured_property")
    if isinstance(raw, dict):
        urn = raw.get("urn") or raw.get("property") or ""
        value = raw.get("value", raw.get("values"))
        return str(urn), value
    value = params.get("value", params.get("values", params.get("structured_property_value")))
    return str(raw or params.get("property") or ""), value


def property_values(raw: Any) -> list[dict[str, Any]]:
    """Turn a step value into GraphQL property values.

    A number is sent as ``numberValue``. Text is sent as ``stringValue``.
    A list sets every entry.
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
        if isinstance(item, (int, float)):
            encoded.append({"numberValue": float(item)})
            continue
        text = str(item).strip()
        if not text:
            raise ValueError("Structured property value is blank")
        encoded.append({"stringValue": text})
    return encoded


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
