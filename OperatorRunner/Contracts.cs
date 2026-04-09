using System.Text.Json;
using System.Text.Json.Serialization;
using OperatorPackage.Core;

namespace OperatorRunner;

public sealed class ExecutionPlan
{
    public string WorkflowId { get; set; } = "wf_default";
    public string DataPath { get; set; } = string.Empty;
    public List<string> Workflow { get; set; } = new();
    public MappingRequest? Mapping { get; set; }
    public SpatialRegionRequest? SpatialRegion { get; set; }
    public TimeWindowRequest? TimeWindow { get; set; }
    public List<string> NormalizeColumns { get; set; } = new();
    public string? FilterColumn { get; set; }
    public string? FilterValue { get; set; }
    public string? TimeColumn { get; set; }
    public string? EncodedTimeColumn { get; set; }
    public AtomicQueryMode AtomicMode { get; set; } = AtomicQueryMode.Origin;
    public string? RequiredViewType { get; set; }
    public List<string> ExpectedRowIds { get; set; } = new();
    public List<int> RecurrentHours { get; set; } = new();
    public bool RequireBackendBuild { get; set; }
    public TaskHintsRequest? TaskHints { get; set; }
    public string? TaskDescription { get; set; }
}

public sealed class PointerStore
{
    private readonly Dictionary<string, object> objects = new(StringComparer.OrdinalIgnoreCase);

    public void Set(string pointer, object value)
    {
        if (string.IsNullOrWhiteSpace(pointer))
            throw new ArgumentException("Pointer cannot be empty.", nameof(pointer));
        objects[pointer] = value;
    }

    public bool TryGet<T>(string pointer, out T? value)
    {
        if (objects.TryGetValue(pointer, out var raw) && raw is T typed)
        {
            value = typed;
            return true;
        }

        value = default;
        return false;
    }

    public T GetRequired<T>(string pointer)
    {
        if (TryGet<T>(pointer, out var value) && value != null)
            return value;

        throw new KeyNotFoundException($"Pointer '{pointer}' is not available as {typeof(T).Name}.");
    }
}

public sealed class ExecutionContext
{
    public PointerStore Store { get; } = new();
    public TabularData Table { get; set; } = new();
    public VisualPointData? VisualData { get; set; }
    public ViewRepresentation? View { get; set; }
    public QueryDefinition? SpatialQuery { get; set; }
    public QueryDefinition? CurrentQuery { get; set; }
    public FilterMask? SpatialMask { get; set; }
    public FilterMask? TemporalMask { get; set; }
    public FilterMask? FinalMask { get; set; }
}

public sealed class MappingRequest
{
    public string? TripIdColumn { get; set; }
    public string? OriginXColumn { get; set; }
    public string? OriginYColumn { get; set; }
    public string? OriginZColumn { get; set; }
    public string? OriginTimeColumn { get; set; }
    public string? DestinationXColumn { get; set; }
    public string? DestinationYColumn { get; set; }
    public string? DestinationZColumn { get; set; }
    public string? DestinationTimeColumn { get; set; }
    public string? XColumn { get; set; }
    public string? YColumn { get; set; }
    public string? ZColumn { get; set; }
    public string? TimeColumn { get; set; }
    public string? ColorColumn { get; set; }
    public string? SizeColumn { get; set; }
    public bool IsSTCMode { get; set; }

    public VisualMapping ToVisualMapping() => new()
    {
        TripIdColumn = TripIdColumn,
        OriginXColumn = OriginXColumn,
        OriginYColumn = OriginYColumn,
        OriginZColumn = OriginZColumn,
        OriginTimeColumn = OriginTimeColumn,
        DestinationXColumn = DestinationXColumn,
        DestinationYColumn = DestinationYColumn,
        DestinationZColumn = DestinationZColumn,
        DestinationTimeColumn = DestinationTimeColumn,
        XColumn = XColumn,
        YColumn = YColumn,
        ZColumn = ZColumn,
        TimeColumn = TimeColumn,
        ColorColumn = ColorColumn,
        SizeColumn = SizeColumn,
        IsSTCMode = IsSTCMode
    };
}

public sealed class SpatialRegionRequest
{
    public float MinX { get; set; }
    public float MaxX { get; set; }
    public float MinY { get; set; }
    public float MaxY { get; set; }
    public float MinTime { get; set; }
    public float MaxTime { get; set; }
}

public sealed class TimeWindowRequest
{
    public float Start { get; set; }
    public float End { get; set; }
}

public sealed class TaskHintsRequest
{
    public bool RequireBackendBuild { get; set; }
    public bool RequireTemporalFilter { get; set; }
    public bool RequireSpatialFilter { get; set; }
    public bool HotspotFocus { get; set; }
}

public sealed class RunnerResponse
{
    public bool Success { get; set; }
    public string WorkflowId { get; set; } = string.Empty;
    public List<string> Workflow { get; set; } = new();
    public string ViewType { get; set; } = "None";
    public int TotalRows { get; set; }
    public int SelectedPointCount { get; set; }
    public List<string> SelectedRowIds { get; set; } = new();
    public bool BackendBuilt { get; set; }
    public Dictionary<string, string> EncodingState { get; set; } = new();
    public SelfEvaluation SelfEvaluation { get; set; } = new();
    public Dictionary<string, object> VisualizationPayload { get; set; } = new();
    public Dictionary<string, object> Diagnostics { get; set; } = new();
    public List<string> Errors { get; set; } = new();
}

public sealed class SelfEvaluation
{
    public float Score { get; set; }
    public float Precision { get; set; }
    public float Recall { get; set; }
    public float F1 { get; set; }
    public List<string> Notes { get; set; } = new();
}

public sealed class StandardOperatorEnvelope
{
    [JsonPropertyName("workflow_id")]
    public string WorkflowId { get; set; } = "wf_default";

    [JsonPropertyName("operator_id")]
    public string OperatorId { get; set; } = "op_001";

    [JsonPropertyName("operator_type")]
    public string OperatorType { get; set; } = string.Empty;

    [JsonPropertyName("operator_level")]
    public string OperatorLevel { get; set; } = "Level_1";

    [JsonPropertyName("timestamp")]
    public string? Timestamp { get; set; }

    [JsonPropertyName("input_data")]
    public JsonElement InputData { get; set; }

    [JsonPropertyName("parameters")]
    public JsonElement Parameters { get; set; }
}

public sealed class StandardWorkflowEnvelope
{
    [JsonPropertyName("workflow_id")]
    public string WorkflowId { get; set; } = "wf_default";

    [JsonPropertyName("workflow_type")]
    public string WorkflowType { get; set; } = "Workflow";

    [JsonPropertyName("execution_graph")]
    public ExecutionGraph ExecutionGraph { get; set; } = new();

    [JsonPropertyName("input_data")]
    public JsonElement InputData { get; set; }

    [JsonPropertyName("parameters")]
    public JsonElement Parameters { get; set; }
}

public sealed class ExecutionGraph
{
    [JsonPropertyName("nodes")]
    public List<ExecutionNode> Nodes { get; set; } = new();

    [JsonPropertyName("edges")]
    public List<ExecutionEdge> Edges { get; set; } = new();
}

public sealed class ExecutionNode
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    [JsonPropertyName("level")]
    public string Level { get; set; } = string.Empty;
}

public sealed class ExecutionEdge
{
    [JsonPropertyName("from")]
    public string From { get; set; } = string.Empty;

    [JsonPropertyName("to")]
    public string To { get; set; } = string.Empty;
}

public sealed class UnityExportEnvelope
{
    [JsonPropertyName("meta")]
    public ExportMeta Meta { get; set; } = new();

    [JsonPropertyName("task")]
    public ExportTask Task { get; set; } = new();

    [JsonPropertyName("selectedWorkflow")]
    public ExportSelectedWorkflow SelectedWorkflow { get; set; } = new();
}

public sealed class ExportMeta
{
    [JsonPropertyName("sourceDataPath")]
    public string SourceDataPath { get; set; } = string.Empty;

    [JsonPropertyName("taskId")]
    public string? TaskId { get; set; }
}

public sealed class ExportTask
{
    [JsonPropertyName("rawText")]
    public string? RawText { get; set; }

    [JsonPropertyName("parsedSpec")]
    public ExportParsedSpec ParsedSpec { get; set; } = new();
}

public sealed class ExportParsedSpec
{
    [JsonPropertyName("requiredViewType")]
    public string? RequiredViewType { get; set; }

    [JsonPropertyName("atomicMode")]
    public AtomicQueryMode AtomicMode { get; set; } = AtomicQueryMode.Origin;

    [JsonPropertyName("requireBackendBuild")]
    public bool RequireBackendBuild { get; set; }

    [JsonPropertyName("mapping")]
    public MappingRequest? Mapping { get; set; }

    [JsonPropertyName("normalizeColumns")]
    public List<string> NormalizeColumns { get; set; } = new();

    [JsonPropertyName("filter")]
    public ExportFilterSpec? Filter { get; set; }

    [JsonPropertyName("timeColumn")]
    public string? TimeColumn { get; set; }

    [JsonPropertyName("encodedTimeColumn")]
    public string? EncodedTimeColumn { get; set; }

    [JsonPropertyName("spatialRegion")]
    public SpatialRegionRequest? SpatialRegion { get; set; }

    [JsonPropertyName("timeWindow")]
    public TimeWindowRequest? TimeWindow { get; set; }

    [JsonPropertyName("recurrentHours")]
    public List<int> RecurrentHours { get; set; } = new();
}

public sealed class ExportFilterSpec
{
    [JsonPropertyName("column")]
    public string? Column { get; set; }

    [JsonPropertyName("value")]
    public string? Value { get; set; }
}

public sealed class ExportSelectedWorkflow
{
    [JsonPropertyName("operators")]
    public List<string> Operators { get; set; } = new();
}
