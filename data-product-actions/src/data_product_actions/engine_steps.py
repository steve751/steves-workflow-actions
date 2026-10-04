"""Register data-product steps on the workflow engine's step catalog."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def register_engine_steps() -> None:
    """Add create and structured-property steps to the engine registry.

    The engine only runs step types it has registered. Importing this package
    (including from the wheel's site hook) does that registration. A missing
    engine install is ignored so the standalone actions still load.
    """
    try:
        from datahub_workflow_actions.steps import REGISTRY, RunContext, StepParams, step
    except ImportError:
        logger.debug("workflow engine is not installed; skipping step registration")
        return

    if "create_data_product" in REGISTRY and "set_data_product_property" in REGISTRY:
        return

    from data_product_actions.graphql_ops import (
        add_owners,
        create_data_product,
        set_structured_property,
    )

    class StructuredPropertyAssignment(StepParams):
        urn: str
        value: Any

    class CreateDataProductParams(StepParams):
        name: str
        domain: str
        description: Optional[str] = None
        structured_property: Optional[StructuredPropertyAssignment] = None
        owner: Optional[str] = None
        ownership_type: Optional[str] = None
        id: Optional[str] = None
        parent_data_product: Optional[str] = None
        workflow_urn: Optional[str] = None

    class SetPropertyParams(StepParams):
        entity: str
        structured_property: StructuredPropertyAssignment
        workflow_urn: Optional[str] = None

    @step(
        "create_data_product",
        label="Create data product",
        description="Create a data product in a domain and optionally set a structured property.",
        group="Metadata",
        params=CreateDataProductParams,
        outputs={"urn": "URN of the created data product"},
    )
    def create_data_product_step(params: CreateDataProductParams, ctx: RunContext) -> dict:
        skipped = _other_workflow(params.workflow_urn, ctx)
        if skipped:
            return skipped
        if ctx.dry_run or ctx.graph is None:
            return {"dryRun": True, "name": params.name, "domain": params.domain}
        urn = create_data_product(ctx.graph, _payload(params))
        if params.structured_property is not None:
            set_structured_property(
                ctx.graph,
                {"entity": urn, "structured_property": params.structured_property.model_dump()},
            )
        if params.owner:
            add_owners(
                ctx.graph,
                {
                    "entity": urn,
                    "owner": params.owner,
                    "ownership_type": params.ownership_type,
                },
            )
        return {"urn": urn}

    @step(
        "set_data_product_property",
        label="Set data product property",
        description="Set a structured property on an existing data product.",
        group="Metadata",
        params=SetPropertyParams,
        outputs={"urn": "URN of the data product"},
    )
    def set_data_product_property_step(params: SetPropertyParams, ctx: RunContext) -> dict:
        skipped = _other_workflow(params.workflow_urn, ctx)
        if skipped:
            return skipped
        if ctx.dry_run or ctx.graph is None:
            return {
                "dryRun": True,
                "urn": params.entity,
                "structuredProperty": params.structured_property.urn,
                "value": params.structured_property.value,
            }
        urn = set_structured_property(
            ctx.graph,
            {
                "entity": params.entity,
                "structured_property": params.structured_property.model_dump(),
            },
        )
        return {
            "urn": urn,
            "structuredProperty": params.structured_property.urn,
            "value": params.structured_property.value,
        }


def _other_workflow(expected: Optional[str], ctx: Any) -> Optional[dict[str, Any]]:
    """Skip result when the step is pinned to a workflow other than the one that fired."""
    if not expected:
        return None
    actual = ((getattr(ctx, "context", None) or {}).get("workflow") or {}).get("urn")
    if actual and actual != expected:
        return {"skipped": True, "reason": f"workflow {actual} != {expected}"}
    return None


def _payload(params: Any) -> dict[str, Any]:
    return {
        "name": params.name,
        "domain": params.domain,
        "description": params.description,
        "id": params.id,
        "parent_data_product": params.parent_data_product,
    }
