"""Template and field parsing. Does not import the action framework."""

from data_product_actions.context import (
    context_from_event,
    render,
    render_mapping,
    should_handle,
)


class _Event:
    def __init__(self, operation: str, entity_urn: str, parameters: dict) -> None:
        self.operation = operation
        self.entityUrn = entity_urn
        self.safe_parameters = parameters


def test_form_fields_render_into_create_params() -> None:
    event = _Event(
        "COMPLETED",
        "urn:li:domain:marketing",
        {
            "result": "ACCEPTED",
            "workflowUrn": "urn:li:actionWorkflow:abc",
            "fields": '{"name": ["Customer 360"], "domain": ["urn:li:domain:marketing"]}',
        },
    )
    context = context_from_event(event)
    assert should_handle({"workflow_urn": "urn:li:actionWorkflow:abc"}, context)
    rendered = render_mapping(
        {
            "name": "{{ fields.name }}",
            "domain": "{{ fields.domain }}",
            "lifecycle_stage": "urn:li:lifecycleStageType:DRAFT",
        },
        context,
    )
    assert rendered == {
        "name": "Customer 360",
        "domain": "urn:li:domain:marketing",
        "lifecycle_stage": "urn:li:lifecycleStageType:DRAFT",
    }


def test_entity_urn_template() -> None:
    context = {
        "entity": {"urn": "urn:li:dataProduct:customer-360"},
        "fields": {},
        "result": "ACCEPTED",
        "operation": "COMPLETED",
        "workflowUrn": "",
    }
    assert render("{{ entity.urn }}", context) == "urn:li:dataProduct:customer-360"


def test_rejected_request_is_ignored() -> None:
    assert not should_handle({}, {"result": "REJECTED", "operation": "COMPLETED"})
