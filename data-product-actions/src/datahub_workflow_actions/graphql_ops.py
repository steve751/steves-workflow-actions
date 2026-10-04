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

_SET_LIFECYCLE_STAGE = """
mutation setLifecycleStage($urn: String!, $lifecycleStageUrn: String) {
  setLifecycleStage(urn: $urn, lifecycleStageUrn: $lifecycleStageUrn)
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


def set_lifecycle_stage(graph: Any, params: dict[str, Any]) -> str:
    entity_urn = _required(params, "entity", "entity_urn", "urn")
    stage_urn = _required(
        params, "lifecycle_stage", "lifecycle_stage_urn", "lifecycleStageUrn"
    )
    graph.execute_graphql(
        query=_SET_LIFECYCLE_STAGE,
        variables={"urn": entity_urn, "lifecycleStageUrn": stage_urn},
        operation_name="setLifecycleStage",
    )
    return entity_urn


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
