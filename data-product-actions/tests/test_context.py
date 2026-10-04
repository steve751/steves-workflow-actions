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
            "structured_property": "urn:li:structuredProperty:io.mycompany.status",
        },
        context,
    )
    assert rendered == {
        "name": "Customer 360",
        "domain": "urn:li:domain:marketing",
        "structured_property": "urn:li:structuredProperty:io.mycompany.status",
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


def test_property_assignment_reads_nested_value() -> None:
    from data_product_actions.graphql_ops import property_assignment

    urn, value = property_assignment(
        {
            "structured_property": {
                "urn": "urn:li:structuredProperty:io.mycompany.status",
                "value": "Draft",
            }
        }
    )
    assert urn == "urn:li:structuredProperty:io.mycompany.status"
    assert value == "Draft"


def test_property_values_keep_strings_and_numbers() -> None:
    from data_product_actions.graphql_ops import property_values

    assert property_values("Draft") == [{"stringValue": "Draft"}]
    assert property_values(3) == [{"numberValue": 3.0}]
    assert property_values(["a", "b"]) == [
        {"stringValue": "a"},
        {"stringValue": "b"},
    ]
