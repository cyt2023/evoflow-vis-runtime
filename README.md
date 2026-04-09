# evoflow-vis-runtime

`evoflow-vis-runtime` is a research prototype for **natural-language-driven visualization workflow search**.

It takes a user task in plain language, infers dataset structure, uses EvoFlow-style search to compose a C# operator workflow, executes that workflow through a .NET runner, evaluates the result with LLM-assisted scoring, and exports a Unity-facing JSON artifact.

## What This Project Does

Current end-to-end pipeline:

`natural language task -> dataset schema inference -> task spec generation -> workflow search -> C# operator execution -> evaluation -> Unity-ready JSON export`

In practice, the system can already:

- read a new CSV and infer likely id/time/spatial/value columns
- parse a natural-language visualization request
- search over a pool of C# visualization operators
- execute the selected workflow through `OperatorRunner`
- score the result using both runner-side structured evaluation and LLM evaluation
- export a final JSON contract for future Unity consumption

## Current Scope

This repository is **not** yet a full Unity application.

Right now it is focused on the backend side of the project:

- planner: understand the task and dataset
- executor: run the selected operator workflow
- exporter: emit a stable JSON artifact for a future Unity frontend

The Unity side is intentionally postponed. The current goal is to make the EvoFlow/backend side robust enough that Unity can later act as a thin consumer of the exported result.

## Main Components

### `evoflow/`
Python orchestration layer for:

- dataset schema inference
- task parsing
- EvoFlow-style workflow search
- LLM-based workflow evaluation
- Unity JSON export

Main entry point:

- [operator_search_main.py](/Users/cyt/Desktop/OperatorsDraft/evoflow/operator_search_main.py)

### `OperatorRunner/`
.NET execution layer that:

- receives a normalized workflow request
- executes C# operators in sequence
- returns execution results, diagnostics, self-evaluation, and visualization payloads

### Operator Packages

- `Data/`
- `View/`
- `Query/`
- `Filter/`
- `Backend/`

These contain the C# operator implementations used by the workflow search.

### `demo_data/`
Current example datasets:

- [taxi_od_small.csv](/Users/cyt/Desktop/OperatorsDraft/demo_data/taxi_od_small.csv)
- [first_week_of_may_2011_10k_sample.csv](/Users/cyt/Desktop/OperatorsDraft/demo_data/first_week_of_may_2011_10k_sample.csv)
- [hurricane_sandy_2012_100k_sample.csv](/Users/cyt/Desktop/OperatorsDraft/demo_data/hurricane_sandy_2012_100k_sample.csv)

### `exports/`
Example exported JSON artifacts:

- [test3.json](/Users/cyt/Desktop/OperatorsDraft/exports/test3.json)
- [test3_schema_sample.json](/Users/cyt/Desktop/OperatorsDraft/exports/test3_schema_sample.json)
- [hurricane_sandy_unity_export.json](/Users/cyt/Desktop/OperatorsDraft/exports/hurricane_sandy_unity_export.json)

## Quick Start

Use the one-command launcher:

```bash
./run_evoflow.sh \
  --task "Find concentrated morning pickup hotspots in the Hurricane Sandy sample and render them as a backend-ready point visualization." \
  --data-path /Users/cyt/Desktop/OperatorsDraft/demo_data/hurricane_sandy_2012_100k_sample.csv \
  --population 1 \
  --generations 0 \
  --elite-size 1 \
  --export-json /Users/cyt/Desktop/OperatorsDraft/exports/test3.json \
  --task-id test3
```

You can also inspect the CLI help:

```bash
./run_evoflow.sh --help
```

## Example Result

On the Hurricane Sandy sample with a backend-ready point-hotspot task, the current system can produce:

- `ViewType: Point`
- `BackendBuilt: True`
- `EncodeTimeOperator + ApplySpatialFilterOperator + ApplyTemporalFilterOperator + CombineFiltersOperator + AdaptedIATKViewBuilderOperator`
- a final exported Unity-facing JSON with `schemaVersion: 2.0.0`

Recent example scores:

- `ExecutionScore: 0.6025`
- `LLMScore: 0.6`
- `Fitness: 0.756`

## Unity Export

The backend currently exports a Unity-facing JSON contract with this top-level structure:

```json
{
  "meta": {},
  "task": {},
  "selectedWorkflow": {},
  "visualization": {},
  "resultSummary": {}
}
```

The most important section is `visualization`, which now uses a more explicit fixed structure:

- `intent`
- `renderPlan`
- `dataSummary`
- `semanticSummary`

For lightweight schema alignment there is also a smaller sample file:

- [test3_schema_sample.json](/Users/cyt/Desktop/OperatorsDraft/exports/test3_schema_sample.json)

For real runtime-side integration, use the full artifact:

- [test3.json](/Users/cyt/Desktop/OperatorsDraft/exports/test3.json)

More detail:

- [UNITY_EXPORT_README_CN.md](/Users/cyt/Desktop/OperatorsDraft/UNITY_EXPORT_README_CN.md)

## Current Status

What is already working:

- natural-language task input
- CSV schema inference with heuristic + LLM-assisted fallback path
- workflow search over real C# operators
- C# runner execution
- LLM-assisted evaluation
- weakly supervised result scoring when no `expectedRowIds` are available
- Unity-facing export JSON generation

What is still improving:

- hotspot quality and concentration
- LLM timeout / retry stability
- broader cross-dataset generalization
- further simplification of the Unity-facing contract

## Suggested Repo Name

Recommended GitHub repository name:

- `evoflow-vis-runtime`

Other acceptable alternatives:

- `evoflow-vis-backend`
- `nl2vis-operator-runtime`
- `evoflow-unity-export`

## Project Notes

Supporting project notes:

- [UPDATE_EVOFLOW_OPERATOR_WORKFLOW_CN.md](/Users/cyt/Desktop/OperatorsDraft/UPDATE_EVOFLOW_OPERATOR_WORKFLOW_CN.md)
- [EVOFLOW_INTERFACE_SPEC_CN.md](/Users/cyt/Desktop/OperatorsDraft/EVOFLOW_INTERFACE_SPEC_CN.md)
- [ADVISOR_NOTE_CN.md](/Users/cyt/Desktop/OperatorsDraft/ADVISOR_NOTE_CN.md)

## Summary

This repository is currently best understood as a **backend research prototype** for:

- natural-language visualization planning
- operator workflow search
- C# visualization execution
- LLM-assisted evaluation
- Unity-facing result export

It is already beyond a toy demo, but it is still an actively evolving prototype rather than a finished product.
