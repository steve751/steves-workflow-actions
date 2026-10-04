"""Set a structured property on a data product when a workflow request is accepted."""

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
from data_product_actions.graphql_ops import set_structured_property

logger = logging.getLogger(__name__)


class SetDataProductPropertyAction(Action):
    """Set a structured property on an existing data product.

    Config or step params:
      entity: data product URN, ``{{ entity.urn }}``, or ``{{ fields.data_product }}``
      structured_property: ``{urn, value}`` to store on the product
      workflow_urn: only handle this workflow
    """

    @classmethod
    def create(
        cls, config_dict: dict, ctx: PipelineContext
    ) -> "SetDataProductPropertyAction":
        return cls(config_dict or {}, ctx)

    def __init__(self, config: dict, ctx: PipelineContext) -> None:
        self.config = config
        self.ctx = ctx

    def act(self, event: EventEnvelope) -> str | None:
        context = context_from_event(event.event)
        if not should_handle(self.config, context):
            return None
        params = render_mapping(self.config, context)
        urn = set_structured_property(self._graph(), params)
        logger.info(
            "Set %s on %s",
            params.get("structured_property") or params.get("property"),
            urn,
        )
        return urn

    def close(self) -> None:
        return None

    def _graph(self) -> Any:
        wrapper = self.ctx.graph
        if wrapper is None:
            raise RuntimeError("DataHub graph client is not configured on this action")
        return wrapper.graph
