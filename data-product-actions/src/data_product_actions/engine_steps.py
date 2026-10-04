"""Register data-product steps on the workflow engine's step catalog."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def register_engine_steps() -> None:
    """Add create and lifecycle steps to the engine registry.

    The engine only runs step types it has registered. Importing this package
    (including from the wheel's site hook) does that registration. A missing
    engine install is ignored so the standalone actions still load.
    """
    try:
        from datahub_workflow_actions.steps import REGISTRY, RunContext, StepParams, step
    except ImportError:
        logger.debug("workflow engine is not installed; skipping step registration")
        return

    if "create_data_product" in REGISTRY and "set_data_product_lifecycle" in REGISTRY:
        return

    from data_product_actions.graphql_ops import create_data_product, set_lifecycle_stage

    class CreateDataProductParams(StepParams):
        name: str
        domain: str
        description: Optional[str] = None
        lifecycle_stage: Optional[str] = None
        id: Optional[str] = None
        parent_data_product: Optional[str] = None
        workflow_urn: Optional[str] = None

    class SetLifecycleParams(StepParams):
        entity: str
        lifecycle_stage: str
        workflow_urn: Optional[str] = None

    @step(
        "create_data_product",
        label="Create data product",
        description="Create a data product in a domain and optionally set its lifecycle stage.",
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
        if params.lifecycle_stage:
            set_lifecycle_stage(
                ctx.graph,
                {"entity": urn, "lifecycle_stage": params.lifecycle_stage},
            )
        return {"urn": urn}

    @step(
        "set_data_product_lifecycle",
        label="Set data product lifecycle",
        description="Set the lifecycle stage on an existing data product.",
        group="Metadata",
        params=SetLifecycleParams,
        outputs={"urn": "URN of the data product"},
    )
    def set_data_product_lifecycle_step(params: SetLifecycleParams, ctx: RunContext) -> dict:
        skipped = _other_workflow(params.workflow_urn, ctx)
        if skipped:
            return skipped
        if ctx.dry_run or ctx.graph is None:
            return {
                "dryRun": True,
                "urn": params.entity,
                "lifecycleStage": params.lifecycle_stage,
            }
        urn = set_lifecycle_stage(
            ctx.graph,
            {"entity": params.entity, "lifecycle_stage": params.lifecycle_stage},
        )
        return {"urn": urn, "lifecycleStage": params.lifecycle_stage}


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
