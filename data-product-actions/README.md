# data-product-actions

Two step types for the DataHub workflow engine (`datahub-workflow-actions`):

| Step type | What it does |
| --- | --- |
| `create_data_product` | Creates a data product in an existing domain. Optionally sets its lifecycle stage in the same step. |
| `set_data_product_lifecycle` | Sets the lifecycle stage on a data product that already exists. |

Installing the wheel adds both types to the engine's step catalog. Use them in a rule's `steps[].type` the same way as `add_term` or `webhook`.

The same code is also exposed as two standalone `datahub-actions` plugins (`CreateDataProductAction`, `SetDataProductLifecycleAction`) for use outside the engine. See [Running it as a DataHub Action pipeline](#running-it-as-a-datahub-action-pipeline).

## Build the wheel

From this directory:

```bash
python3 pack_wheel.py
```

That writes `dist/data_product_actions-0.2.1-py3-none-any.whl` and adds a `.pth` site hook that imports the package at interpreter start, which is what registers the step types with the engine.

The pip name is `data-product-actions` and the Python package is `data_product_actions`. Both must stay different from the engine's `datahub-workflow-actions` / `datahub_workflow_actions`. See [Troubleshooting](#troubleshooting) for why.

## Install on the engine

On the engine ingestion source, set **Extra Pip Libraries** to the engine zip plus this wheel:

```json
[
  "https://github.com/brock-acryl/datahub-workflow-actions/archive/main.zip",
  "https://github.com/steve751/steves-workflow-actions/raw/refs/heads/main/data-product-actions/dist/data_product_actions-0.2.1-py3-none-any.whl"
]
```

Remove any older wheel URL (`datahub_workflow_actions-0.1.0`, `data_product_actions-0.1.0`, `data_product_actions-0.2.0`). Save the source and run it once so the executor builds a fresh virtualenv.

To confirm the install worked, look for the step names in the engine log. Any step failure lists the known types, for example:

```text
known: ['add_owner', 'add_tag', ..., 'create_data_product', ..., 'set_data_product_lifecycle', ...]
```

## Step parameters

The engine renders `{{ ... }}` templates before the step runs, so every parameter below can be a literal or a template. Parameters are strict: a key that is not listed here fails the step with `invalid params`.

### `create_data_product`

| Param | Required | Value |
| --- | --- | --- |
| `name` | yes | Display name of the new data product |
| `domain` | yes | URN of a domain that already exists, such as `urn:li:domain:marketing` |
| `description` | no | Description stored on the new data product |
| `lifecycle_stage` | no | Lifecycle stage URN applied to the product after it is created |
| `id` | no | Fixed id used in the data product URN. Omit it and DataHub generates one |
| `parent_data_product` | no | URN of an existing parent data product |
| `workflow_urn` | keep it | The workflow this step belongs to. The Workflow Builder needs it to run the step. The step also skips itself if a different workflow fired |

Output: `urn` of the created data product. Later steps in the same rule can read it as `{{ steps.<step-id>.output.urn }}`, for example to add owners or assets to the new product with `add_owner` or `add_to_data_product`.

### `set_data_product_lifecycle`

| Param | Required | Value |
| --- | --- | --- |
| `entity` | yes | Data product URN. Usually `{{ entity.urn }}` when the workflow is launched from the product page |
| `lifecycle_stage` | yes | Lifecycle stage URN, for example `urn:li:lifecycleStageType:PUBLISHED` |
| `workflow_urn` | keep it | Same as on `create_data_product` |

Output: `urn` and `lifecycleStage`.

### Template context

| Template | Value |
| --- | --- |
| `{{ form.<field id> }}` | A submitted form field, by field id. Single values render as the value, multi-select fields as a list |
| `{{ form_by_name.<field name> }}` | Same, by the field's display name |
| `{{ entity.urn }}` | The entity the workflow was launched from |
| `{{ workflow.urn }}` | The workflow URN |
| `{{ requester.urn }}` / `{{ approver.urn }}` | Who raised and who decided the request |

### Lifecycle stages

`lifecycle_stage` must be a lifecycle stage URN that exists in your instance and applies to data products. `urn:li:lifecycleStageType:DRAFT` and `urn:li:lifecycleStageType:PUBLISHED` in the examples are placeholders. Replace them with stages from your catalog. The engine's DataHub connection needs permission to manage data products on the target domain.

## Example: create a product when the request is approved

Use this when someone submits a form and an approver accepts it. The form must collect `name` and `domain`, and may collect `description`. The create step also sets the lifecycle stage on the product it just created, so you do not need the new URN in a later step.

Set `workflow_urn` in `params` to the same workflow as the rule's `workflowUrn`. Without it the Workflow Builder does not run the step.

`rules.json` in this folder contains this rule and the one below.

```json
{
  "id": "create-data-product",
  "name": "Create data product when approved",
  "enabled": true,
  "on": {
    "operation": "COMPLETED",
    "result": "ACCEPTED"
  },
  "steps": [
    {
      "id": "create-data-product",
      "type": "create_data_product",
      "params": {
        "name": "{{ form.name }}",
        "domain": "{{ form.domain }}",
        "description": "{{ form.description }}",
        "lifecycle_stage": "urn:li:lifecycleStageType:DRAFT",
        "workflow_urn": "urn:li:actionWorkflow:8a96234f-96b7-465b-a633-579d8bf2cf8d"
      }
    }
  ],
  "engineId": "urn:li:dataHubIngestionSource:0ae5de7b-d931-4e18-a87c-44bd3951b368",
  "workflowUrn": "urn:li:actionWorkflow:8a96234f-96b7-465b-a633-579d8bf2cf8d",
  "description": "When the request is approved, create the data product in the chosen domain and set its lifecycle stage."
}
```

A submitted form with `name = Customer 360`, `domain = urn:li:domain:marketing`, `description = Customer data product` creates a data product named Customer 360 in `urn:li:domain:marketing`, then sets its lifecycle stage to the URN in `lifecycle_stage`.

## Example: change the lifecycle stage of an existing data product

Launch this workflow from the data product page. `{{ entity.urn }}` is that product.

```json
{
  "id": "set-data-product-lifecycle",
  "name": "Set data product lifecycle stage",
  "enabled": true,
  "on": {
    "operation": "COMPLETED",
    "result": "ACCEPTED"
  },
  "steps": [
    {
      "id": "set-lifecycle-stage",
      "type": "set_data_product_lifecycle",
      "params": {
        "entity": "{{ entity.urn }}",
        "lifecycle_stage": "urn:li:lifecycleStageType:PUBLISHED",
        "workflow_urn": "urn:li:actionWorkflow:8a96234f-96b7-465b-a633-579d8bf2cf8d"
      }
    }
  ],
  "engineId": "urn:li:dataHubIngestionSource:0ae5de7b-d931-4e18-a87c-44bd3951b368",
  "workflowUrn": "urn:li:actionWorkflow:8a96234f-96b7-465b-a633-579d8bf2cf8d",
  "description": "When the request is approved, set the lifecycle stage on the data product the workflow was launched from."
}
```

To take the product URN from the form instead of the page it was launched from, set `entity` to `{{ form.data_product }}` and add a form field whose id is `data_product`.

## Running it as a DataHub Action pipeline

Outside the engine, the same logic is registered on the `datahub_actions.action.plugins` entry point as `create_data_product` and `set_data_product_lifecycle`. `examples/actions-pipeline.json` is a pipeline that listens for the accepted workflow and runs the create action. Run it with the actions CLI after installing the wheel in that environment:

```bash
datahub actions -c examples/actions-pipeline.json
```

This path reads the raw completion event, so its templates are `{{ fields.name }}` rather than `{{ form.name }}`, and `workflow_urn` is a valid config key there (it filters events to one workflow).

## Troubleshooting

**`Requirements contain conflicting URLs for package datahub-workflow-actions`**
Two entries in Extra Pip Libraries resolve to the same pip package name. An earlier build of this wheel was named `datahub-workflow-actions`, which clashes with the engine. Use the `data_product_actions-0.2.1` wheel and remove the old URL.

**`Caught exception while attempting to instantiate Action with type workflow_actions`**
The installed wheel unpacked into the engine's Python package `datahub_workflow_actions` and overwrote its `context.py`. This happens with the `0.1.0` wheels. Use `0.2.1`, which installs as `data_product_actions`.

**`unknown step type 'datahub_workflow_actions.create_product:CreateDataProductAction'`**
The rule still uses the old import-path type string. The engine only runs registered step names. Change the step `type` to `create_data_product` or `set_data_product_lifecycle`. If the known-types list in that message does not include them, the wheel is not installed in the engine's venv; rerun the source.

**`invalid params: workflow_urn Extra inputs are not permitted`**
The engine is running the `0.2.0` wheel, which did not accept `workflow_urn`. Install `0.2.1` and rerun the source. For any other key in that message, the step does not accept it; check the parameter tables above.

**`rule ... not fired (operation CREATE != COMPLETED)` / `(operation MODIFY != COMPLETED)`**
Not an error. The engine saw the request being created or a step being decided and skipped it. The rule fires on the final `COMPLETED` event with `result = ACCEPTED`.

**`warning: The package acryl-datahub==1.7.0.14 does not have an extra named datahub-workflow-actions`**
Harmless. The executor tries to install an `acryl-datahub` extra matching the source type; the engine is provided by Extra Pip Libraries instead.
