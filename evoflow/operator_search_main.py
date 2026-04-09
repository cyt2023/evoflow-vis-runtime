import argparse
import concurrent.futures
import csv
import json
import os
import random
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from real_llm import run_qwen_llm


ROOT = Path(__file__).resolve().parent.parent
RUNNER_PROJECT = ROOT / "OperatorRunner" / "OperatorRunner.csproj"
RUNNER_DLL = ROOT / "OperatorRunner" / "bin" / "Debug" / "net8.0" / "OperatorRunner.dll"
DOTNET_PATH = ROOT / ".dotnet" / "dotnet"

POPULATION_SIZE = 12
GENERATIONS = 8
ELITE_SIZE = 4
MUTATION_RATE = 0.25
RANDOM_SEED = 7
VERBOSE = True
TASK_PARSE_TIMEOUT_SECONDS = 10
DATASET_SCHEMA_TIMEOUT_SECONDS = 10
WORKFLOW_EVAL_TIMEOUT_SECONDS = 30
LLM_RETRY_ATTEMPTS = 3
EXPORT_SCHEMA_VERSION = "2.0.0"
LOG_LIST_SAMPLE_SIZE = 8
LOG_TEXT_PREVIEW = 1200


@dataclass
class TaskSpec:
    name: str
    description: str
    request: dict


@dataclass(frozen=True)
class DatasetProfile:
    name: str
    data_path: Path
    dataset_fields: list[str]
    trip_id_column: str
    mapping: dict
    normalize_columns: list[str]
    filter_column: str
    filter_value: str
    time_column: str
    encoded_time_column: str
    spatial_region: dict
    time_window: dict
    expected_row_ids: list[str]
    recurrent_hours: list[int] = field(default_factory=list)


@dataclass
class Candidate:
    ops: list[str]
    workflow: list[str] = field(default_factory=list)
    fitness: float = 0.0
    exec_score: float = 0.0
    llm_score: float = 0.0
    cost: float = 0.0
    response: dict = field(default_factory=dict)


DEFAULT_DESCRIPTION = (
    "Find morning-rush taxi trips whose origin is inside the downtown hotspot box, "
    "show them in an STC view, and update the backend-ready view after spatial and temporal filtering."
)

TASK = None
DATASET_PROFILE = None


ALL_OPERATORS = [
    "ReadDataOperator",
    "FilterRowsOperator",
    "NormalizeAttributesOperator",
    "EncodeTimeOperator",
    "MapToVisualSpaceOperator",
    "BuildPointViewOperator",
    "BuildSTCViewOperator",
    "Build2DProjectionViewOperator",
    "BuildLinkViewOperator",
    "CreateAtomicQueryOperator",
    "CreateDirectionalQueryOperator",
    "MergeQueriesOperator",
    "RecurrentQueryComposeOperator",
    "ApplySpatialFilterOperator",
    "ApplyTemporalFilterOperator",
    "CombineFiltersOperator",
    "UpdateViewEncodingOperator",
    "AdaptedIATKViewBuilderOperator",
]

WORKFLOW_CACHE: dict[tuple[str, ...], dict] = {}
LLM_CACHE: dict[tuple[str, ...], tuple[float, str]] = {}
TASK_PARSE_CACHE: dict[str, TaskSpec] = {}
DATASET_PROFILE_CACHE: dict[str, DatasetProfile] = {}


def read_dataset_header(data_path: Path) -> list[str]:
    with data_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
    normalized = []
    for index, column in enumerate(header):
        column_name = (column or "").strip()
        normalized.append(column_name if column_name else f"column_{index}")
    return normalized


def load_dataset_preview(data_path: Path, sample_size: int = 5) -> tuple[list[str], list[dict]]:
    with data_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        raw_header = next(reader)
        fields = [(column or "").strip() if (column or "").strip() else f"column_{index}" for index, column in enumerate(raw_header)]
        rows = []
        for raw_row in reader:
            if len(rows) >= sample_size:
                break
            row = {}
            for index, field in enumerate(fields):
                row[field] = raw_row[index] if index < len(raw_row) else ""
            rows.append(row)
    return fields, rows


def looks_like_float(value: str) -> bool:
    try:
        float(str(value).strip())
        return True
    except (TypeError, ValueError):
        return False


def looks_like_datetime(value: str) -> bool:
    text = str(value).strip()
    if not text:
        return False
    patterns = [
        r"^\d{4}-\d{2}-\d{2}",
        r"^\d{2}/\d{2}/\d{4}",
        r"^\d{4}/\d{2}/\d{2}",
        r"^\d{10,13}$",
    ]
    return any(re.match(pattern, text) for pattern in patterns)


def keyword_score(name: str, groups: list[list[str]]) -> int:
    lowered = name.lower()
    score = 0
    for group in groups:
        if any(token in lowered for token in group):
            score += 1
    return score


def find_best_column(fields: list[str], groups: list[list[str]], *, candidates: Optional[list[str]] = None) -> str:
    search_space = candidates or fields
    ranked = []
    for field in search_space:
        score = keyword_score(field, groups)
        if score > 0:
            ranked.append((score, len(field), field))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return ranked[0][2] if ranked else ""


def find_preferred_column(fields: list[str], preferred_names: list[str], *, candidates: Optional[list[str]] = None) -> str:
    search_space = candidates or fields
    lowered_map = {field.lower(): field for field in search_space}
    for preferred in preferred_names:
        if preferred.lower() in lowered_map:
            return lowered_map[preferred.lower()]
    return ""


def infer_id_column(fields: list[str], sample_rows: list[dict]) -> str:
    exact_priority = [
        "trip_id",
        "record_id",
        "row_id",
        "id",
        "uuid",
        "identifier",
    ]
    lowered_map = {field.lower(): field for field in fields}
    for candidate in exact_priority:
        if candidate in lowered_map:
            return lowered_map[candidate]

    if fields and fields[0] == "column_0":
        values = [str(row.get("column_0", "")).strip() for row in sample_rows]
        if values and all(values):
            return "column_0"

    ranked = []
    for field in fields:
        lowered = field.lower()
        score = 0
        if lowered.endswith("_id"):
            score += 4
        if lowered == "id":
            score += 4
        if "uuid" in lowered or "identifier" in lowered:
            score += 4
        if score > 0:
            ranked.append((score, len(field), field))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return ranked[0][2] if ranked else (fields[0] if fields else "")


def infer_dataset_profile_heuristic(data_path: Path, fields: list[str], sample_rows: list[dict]) -> DatasetProfile:
    numeric_columns = []
    time_columns = []
    for field in fields:
        values = [str(row.get(field, "")).strip() for row in sample_rows if str(row.get(field, "")).strip()]
        if values and sum(looks_like_float(value) for value in values) >= max(1, len(values) // 2):
            numeric_columns.append(field)
        if values and sum(looks_like_datetime(value) for value in values) >= max(1, len(values) // 2):
            time_columns.append(field)

    id_column = infer_id_column(fields, sample_rows)

    origin_x = find_best_column(fields, [["pickup", "origin", "start"], ["longitude", "lon", "lng", "_x", " x"]], candidates=numeric_columns)
    origin_y = find_best_column(fields, [["pickup", "origin", "start"], ["latitude", "lat", "_y", " y"]], candidates=numeric_columns)
    destination_x = find_best_column(fields, [["dropoff", "destination", "end"], ["longitude", "lon", "lng", "_x", " x"]], candidates=numeric_columns)
    destination_y = find_best_column(fields, [["dropoff", "destination", "end"], ["latitude", "lat", "_y", " y"]], candidates=numeric_columns)

    generic_x = find_best_column(fields, [["longitude", "lon", "lng", "_x", " x"]], candidates=numeric_columns)
    generic_y = find_best_column(fields, [["latitude", "lat", "_y", " y"]], candidates=numeric_columns)

    data_kind = "OD" if all([origin_x, origin_y, destination_x, destination_y]) else "Point"
    time_column = (
        find_preferred_column(fields, ["pickup_datetime", "pickup_time", "time", "datetime"], candidates=time_columns)
        or find_best_column(fields, [["time", "date", "timestamp", "datetime"]], candidates=time_columns)
        or (time_columns[0] if time_columns else "")
    )

    color_column = (
        find_preferred_column(
            fields,
            ["fare_amount", "fare", "total_amount", "total", "amount", "tip_amount", "tip"],
            candidates=numeric_columns,
        )
        or find_best_column(fields, [["fare", "amount", "price", "value", "score", "tip", "total"]], candidates=numeric_columns)
    )
    size_column = (
        find_preferred_column(fields, ["passenger_count", "passengers", "count", "size"], candidates=numeric_columns)
        or find_best_column(fields, [["passenger", "count", "size", "volume", "weight"]], candidates=numeric_columns)
    )

    excluded_numeric = {id_column, origin_x, origin_y, destination_x, destination_y, generic_x, generic_y}
    if not color_column:
        color_column = next((field for field in numeric_columns if field not in excluded_numeric | {size_column}), "")
    if not size_column:
        size_column = next((field for field in numeric_columns if field not in excluded_numeric | {color_column}), "")

    filter_column = find_best_column(fields, [["passenger", "count", "category", "type", "class"]], candidates=fields)
    filter_value = "1" if filter_column and ("count" in filter_column.lower() or "passenger" in filter_column.lower()) else ""

    normalize_columns = []
    for column in [origin_x, origin_y, destination_x, destination_y] if data_kind == "OD" else [generic_x, generic_y]:
        if column and column not in normalize_columns:
            normalize_columns.append(column)
    for column in [size_column, color_column]:
        if column and column not in normalize_columns:
            normalize_columns.append(column)
    for column in numeric_columns:
        if column not in normalize_columns and column != id_column:
            normalize_columns.append(column)

    if data_kind == "OD":
        mapping = {
            "tripIdColumn": id_column,
            "originXColumn": origin_x,
            "originYColumn": origin_y,
            "destinationXColumn": destination_x,
            "destinationYColumn": destination_y,
            "originTimeColumn": "EncodedTime" if time_column else "",
            "destinationTimeColumn": "EncodedTime" if time_column else "",
            "colorColumn": color_column,
            "sizeColumn": size_column,
            "isSTCMode": True,
        }
    else:
        mapping = {
            "tripIdColumn": id_column,
            "xColumn": generic_x,
            "yColumn": generic_y,
            "timeColumn": "EncodedTime" if time_column else "",
            "colorColumn": color_column,
            "sizeColumn": size_column,
            "isSTCMode": True,
        }

    return DatasetProfile(
        name=f"inferred_{data_path.stem}",
        data_path=data_path.resolve(),
        dataset_fields=fields,
        trip_id_column=id_column,
        mapping=mapping,
        normalize_columns=[column for column in normalize_columns if column],
        filter_column=filter_column,
        filter_value=filter_value,
        time_column=time_column,
        encoded_time_column="EncodedTime",
        spatial_region={
            "minX": 0.15,
            "maxX": 0.85,
            "minY": 0.15,
            "maxY": 0.85,
            "minTime": 0.0,
            "maxTime": 86400.0 if time_column else 1.0,
        },
        time_window={
            "start": 21600.0 if time_column else 0.0,
            "end": 36000.0 if time_column else 1.0,
        },
        expected_row_ids=[],
        recurrent_hours=[7, 8, 9] if time_column else [],
    )


def infer_dataset_profile_with_llm(data_path: Path, heuristic_profile: DatasetProfile, sample_rows: list[dict]) -> Optional[DatasetProfile]:
    prompt = f"""
You are inferring a dataset schema for an EvoFlow visualization backend.

CSV path:
{data_path}

Headers:
{json.dumps(heuristic_profile.dataset_fields, ensure_ascii=False)}

Sample rows:
{json.dumps(sample_rows, ensure_ascii=False, indent=2)}

Heuristic baseline:
{json.dumps({
    "tripIdColumn": heuristic_profile.trip_id_column,
    "mapping": heuristic_profile.mapping,
    "normalizeColumns": heuristic_profile.normalize_columns,
    "filterColumn": heuristic_profile.filter_column,
    "filterValue": heuristic_profile.filter_value,
    "timeColumn": heuristic_profile.time_column,
}, ensure_ascii=False, indent=2)}

Return JSON only in this shape:
{{
  "dataKind": "OD|Point",
  "tripIdColumn": "column name or empty",
  "originXColumn": "column name or empty",
  "originYColumn": "column name or empty",
  "destinationXColumn": "column name or empty",
  "destinationYColumn": "column name or empty",
  "xColumn": "column name or empty",
  "yColumn": "column name or empty",
  "timeColumn": "column name or empty",
  "colorColumn": "column name or empty",
  "sizeColumn": "column name or empty",
  "filterColumn": "column name or empty",
  "filterValue": "string value or empty",
  "normalizeColumns": ["column1", "column2"],
  "notes": "short note"
}}

Rules:
- Use only headers that actually exist.
- Prefer OD if there are clear origin/pickup and destination/dropoff coordinate pairs.
- Prefer Point if there is only one coordinate pair.
- timeColumn should be a real time/date column if available.
- normalizeColumns should only include numeric columns.
""".strip()

    log_text_block("\n=== Step 0A: Dataset Schema LLM Prompt ===", prompt)
    log(f"[Progress] Calling LLM to infer dataset schema (timeout={DATASET_SCHEMA_TIMEOUT_SECONDS}s)...")
    answer = call_llm_with_timeout(
        model_size="small",
        prompt=prompt,
        temperature=0.1,
        timeout_seconds=DATASET_SCHEMA_TIMEOUT_SECONDS,
        label="Dataset Schema",
        retries=2,
    )

    if not answer or answer.strip().upper() == "ERROR":
        log("[Dataset Schema] LLM schema inference failed. Using heuristic schema.")
        return None

    log_text_block("\n=== Step 0B: Dataset Schema LLM Raw Response ===", answer)
    match = re.search(r"\{.*\}", answer, flags=re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    fields = set(heuristic_profile.dataset_fields)
    data_kind = parsed.get("dataKind", "OD")
    if data_kind not in {"OD", "Point"}:
        data_kind = "OD" if all(
            heuristic_profile.mapping.get(key)
            for key in ("originXColumn", "originYColumn", "destinationXColumn", "destinationYColumn")
        ) else "Point"

    def valid(name: str) -> str:
        return name if name in fields else ""

    normalize_columns = [column for column in (parsed.get("normalizeColumns") or []) if column in fields]
    if not normalize_columns:
        normalize_columns = heuristic_profile.normalize_columns

    time_column = valid(parsed.get("timeColumn", "")) or heuristic_profile.time_column
    trip_id_column = valid(parsed.get("tripIdColumn", "")) or heuristic_profile.trip_id_column
    color_column = valid(parsed.get("colorColumn", "")) or heuristic_profile.mapping.get("colorColumn", "")
    size_column = valid(parsed.get("sizeColumn", "")) or heuristic_profile.mapping.get("sizeColumn", "")
    filter_column = valid(parsed.get("filterColumn", "")) or heuristic_profile.filter_column
    filter_value = parsed.get("filterValue", heuristic_profile.filter_value)

    if data_kind == "OD":
        mapping = {
            "tripIdColumn": trip_id_column,
            "originXColumn": valid(parsed.get("originXColumn", "")) or heuristic_profile.mapping.get("originXColumn", ""),
            "originYColumn": valid(parsed.get("originYColumn", "")) or heuristic_profile.mapping.get("originYColumn", ""),
            "destinationXColumn": valid(parsed.get("destinationXColumn", "")) or heuristic_profile.mapping.get("destinationXColumn", ""),
            "destinationYColumn": valid(parsed.get("destinationYColumn", "")) or heuristic_profile.mapping.get("destinationYColumn", ""),
            "originTimeColumn": "EncodedTime" if time_column else "",
            "destinationTimeColumn": "EncodedTime" if time_column else "",
            "colorColumn": color_column,
            "sizeColumn": size_column,
            "isSTCMode": True,
        }
    else:
        mapping = {
            "tripIdColumn": trip_id_column,
            "xColumn": valid(parsed.get("xColumn", "")) or heuristic_profile.mapping.get("xColumn", ""),
            "yColumn": valid(parsed.get("yColumn", "")) or heuristic_profile.mapping.get("yColumn", ""),
            "timeColumn": "EncodedTime" if time_column else "",
            "colorColumn": color_column,
            "sizeColumn": size_column,
            "isSTCMode": True,
        }

    profile = DatasetProfile(
        name=f"schema_{data_path.stem}",
        data_path=data_path.resolve(),
        dataset_fields=heuristic_profile.dataset_fields,
        trip_id_column=trip_id_column,
        mapping=mapping,
        normalize_columns=normalize_columns,
        filter_column=filter_column,
        filter_value=filter_value,
        time_column=time_column,
        encoded_time_column="EncodedTime",
        spatial_region=heuristic_profile.spatial_region,
        time_window=heuristic_profile.time_window,
        expected_row_ids=[],
        recurrent_hours=[7, 8, 9] if time_column else [],
    )
    log_json("\n=== Step 0C: Inferred Dataset Schema ===", {
        "name": profile.name,
        "mapping": profile.mapping,
        "normalizeColumns": profile.normalize_columns,
        "filterColumn": profile.filter_column,
        "timeColumn": profile.time_column,
    })
    return profile


def resolve_dataset_profile(data_path: Union[str, Path]) -> DatasetProfile:
    path = Path(data_path).resolve()
    cache_key = str(path)
    if cache_key in DATASET_PROFILE_CACHE:
        log("[Dataset Schema] Reusing cached dataset profile.")
        return DATASET_PROFILE_CACHE[cache_key]

    fields, sample_rows = load_dataset_preview(path)
    log("\n=== Step 0: Dataset Preview ===")
    log_json("Dataset sample:", {"path": str(path), "fields": fields, "sampleRows": sample_rows})

    heuristic_profile = infer_dataset_profile_heuristic(path, fields, sample_rows)
    log_json("\n=== Step 0: Heuristic Dataset Schema ===", {
        "name": heuristic_profile.name,
        "mapping": heuristic_profile.mapping,
        "normalizeColumns": heuristic_profile.normalize_columns,
        "filterColumn": heuristic_profile.filter_column,
        "timeColumn": heuristic_profile.time_column,
    })

    profile = infer_dataset_profile_with_llm(path, heuristic_profile, sample_rows) or heuristic_profile
    DATASET_PROFILE_CACHE[cache_key] = profile
    return profile


def default_required_view_type(description: str) -> str:
    lower = description.lower()
    if "projection" in lower or "2d" in lower:
        return "Projection2D"
    if "link" in lower:
        return "Link"
    if "point" in lower or "点图" in description or "散点" in description or "点状" in description:
        return "Point"
    return "STC"


def default_atomic_mode(description: str) -> str:
    lower = description.lower()
    return "Destination" if "destination" in lower and "origin" not in lower else "Origin"


def infer_task_hints(description: str) -> dict:
    lower = description.lower()
    require_backend = any(token in lower for token in ("backend", "render", "display", "visualization", "view"))
    require_temporal = any(
        token in lower
        for token in ("temporal", "time", "morning", "rush", "hour", "peak", "daily", "weekly", "monthly")
    )
    require_spatial = any(
        token in lower
        for token in ("spatial", "origin", "destination", "pickup", "dropoff", "region", "location", "hotspot")
    )
    hotspot_focus = any(token in lower for token in ("hotspot", "cluster", "focus", "concentrat", "peak"))
    return {
        "requireBackendBuild": require_backend,
        "requireTemporalFilter": require_temporal,
        "requireSpatialFilter": require_spatial,
        "hotspotFocus": hotspot_focus,
    }


def build_task_request(
    description: str,
    profile: DatasetProfile,
    *,
    required_view_type: str,
    atomic_mode: str,
    require_backend: bool,
    normalize_columns: Optional[list[str]] = None,
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
    time_column: Optional[str] = None,
    encoded_time_column: Optional[str] = None,
    spatial_region: Optional[dict] = None,
    time_window: Optional[dict] = None,
    expected_row_ids: Optional[list[str]] = None,
    recurrent_hours: Optional[list[int]] = None,
) -> dict:
    mapping = json.loads(json.dumps(profile.mapping))
    mapping["isSTCMode"] = required_view_type == "STC"
    task_hints = infer_task_hints(description)
    task_hints["requireBackendBuild"] = require_backend
    request = {
        "taskDescription": description,
        "dataPath": str(profile.data_path),
        "datasetProfile": profile.name,
        "mapping": mapping,
        "normalizeColumns": normalize_columns or list(profile.normalize_columns),
        "filterColumn": filter_column if filter_column is not None else profile.filter_column,
        "filterValue": filter_value if filter_value is not None else profile.filter_value,
        "timeColumn": time_column or profile.time_column,
        "encodedTimeColumn": encoded_time_column or profile.encoded_time_column,
        "spatialRegion": spatial_region or dict(profile.spatial_region),
        "timeWindow": time_window or dict(profile.time_window),
        "atomicMode": atomic_mode,
        "requiredViewType": required_view_type,
        "expectedRowIds": expected_row_ids if expected_row_ids is not None else list(profile.expected_row_ids),
        "requireBackendBuild": require_backend,
        "recurrentHours": recurrent_hours if recurrent_hours is not None else list(profile.recurrent_hours),
        "taskHints": task_hints,
    }
    return request


def log(message: str = "") -> None:
    if VERBOSE:
        print(message, flush=True)


def summarize_for_log(value):
    if isinstance(value, dict):
        summarized = {}
        for key, item in value.items():
            if key in {"selectedRowIds", "points", "links", "samplePoints"} and isinstance(item, list):
                summarized[key] = {
                    "count": len(item),
                    "sample": [summarize_for_log(entry) for entry in item[:LOG_LIST_SAMPLE_SIZE]],
                }
            else:
                summarized[key] = summarize_for_log(item)
        return summarized
    if isinstance(value, list):
        if len(value) > LOG_LIST_SAMPLE_SIZE:
            return {
                "count": len(value),
                "sample": [summarize_for_log(entry) for entry in value[:LOG_LIST_SAMPLE_SIZE]],
            }
        return [summarize_for_log(entry) for entry in value]
    if isinstance(value, str) and len(value) > LOG_TEXT_PREVIEW:
        return value[:LOG_TEXT_PREVIEW] + "...<truncated>"
    return value


def log_json(title: str, data: dict) -> None:
    if VERBOSE:
        print(title, flush=True)
        print(json.dumps(summarize_for_log(data), indent=2, ensure_ascii=False), flush=True)


def log_text_block(title: str, text: str) -> None:
    if not VERBOSE:
        return
    preview = text if len(text) <= LOG_TEXT_PREVIEW else text[:LOG_TEXT_PREVIEW] + "...<truncated>"
    print(title, flush=True)
    print(preview, flush=True)


def summarize_selected_ids(ids: list[str]) -> str:
    if not ids:
        return "count=0"
    sample = ids[:LOG_LIST_SAMPLE_SIZE]
    suffix = " ..." if len(ids) > LOG_LIST_SAMPLE_SIZE else ""
    return f"count={len(ids)} sample={sample}{suffix}"


def call_llm_with_timeout(
    *,
    model_size: str,
    prompt: str,
    temperature: float,
    timeout_seconds: int,
    label: str,
    retries: int = 1,
):
    last_answer = None
    for attempt in range(1, retries + 1):
        if retries > 1:
            log(f"[{label}] Attempt {attempt}/{retries}...")
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(run_qwen_llm, model_size, prompt, temperature)
            answer = future.result(timeout=timeout_seconds)
            last_answer = answer
        except concurrent.futures.TimeoutError:
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            log(f"[{label}] Timed out after {timeout_seconds}s on attempt {attempt}/{retries}.")
            last_answer = "ERROR"
            continue
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if answer and answer.strip().upper() != "ERROR":
            return answer

        log(f"[{label}] Request failed on attempt {attempt}/{retries}.")
    return last_answer or "ERROR"


def ensure_runner_ready() -> None:
    if not DOTNET_PATH.exists():
        raise RuntimeError(
            f"Missing dotnet at {DOTNET_PATH}. Install .NET SDK into the project-local .dotnet folder first."
        )

    env = dotnet_env()
    log("[Setup] Checking and building C# operator runner...")
    subprocess.run(
        [str(DOTNET_PATH), "build", str(RUNNER_PROJECT), "-p:UseAppHost=false"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    if not RUNNER_DLL.exists():
        raise RuntimeError(f"Runner build finished, but DLL was not found at {RUNNER_DLL}")
    log("[Setup] Operator runner is ready.")


def dotnet_env() -> dict:
    env = os.environ.copy()
    env["HOME"] = str(ROOT)
    env["DOTNET_CLI_HOME"] = str(ROOT)
    env["PATH"] = f"{DOTNET_PATH.parent}:{env.get('PATH', '')}"
    return env


def random_candidate() -> Candidate:
    task_hints = TASK.request.get("taskHints", {}) if TASK else {}
    required_view = TASK.request.get("requiredViewType") if TASK else None
    preferred_view = {
        "STC": "BuildSTCViewOperator",
        "Point": "BuildPointViewOperator",
        "Projection2D": "Build2DProjectionViewOperator",
        "Link": "BuildLinkViewOperator",
    }.get(required_view)

    chosen = []
    for op in ALL_OPERATORS:
        if op == "ReadDataOperator":
            continue

        probability = 0.45
        if op == "EncodeTimeOperator" and task_hints.get("requireTemporalFilter"):
            probability = 0.85
        elif op == "ApplyTemporalFilterOperator" and task_hints.get("requireTemporalFilter"):
            probability = 0.85
        elif op == "ApplySpatialFilterOperator" and task_hints.get("requireSpatialFilter"):
            probability = 0.8
        elif op in {"UpdateViewEncodingOperator", "AdaptedIATKViewBuilderOperator"} and task_hints.get("requireBackendBuild"):
            probability = 0.85
        elif op.startswith("Build"):
            probability = 0.85 if op == preferred_view else 0.2

        if random.random() < probability:
            chosen.append(op)
    return Candidate(ops=chosen)


def fallback_task_spec(description: str, profile: DatasetProfile) -> TaskSpec:
    lower = description.lower()
    required_view_type = default_required_view_type(description)
    require_backend = "backend" in lower or "render" in lower or "view" in lower or "display" in lower
    atomic_mode = default_atomic_mode(description)

    task_name = description.strip()[:60] if description.strip() else "Interactive Task"

    return TaskSpec(
        name=task_name,
        description=description,
        request=build_task_request(
            description,
            profile,
            required_view_type=required_view_type,
            atomic_mode=atomic_mode,
            require_backend=require_backend,
        ),
    )


def parse_task_with_llm(description: str, profile: DatasetProfile) -> TaskSpec:
    cache_key = f"{profile.name}::{description}"
    if cache_key in TASK_PARSE_CACHE:
        log("[Task Parse] Reusing cached task spec.")
        return TASK_PARSE_CACHE[cache_key]

    prompt = f"""
You are converting a natural-language visualization task into a structured task spec for an EvoFlow operator search system.

Available operator pool:
{json.dumps(ALL_OPERATORS, ensure_ascii=False)}

Dataset fields:
{", ".join(profile.dataset_fields)}

Return valid JSON only with this shape:
{{
  "taskName": "short name",
  "requiredViewType": "STC|Projection2D|Point|Link",
  "atomicMode": "Origin|Destination|Either",
  "requireBackendBuild": true,
  "normalizeColumns": {json.dumps(profile.normalize_columns[:4], ensure_ascii=False)},
  "filterColumn": "{profile.filter_column}",
  "filterValue": "{profile.filter_value}",
  "timeColumn": "{profile.time_column}",
  "encodedTimeColumn": "EncodedTime",
  "spatialRegion": {json.dumps(profile.spatial_region, ensure_ascii=False)},
  "timeWindow": {json.dumps(profile.time_window, ensure_ascii=False)},
  "expectedRowIds": {json.dumps(profile.expected_row_ids, ensure_ascii=False)}
}}

Guidelines:
- Use only the allowed requiredViewType values.
- Keep normalizeColumns to valid numeric dataset columns only.
- If the task does not mention row filtering, set filterColumn to "" and filterValue to "".
- If the task does not clearly require backend/rendering, set requireBackendBuild to false.
- If uncertain, choose sensible defaults for this dataset.

Task description:
{description}
""".strip()

    log("\n=== Step 1: Raw Task ===")
    log(description)
    log_text_block("\n=== Step 2: LLM Task Parsing Prompt ===", prompt)
    log(f"[Progress] Calling LLM to parse the natural-language task (timeout={TASK_PARSE_TIMEOUT_SECONDS}s)...")
    answer = call_llm_with_timeout(
        model_size="small",
        prompt=prompt,
        temperature=0.1,
        timeout_seconds=TASK_PARSE_TIMEOUT_SECONDS,
        label="Task Parse",
        retries=2,
    )

    if not answer or answer.strip().upper() == "ERROR":
        log("[Task Parse] LLM parsing failed. Falling back to heuristic task spec.")
        task = fallback_task_spec(description, profile)
        TASK_PARSE_CACHE[cache_key] = task
        log_json("\n=== Step 3: Parsed Task Spec (Fallback) ===", task.request)
        return task
    log("[Progress] LLM task parsing finished.")

    log_text_block("\n=== Step 3: LLM Task Parsing Raw Response ===", answer)
    match = re.search(r"\{.*\}", answer, flags=re.DOTALL)
    if not match:
        log("[Task Parse] No JSON found in LLM output. Falling back to heuristic task spec.")
        task = fallback_task_spec(description, profile)
        TASK_PARSE_CACHE[cache_key] = task
        log_json("\n=== Step 3: Parsed Task Spec (Fallback) ===", task.request)
        return task

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        log("[Task Parse] JSON decoding failed. Falling back to heuristic task spec.")
        task = fallback_task_spec(description, profile)
        TASK_PARSE_CACHE[cache_key] = task
        log_json("\n=== Step 3: Parsed Task Spec (Fallback) ===", task.request)
        return task

    required_view_type = parsed.get("requiredViewType", default_required_view_type(description))
    if required_view_type not in {"STC", "Projection2D", "Point", "Link"}:
        required_view_type = default_required_view_type(description)

    atomic_mode = parsed.get("atomicMode", default_atomic_mode(description))
    if atomic_mode not in {"Origin", "Destination", "Either"}:
        atomic_mode = default_atomic_mode(description)

    normalize_columns = parsed.get("normalizeColumns") or list(profile.normalize_columns)

    filter_column = parsed.get("filterColumn", "")
    filter_value = parsed.get("filterValue", "")

    task = TaskSpec(
        name=parsed.get("taskName") or description.strip()[:60] or "Interactive Task",
        description=description,
        request=build_task_request(
            description,
            profile,
            required_view_type=required_view_type,
            atomic_mode=atomic_mode,
            require_backend=bool(parsed.get("requireBackendBuild", False)),
            normalize_columns=normalize_columns,
            filter_column=filter_column,
            filter_value=filter_value,
            time_column=parsed.get("timeColumn", profile.time_column),
            encoded_time_column=parsed.get("encodedTimeColumn", profile.encoded_time_column),
            spatial_region=parsed.get("spatialRegion") or dict(profile.spatial_region),
            time_window=parsed.get("timeWindow") or dict(profile.time_window),
            expected_row_ids=parsed.get("expectedRowIds"),
            recurrent_hours=parsed.get("recurrentHours") or list(profile.recurrent_hours),
        ),
    )
    TASK_PARSE_CACHE[cache_key] = task
    log_json("\n=== Step 3: Parsed Task Spec ===", task.request)
    return task


def build_workflow(candidate: Candidate) -> list[str]:
    chosen = set(candidate.ops)
    task_hints = TASK.request.get("taskHints", {}) if TASK else {}
    required_view = TASK.request.get("requiredViewType", "Point") if TASK else "Point"
    preferred_view = {
        "STC": "BuildSTCViewOperator",
        "Point": "BuildPointViewOperator",
        "Projection2D": "Build2DProjectionViewOperator",
        "Link": "BuildLinkViewOperator",
    }.get(required_view, "BuildPointViewOperator")

    workflow = ["ReadDataOperator"]

    if "FilterRowsOperator" in chosen:
        workflow.append("FilterRowsOperator")
    if "NormalizeAttributesOperator" in chosen:
        workflow.append("NormalizeAttributesOperator")
    if "EncodeTimeOperator" in chosen or (task_hints.get("requireTemporalFilter") and TASK.request.get("timeColumn")):
        workflow.append("EncodeTimeOperator")

    # Mapping is the bridge from tabular data to view/filter operators.
    workflow.append("MapToVisualSpaceOperator")

    view_ops = [op for op in ALL_OPERATORS if op.startswith("Build") and op in chosen]
    if view_ops:
        view_op = preferred_view if preferred_view in view_ops else view_ops[0]
    else:
        view_op = preferred_view
    workflow.append(view_op)

    query_ops = [op for op in (
        "CreateAtomicQueryOperator",
        "CreateDirectionalQueryOperator",
        "RecurrentQueryComposeOperator",
        "MergeQueriesOperator",
    ) if op in chosen]

    if "CreateDirectionalQueryOperator" in query_ops and "CreateAtomicQueryOperator" not in query_ops:
        query_ops.insert(0, "CreateAtomicQueryOperator")
    if "MergeQueriesOperator" in query_ops and not any(
        op in query_ops for op in ("CreateDirectionalQueryOperator", "RecurrentQueryComposeOperator")
    ):
        query_ops.remove("MergeQueriesOperator")

    workflow.extend(query_ops)

    filter_ops = [op for op in ("ApplySpatialFilterOperator", "ApplyTemporalFilterOperator") if op in chosen]
    if task_hints.get("requireSpatialFilter") and "ApplySpatialFilterOperator" not in filter_ops:
        filter_ops.append("ApplySpatialFilterOperator")
    if task_hints.get("requireTemporalFilter") and TASK.request.get("timeColumn") and "ApplyTemporalFilterOperator" not in filter_ops:
        filter_ops.append("ApplyTemporalFilterOperator")
    if "ApplySpatialFilterOperator" in filter_ops and "CreateAtomicQueryOperator" not in workflow:
        workflow.insert(workflow.index(view_op) + 1, "CreateAtomicQueryOperator")
    workflow.extend(filter_ops)

    if "CombineFiltersOperator" in chosen and all(op in workflow for op in ("ApplySpatialFilterOperator", "ApplyTemporalFilterOperator")):
        workflow.append("CombineFiltersOperator")

    if "UpdateViewEncodingOperator" in chosen or task_hints.get("requireBackendBuild"):
        workflow.append("UpdateViewEncodingOperator")

    if "AdaptedIATKViewBuilderOperator" in chosen or task_hints.get("requireBackendBuild"):
        workflow.append("AdaptedIATKViewBuilderOperator")

    # Remove duplicates while preserving the legal repaired order.
    deduped = []
    for op in workflow:
        if op not in deduped:
            deduped.append(op)
    return deduped


def mutate(candidate: Candidate) -> Candidate:
    child = Candidate(ops=list(candidate.ops))
    current = set(child.ops)
    for op in ALL_OPERATORS:
        if op == "ReadDataOperator":
            continue
        if random.random() < MUTATION_RATE:
            if op in current:
                current.remove(op)
            else:
                current.add(op)
    child.ops = list(current)
    child.workflow = []
    child.fitness = 0.0
    child.exec_score = 0.0
    child.llm_score = 0.0
    child.cost = 0.0
    child.response = {}
    return child


def crossover(left: Candidate, right: Candidate) -> Candidate:
    merged = []
    for op in ALL_OPERATORS:
        if op == "ReadDataOperator":
            continue
        if op in left.ops or op in right.ops:
            if random.choice([True, False]):
                merged.append(op)
    return Candidate(ops=merged)


def prepare_request(workflow: list[str]) -> dict:
    request = json.loads(json.dumps(TASK.request))
    request["workflow"] = workflow
    if "EncodeTimeOperator" not in workflow:
        fallback_time = request.get("timeColumn", "")
        request["mapping"]["originTimeColumn"] = fallback_time
        request["mapping"]["destinationTimeColumn"] = fallback_time
    return request


def run_workflow(workflow: list[str]) -> dict:
    key = tuple(workflow)
    if key in WORKFLOW_CACHE:
        log(f"[Runner] Cache hit for workflow: {workflow}")
        return WORKFLOW_CACHE[key]

    request = prepare_request(workflow)
    env = dotnet_env()
    log("\n=== Step 5: Executing Workflow ===")
    log(f"Workflow: {workflow}")
    log_json("Runner request:", request)
    log("[Progress] Calling C# operator runner...")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(request, handle)
        request_path = handle.name

    try:
        completed = subprocess.run(
            [
                str(DOTNET_PATH),
                str(RUNNER_DLL),
                "--request",
                request_path,
            ],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        response = json.loads(completed.stdout)
        log("[Progress] C# operator runner finished.")
        WORKFLOW_CACHE[key] = response
        log_json("Runner response:", response)
        return response
    finally:
        Path(request_path).unlink(missing_ok=True)


def llm_evaluate_workflow(workflow: list[str], response: dict) -> tuple[float, str]:
    key = tuple(workflow)
    if key in LLM_CACHE:
        log(f"[LLM Eval] Cache hit for workflow: {workflow}")
        return LLM_CACHE[key]

    diagnostics = response.get("diagnostics", {})
    selection_summary = {
        "selectedRowCount": len(response.get("selectedRowIds", [])),
        "selectedRowSample": response.get("selectedRowIds", [])[:LOG_LIST_SAMPLE_SIZE],
        "selectedPointCount": response.get("selectedPointCount"),
        "totalRows": response.get("totalRows"),
        "backendBuilt": response.get("backendBuilt"),
    }
    evaluation_summary = {
        "viewType": response.get("viewType"),
        "selectionSummary": selection_summary,
        "selfEvaluation": response.get("selfEvaluation"),
        "diagnosticsSummary": {
            "spatialSelectedCount": diagnostics.get("spatialSelectedCount"),
            "temporalSelectedCount": diagnostics.get("temporalSelectedCount"),
            "finalSelectedCount": diagnostics.get("finalSelectedCount"),
            "spatialTargetRole": diagnostics.get("spatialTargetRole"),
            "temporalTargetRole": diagnostics.get("temporalTargetRole"),
            "finalTargetRole": diagnostics.get("finalTargetRole"),
        },
    }

    prompt = f"""
You are evaluating whether an operator workflow successfully completed a visualization task.

Task:
{TASK.description}

Workflow:
{json.dumps(workflow, ensure_ascii=False)}

Execution result:
{json.dumps(evaluation_summary, ensure_ascii=False)}

Give a single overall score from 0.0 to 1.0 for how well this workflow seems to satisfy the task.
Return exactly two lines:
score: <number>
reason: <short sentence>
""".strip()

    log_text_block("\n=== Step 6: LLM Workflow Evaluation Prompt ===", prompt)
    log("[Progress] Calling LLM to evaluate workflow quality...")
    answer = call_llm_with_timeout(
        model_size="small",
        prompt=prompt,
        temperature=0.2,
        timeout_seconds=WORKFLOW_EVAL_TIMEOUT_SECONDS,
        label="LLM Eval",
        retries=LLM_RETRY_ATTEMPTS,
    )
    if not answer or answer.strip().upper() == "ERROR":
        result = (0.5, "LLM evaluation unavailable.")
        LLM_CACHE[key] = result
        log("[LLM Eval] LLM evaluation failed or timed out; using fallback score 0.5.")
        return result
    log("[Progress] LLM workflow evaluation finished.")

    log_text_block("\n=== Step 7: LLM Workflow Evaluation Raw Response ===", answer)
    match = re.search(r"score\s*:\s*([0-9]*\.?[0-9]+)", answer, flags=re.IGNORECASE)
    if not match:
        result = (0.5, answer.strip().splitlines()[-1][:120])
        LLM_CACHE[key] = result
        log(f"[LLM Eval] Could not parse score; fallback result: {result}")
        return result

    score = float(match.group(1))
    if score > 1.0:
        score = score / 100.0
    score = max(0.0, min(1.0, score))

    reason_match = re.search(r"reason\s*:\s*(.+)", answer, flags=re.IGNORECASE)
    reason = reason_match.group(1).strip() if reason_match else answer.strip().splitlines()[-1][:120]
    result = (score, reason)
    LLM_CACHE[key] = result
    log(f"[LLM Eval] Parsed score={score:.3f}, reason={reason}")
    return result


def evaluate_candidate(candidate: Candidate) -> Candidate:
    workflow = build_workflow(candidate)
    log("\n=== Step 4: Candidate Workflow Proposal ===")
    log(f"Chosen operator pool subset: {candidate.ops}")
    log(f"Repaired executable workflow: {workflow}")
    log("[Progress] Evaluating one candidate workflow...")
    response = run_workflow(workflow)

    exec_score = float(response["selfEvaluation"]["score"])
    llm_score, llm_reason = llm_evaluate_workflow(workflow, response)
    selected_ids = response.get("selectedRowIds", [])
    expected_ids = TASK.request["expectedRowIds"]
    diagnostics = response.get("diagnostics", {})
    task_hints = TASK.request.get("taskHints", {})
    required_view = TASK.request["requiredViewType"]

    exact_match_bonus = 0.1 if expected_ids and selected_ids == expected_ids else 0.0
    view_match = response.get("viewType") == required_view
    view_bonus = 0.08 if view_match else 0.0
    backend_required = bool(TASK.request.get("requireBackendBuild"))
    backend_ready = bool(response.get("backendBuilt"))
    backend_bonus = 0.08 if backend_required and backend_ready else (0.03 if backend_ready else 0.0)

    temporal_required = bool(task_hints.get("requireTemporalFilter"))
    spatial_required = bool(task_hints.get("requireSpatialFilter"))
    hotspot_focus = bool(task_hints.get("hotspotFocus"))

    temporal_hits = diagnostics.get("temporalSelectedCount") or 0
    spatial_hits = diagnostics.get("spatialSelectedCount") or 0
    final_hits = diagnostics.get("finalSelectedCount") or 0
    total_rows = response.get("totalRows") or 0
    selected_count = response.get("selectedPointCount") or 0
    selection_ratio = (selected_count / total_rows) if total_rows else 0.0

    temporal_bonus = 0.06 if temporal_required and temporal_hits > 0 else 0.0
    spatial_bonus = 0.04 if spatial_required and spatial_hits > 0 else 0.0

    penalties = 0.0
    if not view_match:
        penalties += 0.12
    if backend_required and not backend_ready:
        penalties += 0.12
    if temporal_required and temporal_hits <= 0:
        penalties += 0.10
    if spatial_required and spatial_hits <= 0:
        penalties += 0.06
    if hotspot_focus and selection_ratio > 0.35:
        penalties += min(0.12, (selection_ratio - 0.35) * 0.25)
    if total_rows and final_hits == 0:
        penalties += 0.08

    cost = float(len(workflow))
    fitness = (
        (0.4 * exec_score)
        + (0.6 * llm_score)
        + exact_match_bonus
        + view_bonus
        + backend_bonus
        + temporal_bonus
        + spatial_bonus
        - (0.015 * max(0, cost - 8))
        - penalties
    )

    candidate.workflow = workflow
    candidate.response = response
    candidate.exec_score = exec_score
    candidate.llm_score = llm_score
    candidate.cost = cost
    candidate.fitness = round(fitness, 4)
    candidate.response["llmEvaluation"] = {
        "score": llm_score,
        "reason": llm_reason,
    }
    candidate.response["fitnessBreakdown"] = {
        "viewMatch": view_match,
        "backendRequired": backend_required,
        "backendReady": backend_ready,
        "temporalRequired": temporal_required,
        "temporalSelectedCount": temporal_hits,
        "spatialRequired": spatial_required,
        "spatialSelectedCount": spatial_hits,
        "hotspotFocus": hotspot_focus,
        "selectionRatio": round(selection_ratio, 4),
        "penalties": round(penalties, 4),
    }
    log(
        "[Candidate Result] "
        f"fitness={candidate.fitness:.3f} exec={candidate.exec_score:.3f} "
        f"llm={candidate.llm_score:.3f} cost={candidate.cost:.0f} "
        f"selected={summarize_selected_ids(candidate.response.get('selectedRowIds', []))} "
        f"viewMatch={view_match} backend={backend_ready} temporalHits={temporal_hits} "
        f"selectionRatio={selection_ratio:.3f}"
    )
    log("[Progress] Candidate evaluation complete.")
    return candidate


def evolve() -> list[Candidate]:
    random.seed(RANDOM_SEED)
    log("\n=== Step 4A: Initial Population Evaluation ===")
    population = [evaluate_candidate(random_candidate()) for _ in range(POPULATION_SIZE)]

    for generation in range(GENERATIONS):
        population.sort(key=lambda item: item.fitness, reverse=True)
        best = population[0]
        log(
            f"\n=== Step 8: Generation {generation} Best ===\n"
            f"[Generation {generation}] "
            f"fitness={best.fitness:.3f} exec={best.exec_score:.3f} llm={best.llm_score:.3f} cost={best.cost:.0f} "
            f"selected={summarize_selected_ids(best.response.get('selectedRowIds', []))}"
        )

        elites = population[:ELITE_SIZE]
        next_population = elites[:]

        while len(next_population) < POPULATION_SIZE:
            if len(elites) >= 2:
                left, right = random.sample(elites, 2)
            elif len(elites) == 1:
                left = right = elites[0]
            else:
                left = right = population[0]
            child = mutate(crossover(left, right))
            log(f"[Progress] Generating child workflow {len(next_population) + 1}/{POPULATION_SIZE} for generation {generation}...")
            next_population.append(evaluate_candidate(child))

        population = next_population

    population.sort(key=lambda item: item.fitness, reverse=True)
    return population


def build_unity_export(task: TaskSpec, best: Candidate, *, task_id: Optional[str] = None) -> dict:
    response = best.response
    self_eval = response.get("selfEvaluation", {})
    llm_eval = response.get("llmEvaluation", {})
    visualization_payload = response.get("visualizationPayload", {})
    request = task.request
    task_hints = request.get("taskHints", {})
    mapping = request.get("mapping", {})
    selected_row_ids = response.get("selectedRowIds", [])
    selection_state = visualization_payload.get("selectionState", {})
    source_summary = visualization_payload.get("sourceDataSummary", {})
    query_context = visualization_payload.get("queryContext", {})
    diagnostics = response.get("diagnostics", {})

    def sample_items(items: list[Any], *, limit: int = LOG_LIST_SAMPLE_SIZE) -> list[Any]:
        return list(items[:limit])

    def normalize_view(view: dict) -> dict:
        return {
            "name": view.get("viewName") or "None",
            "type": view.get("viewType") or "None",
            "role": view.get("role") or "All",
            "projection": view.get("projectionKind") or "",
            "pointCount": int(view.get("pointCount") or 0),
            "linkCount": int(view.get("linkCount") or 0),
            "backendReady": bool(view.get("backendBuilt")),
        }

    def normalize_points(points: list[dict]) -> list[dict]:
        normalized = []
        for point in points:
            normalized.append({
                "pointId": int(point.get("index", 0)),
                "sourceRowIndex": int(point.get("sourceRowIndex", 0)),
                "rowId": str(point.get("rowId", "")),
                "role": str(point.get("role", "All")),
                "position": {
                    "x": point.get("x", 0.0),
                    "y": point.get("y", 0.0),
                    "z": point.get("z", 0.0),
                },
                "timeValue": point.get("time"),
                "colorValue": point.get("colorValue"),
                "sizeValue": point.get("sizeValue"),
                "selected": bool(point.get("isSelected")),
            })
        return normalized

    def normalize_links(links: list[dict]) -> list[dict]:
        normalized = []
        for link in links:
            normalized.append({
                "linkId": int(link.get("index", 0)),
                "originPointId": int(link.get("originIndex", -1)),
                "destinationPointId": int(link.get("destinationIndex", -1)),
                "originRowId": str(link.get("originRowId", "")),
                "destinationRowId": str(link.get("destinationRowId", "")),
                "weight": link.get("weight", 0.0),
            })
        return normalized

    def build_channel_contract() -> dict:
        primary_view_type = response.get("viewType", "None")
        position_channel = {
            "x": mapping.get("originXColumn"),
            "y": mapping.get("originYColumn"),
            "z": request.get("encodedTimeColumn") if primary_view_type == "STC" else None,
            "time": request.get("timeColumn"),
        }
        return {
            "position": position_channel,
            "color": {
                "sourceColumn": mapping.get("colorColumn"),
                "valueType": "numeric" if mapping.get("colorColumn") else "none",
            },
            "size": {
                "sourceColumn": mapping.get("sizeColumn"),
                "valueType": "numeric" if mapping.get("sizeColumn") else "none",
            },
        }

    def build_filter_contract() -> dict:
        spatial_region = request.get("spatialRegion") or {}
        time_window = request.get("timeWindow") or {}
        recurrent_hours = request.get("recurrentHours", [])
        return {
            "rowFilter": {
                "enabled": bool(request.get("filterColumn")),
                "column": request.get("filterColumn") or "",
                "value": request.get("filterValue") or "",
            },
            "spatialFilter": {
                "required": bool(task_hints.get("requireSpatialFilter")),
                "applied": int(diagnostics.get("spatialSelectedCount") or 0) > 0,
                "targetRole": diagnostics.get("spatialTargetRole") or "All",
                "region": {
                    "minX": spatial_region.get("minX"),
                    "maxX": spatial_region.get("maxX"),
                    "minY": spatial_region.get("minY"),
                    "maxY": spatial_region.get("maxY"),
                    "minTime": spatial_region.get("minTime"),
                    "maxTime": spatial_region.get("maxTime"),
                },
                "selectedPointCount": int(diagnostics.get("spatialSelectedCount") or 0),
            },
            "temporalFilter": {
                "required": bool(task_hints.get("requireTemporalFilter")),
                "applied": int(diagnostics.get("temporalSelectedCount") or 0) > 0,
                "targetRole": diagnostics.get("temporalTargetRole") or "All",
                "timeColumn": request.get("timeColumn") or "",
                "encodedTimeColumn": request.get("encodedTimeColumn") or "",
                "window": {
                    "start": time_window.get("start"),
                    "end": time_window.get("end"),
                },
                "recurrentHours": recurrent_hours,
                "selectedPointCount": int(diagnostics.get("temporalSelectedCount") or 0),
            },
            "combinedSelection": {
                "applied": int(diagnostics.get("finalSelectedCount") or 0) > 0,
                "targetRole": diagnostics.get("finalTargetRole") or "All",
                "selectedPointCount": int(diagnostics.get("finalSelectedCount") or 0),
            },
        }

    def build_visualization_contract() -> dict:
        primary_view = normalize_view(visualization_payload.get("primaryView", {}))
        coordinated_views = [
            normalize_view(view)
            for view in visualization_payload.get("coordinatedViews", [])
        ]
        points = normalize_points(visualization_payload.get("points", []))
        links = normalize_links(visualization_payload.get("links", []))

        return {
            "intent": {
                "primaryViewType": request.get("requiredViewType"),
                "targetRole": request.get("atomicMode"),
                "backendReadyRequired": bool(task_hints.get("requireBackendBuild")),
                "spatialFilterRequired": bool(task_hints.get("requireSpatialFilter")),
                "temporalFilterRequired": bool(task_hints.get("requireTemporalFilter")),
                "hotspotFocus": bool(task_hints.get("hotspotFocus")),
            },
            "renderPlan": {
                "status": "ready" if response.get("backendBuilt") else "partial",
                "primaryView": primary_view,
                "coordinatedViews": coordinated_views,
                "channels": build_channel_contract(),
                "filtersApplied": build_filter_contract(),
                "selection": {
                    "selectedRowIds": selected_row_ids,
                    "selectedRowCount": len(selected_row_ids),
                    "selectedRowSample": sample_items(selected_row_ids),
                    "selectedPointCount": int(response.get("selectedPointCount") or 0),
                    "finalSelectedPointCount": int(selection_state.get("finalSelectedCount") or diagnostics.get("finalSelectedCount") or 0),
                },
                "geometry": {
                    "points": points,
                    "links": links,
                },
            },
            "dataSummary": {
                "rowCount": int(response.get("totalRows") or 0),
                "pointCount": int(source_summary.get("pointCount") or 0),
                "linkCount": int(source_summary.get("linkCount") or 0),
                "timeRange": {
                    "min": source_summary.get("timeMin"),
                    "max": source_summary.get("timeMax"),
                },
                "hasODSemantics": bool(source_summary.get("hasODSemantics")),
            },
            "semanticSummary": {
                "whatToRender": f'{response.get("viewType", "None")} view',
                "whyTheseMarks": "Marks satisfy the selected workflow output after row, spatial, and temporal filtering.",
                "queryIntent": {
                    "atomicMode": query_context.get("atomicMode") or request.get("atomicMode"),
                    "requiredViewType": query_context.get("requiredViewType") or request.get("requiredViewType"),
                    "activeQueryType": query_context.get("activeQueryType") or "",
                },
            },
        }

    return {
        "meta": {
            "schemaVersion": EXPORT_SCHEMA_VERSION,
            "exportedAt": datetime.now(timezone.utc).isoformat(),
            "taskId": task_id or task.name.lower().replace(" ", "-"),
            "datasetProfile": request.get("datasetProfile"),
            "sourceDataPath": request.get("dataPath"),
        },
        "task": {
            "rawText": task.description,
            "parsedSpec": {
                "requiredViewType": request.get("requiredViewType"),
                "atomicMode": request.get("atomicMode"),
                "requireBackendBuild": request.get("requireBackendBuild"),
                "mapping": request.get("mapping"),
                "normalizeColumns": request.get("normalizeColumns"),
                "filter": {
                    "column": request.get("filterColumn"),
                    "value": request.get("filterValue"),
                },
                "timeColumn": request.get("timeColumn"),
                "encodedTimeColumn": request.get("encodedTimeColumn"),
                "spatialRegion": request.get("spatialRegion"),
                "timeWindow": request.get("timeWindow"),
                "recurrentHours": request.get("recurrentHours", []),
            },
        },
        "selectedWorkflow": {
            "operators": best.workflow,
            "operatorCount": len(best.workflow),
            "parametersUsed": {
                "mapping": request.get("mapping"),
                "filterColumn": request.get("filterColumn"),
                "filterValue": request.get("filterValue"),
                "timeWindow": request.get("timeWindow"),
                "spatialRegion": request.get("spatialRegion"),
                "atomicMode": request.get("atomicMode"),
                "recurrentHours": request.get("recurrentHours", []),
            },
            "scores": {
                "fitness": best.fitness,
                "execution": best.exec_score,
                "llm": best.llm_score,
                "selfEvaluation": self_eval,
                "llmReason": llm_eval.get("reason"),
            },
        },
        "visualization": build_visualization_contract(),
        "resultSummary": {
            "viewType": response.get("viewType"),
            "selectedRowIds": selected_row_ids,
            "selectedRowCount": len(selected_row_ids),
            "selectedRowSample": sample_items(selected_row_ids),
            "selectedPointCount": response.get("selectedPointCount"),
            "totalRows": response.get("totalRows"),
            "backendBuilt": response.get("backendBuilt"),
            "encodingState": response.get("encodingState", {}),
            "diagnostics": {
                "spatialSelectedCount": diagnostics.get("spatialSelectedCount"),
                "temporalSelectedCount": diagnostics.get("temporalSelectedCount"),
                "finalSelectedCount": diagnostics.get("finalSelectedCount"),
                "spatialTargetRole": diagnostics.get("spatialTargetRole"),
                "temporalTargetRole": diagnostics.get("temporalTargetRole"),
                "finalTargetRole": diagnostics.get("finalTargetRole"),
            },
        },
    }


def export_unity_json(task: TaskSpec, best: Candidate, output_path: Union[str, Path], *, task_id: Optional[str] = None) -> Path:
    export_path = Path(output_path)
    if not export_path.is_absolute():
        export_path = (ROOT / export_path).resolve()
    export_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_unity_export(task, best, task_id=task_id)
    export_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"[Export] Unity-ready JSON written to {export_path}")
    return export_path


def print_result(best: Candidate) -> None:
    print("\n=== Final Task ===")
    print(TASK.name)
    print(TASK.description)

    print("\n=== Final Best Workflow ===")
    for index, op_name in enumerate(best.workflow, start=1):
        print(f"{index:02d}. {op_name}")

    response = best.response
    self_eval = response["selfEvaluation"]
    llm_eval = response.get("llmEvaluation", {})

    print("\n=== Final Execution Result ===")
    print(f"ViewType: {response.get('viewType')}")
    print(f"SelectedRowIds: {summarize_selected_ids(response.get('selectedRowIds', []))}")
    print(f"SelectedPointCount: {response.get('selectedPointCount')}")
    print(f"BackendBuilt: {response.get('backendBuilt')}")

    print("\n=== Final EvoFlow Score ===")
    print(f"Fitness: {best.fitness}")
    print(f"ExecutionScore: {best.exec_score}")
    print(f"LLMScore: {best.llm_score}")
    print(f"SelfEvaluation.Score: {self_eval.get('score')}")
    print(f"Precision: {self_eval.get('precision')}")
    print(f"Recall: {self_eval.get('recall')}")
    print(f"F1: {self_eval.get('f1')}")
    print(f"LLMReason: {llm_eval.get('reason')}")

    diagnostics = response.get("diagnostics", {})
    print("\n=== Final Diagnostics ===")
    print(f"SpatialSelectedCount: {diagnostics.get('spatialSelectedCount')}")
    print(f"TemporalSelectedCount: {diagnostics.get('temporalSelectedCount')}")
    print(f"FinalSelectedCount: {diagnostics.get('finalSelectedCount')}")


def main() -> None:
    global TASK, DATASET_PROFILE, POPULATION_SIZE, GENERATIONS, ELITE_SIZE

    parser = argparse.ArgumentParser(description="Run EvoFlow operator search from a terminal task description.")
    parser.add_argument("--task", help="Task description to run. If omitted, the program prompts in the terminal.")
    parser.add_argument(
        "--data-path",
        default=str(ROOT / "demo_data" / "first_week_of_may_2011_10k_sample.csv"),
        help="CSV dataset to use for task parsing, workflow execution, and export.",
    )
    parser.add_argument(
        "--export-json",
        default=str(ROOT / "exports" / "unity_export.json"),
        help="Where to write the final Unity-ready JSON artifact.",
    )
    parser.add_argument("--task-id", help="Optional stable task id to include in the exported JSON.")
    parser.add_argument("--population", type=int, default=POPULATION_SIZE, help="Population size for EvoFlow search.")
    parser.add_argument("--generations", type=int, default=GENERATIONS, help="Number of generations to evolve.")
    parser.add_argument("--elite-size", type=int, default=ELITE_SIZE, help="How many elite workflows survive each generation.")
    args = parser.parse_args()

    description = args.task
    if not description:
        print("Enter a task description for EvoFlow:")
        description = input("> ").strip()
    if not description:
        description = DEFAULT_DESCRIPTION

    DATASET_PROFILE = resolve_dataset_profile(args.data_path)
    log(f"[Setup] Using dataset profile: {DATASET_PROFILE.name}")
    log(f"[Setup] Dataset path: {DATASET_PROFILE.data_path}")
    TASK = parse_task_with_llm(description, DATASET_PROFILE)

    POPULATION_SIZE = args.population
    GENERATIONS = args.generations
    ELITE_SIZE = min(args.elite_size, args.population)

    WORKFLOW_CACHE.clear()
    LLM_CACHE.clear()
    TASK_PARSE_CACHE.clear()
    ensure_runner_ready()
    ranked = evolve()
    best = ranked[0]
    export_unity_json(TASK, best, args.export_json, task_id=args.task_id)
    print_result(best)


if __name__ == "__main__":
    main()
