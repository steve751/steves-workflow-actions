"""Set the lifecycle stage on a data product when a workflow request is accepted."""

from __future__ import annotations

import logging
from typing import Any

from datahub_actions.action.action import Action
from datahub_actions.event.event_envelope import EventEnvelope
from datahub_actions.pipeline.pipeline_context import PipelineContext

from data_product_actions.context import (
    context_from_event,
    render_mapping,
    should_handle,
)
from data_product_actions.graphql_ops import set_lifecycle_stage

logger = logging.getLogger(__name__)


class SetDataProductLifecycleAction(Action):
    """Set the lifecycle stage on an existing data product.

    Config or step params:
      entity: data product URN, ``{{ entity.urn }}``, or ``{{ fields.data_product }}``
      lifecycle_stage: lifecycle stage URN, for example ``urn:li:lifecycleStageType:PUBLISHED``
      workflow_urn: only handle this workflow
    """

    @classmethod
    def create(
        cls, config_dict: dict, ctx: PipelineContext
    ) -> "SetDataProductLifecycleAction":
        return cls(config_dict or {}, ctx)

    def __init__(self, config: dict, ctx: PipelineContext) -> None:
        self.config = config
        self.ctx = ctx

    def act(self, event: EventEnvelope) -> str | None:
        context = context_from_event(event.event)
        if not should_handle(self.config, context):
            return None
        params = render_mapping(self.config, context)
        urn = set_lifecycle_stage(self._graph(), params)
        logger.info("Set lifecycle stage on %s to %s", urn, params.get("lifecycle_stage"))
        return urn

    def close(self) -> None:
        return None

    def _graph(self) -> Any:
        wrapper = self.ctx.graph
        if wrapper is None:
            raise RuntimeError("DataHub graph client is not configured on this action")
        return wrapper.graph
