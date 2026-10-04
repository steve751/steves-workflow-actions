"""Create a data product when a workflow request is accepted."""

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
from data_product_actions.graphql_ops import create_data_product, set_lifecycle_stage

logger = logging.getLogger(__name__)


class CreateDataProductAction(Action):
    """Create a data product from workflow form fields.

    Config or step params:
      name: product name, or ``{{ fields.name }}``
      domain: existing domain URN, or ``{{ fields.domain }}``
      description: optional, or ``{{ fields.description }}``
      lifecycle_stage: optional stage URN applied to the new product
      workflow_urn: only handle this workflow
    """

    @classmethod
    def create(cls, config_dict: dict, ctx: PipelineContext) -> "CreateDataProductAction":
        return cls(config_dict or {}, ctx)

    def __init__(self, config: dict, ctx: PipelineContext) -> None:
        self.config = config
        self.ctx = ctx

    def act(self, event: EventEnvelope) -> str | None:
        context = context_from_event(event.event)
        if not should_handle(self.config, context):
            return None
        params = render_mapping(self.config, context)
        urn = create_data_product(self._graph(), params)
        stage = params.get("lifecycle_stage") or params.get("lifecycle_stage_urn")
        if stage:
            set_lifecycle_stage(
                self._graph(),
                {"entity": urn, "lifecycle_stage": stage},
            )
            logger.info("Created %s and set lifecycle stage %s", urn, stage)
        else:
            logger.info("Created %s", urn)
        return urn

    def close(self) -> None:
        return None

    def _graph(self) -> Any:
        wrapper = self.ctx.graph
        if wrapper is None:
            raise RuntimeError("DataHub graph client is not configured on this action")
        return wrapper.graph
