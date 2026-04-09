using System.Text.Json;
using OperatorPackage.Core;

namespace OperatorRunner;

public static class RequestNormalizer
{
    public static ExecutionPlan Parse(string json, JsonSerializerOptions options)
    {
        using var document = JsonDocument.Parse(json);
        var root = document.RootElement;

        if (root.TryGetProperty("selectedWorkflow", out _))
            return FromUnityExport(json, options);

        if (root.TryGetProperty("execution_graph", out _))
            return FromStandardWorkflow(json, options);

        if (root.TryGetProperty("operator_type", out _))
            return FromStandardOperator(json, options);

        return JsonSerializer.Deserialize<ExecutionPlan>(json, options) ?? new ExecutionPlan();
    }

    private static ExecutionPlan FromUnityExport(string json, JsonSerializerOptions options)
    {
        var export = JsonSerializer.Deserialize<UnityExportEnvelope>(json, options) ?? new UnityExportEnvelope();
        return new ExecutionPlan
        {
            WorkflowId = export.Meta.TaskId ?? "wf_unity_export",
            DataPath = export.Meta.SourceDataPath,
            Workflow = export.SelectedWorkflow.Operators,
            Mapping = export.Task.ParsedSpec.Mapping,
            SpatialRegion = export.Task.ParsedSpec.SpatialRegion,
            TimeWindow = export.Task.ParsedSpec.TimeWindow,
            NormalizeColumns = export.Task.ParsedSpec.NormalizeColumns,
            FilterColumn = export.Task.ParsedSpec.Filter?.Column,
            FilterValue = export.Task.ParsedSpec.Filter?.Value,
            TimeColumn = export.Task.ParsedSpec.TimeColumn,
            EncodedTimeColumn = export.Task.ParsedSpec.EncodedTimeColumn,
            AtomicMode = export.Task.ParsedSpec.AtomicMode,
            RequiredViewType = export.Task.ParsedSpec.RequiredViewType,
            RecurrentHours = export.Task.ParsedSpec.RecurrentHours,
            RequireBackendBuild = export.Task.ParsedSpec.RequireBackendBuild,
            TaskDescription = export.Task.RawText,
            TaskHints = new TaskHintsRequest
            {
                RequireBackendBuild = export.Task.ParsedSpec.RequireBackendBuild,
                RequireSpatialFilter = export.Task.ParsedSpec.SpatialRegion != null,
                RequireTemporalFilter = export.Task.ParsedSpec.TimeWindow != null,
                HotspotFocus = !string.IsNullOrWhiteSpace(export.Task.RawText) &&
                               export.Task.RawText.Contains("hotspot", StringComparison.OrdinalIgnoreCase)
            }
        };
    }

    private static ExecutionPlan FromStandardWorkflow(string json, JsonSerializerOptions options)
    {
        var workflow = JsonSerializer.Deserialize<StandardWorkflowEnvelope>(json, options) ?? new StandardWorkflowEnvelope();
        var plan = new ExecutionPlan
        {
            WorkflowId = workflow.WorkflowId,
            Workflow = TopologicalSort(workflow.ExecutionGraph),
        };

        ApplyCommonInputData(plan, workflow.InputData);
        ApplyCommonParameters(plan, workflow.Parameters);
        return plan;
    }

    private static ExecutionPlan FromStandardOperator(string json, JsonSerializerOptions options)
    {
        var request = JsonSerializer.Deserialize<StandardOperatorEnvelope>(json, options) ?? new StandardOperatorEnvelope();
        var plan = new ExecutionPlan
        {
            WorkflowId = request.WorkflowId,
            Workflow = new List<string> { MapOperatorType(request.OperatorType) }
        };

        ApplyCommonInputData(plan, request.InputData);
        ApplyCommonParameters(plan, request.Parameters);
        return plan;
    }

    private static void ApplyCommonInputData(ExecutionPlan plan, JsonElement inputData)
    {
        if (inputData.ValueKind != JsonValueKind.Object)
            return;

        if (TryGetString(inputData, "source_path", out var sourcePath))
            plan.DataPath = sourcePath!;
        else if (TryGetString(inputData, "data_path", out var dataPath))
            plan.DataPath = dataPath!;
        else if (TryGetString(inputData, "pointer", out var pointer))
            plan.DataPath = pointer!;
        else if (TryGetString(inputData, "tabular_pointer", out var tabularPointer))
            plan.DataPath = tabularPointer!;
    }

    private static void ApplyCommonParameters(ExecutionPlan plan, JsonElement parameters)
    {
        if (parameters.ValueKind != JsonValueKind.Object)
            return;

        if (TryGetString(parameters, "time_column", out var timeColumn))
            plan.TimeColumn = timeColumn;
        if (TryGetString(parameters, "output_column", out var outputColumn))
            plan.EncodedTimeColumn = outputColumn;

        if (parameters.TryGetProperty("mapping", out var mappingElement))
            plan.Mapping = JsonSerializer.Deserialize<MappingRequest>(mappingElement.GetRawText(), JsonDefaults.Options);
        else
            plan.Mapping = ParseMappingFromFlatParameters(parameters, plan.Mapping);

        if (parameters.TryGetProperty("spatial_region", out var spatialElement))
            plan.SpatialRegion = JsonSerializer.Deserialize<SpatialRegionRequest>(spatialElement.GetRawText(), JsonDefaults.Options);

        if (parameters.TryGetProperty("time_window", out var timeWindowElement))
            plan.TimeWindow = JsonSerializer.Deserialize<TimeWindowRequest>(timeWindowElement.GetRawText(), JsonDefaults.Options);

        if (TryGetString(parameters, "mode", out var atomicMode) &&
            Enum.TryParse<AtomicQueryMode>(atomicMode, true, out var parsedAtomicMode))
            plan.AtomicMode = parsedAtomicMode;

        if (parameters.TryGetProperty("normalize_columns", out var normalizeColumnsElement) &&
            normalizeColumnsElement.ValueKind == JsonValueKind.Array)
        {
            plan.NormalizeColumns = normalizeColumnsElement.EnumerateArray()
                .Where(x => x.ValueKind == JsonValueKind.String)
                .Select(x => x.GetString()!)
                .ToList();
        }

        if (parameters.TryGetProperty("filter", out var filterElement) && filterElement.ValueKind == JsonValueKind.Object)
        {
            if (TryGetString(filterElement, "column", out var filterColumn))
                plan.FilterColumn = filterColumn;
            if (TryGetString(filterElement, "value", out var filterValue))
                plan.FilterValue = filterValue;
        }

        if (parameters.TryGetProperty("recurrent_hours", out var recurrentHoursElement) &&
            recurrentHoursElement.ValueKind == JsonValueKind.Array)
        {
            plan.RecurrentHours = recurrentHoursElement.EnumerateArray()
                .Where(x => x.TryGetInt32(out _))
                .Select(x => x.GetInt32())
                .ToList();
        }
    }

    private static MappingRequest ParseMappingFromFlatParameters(JsonElement parameters, MappingRequest? existing)
    {
        var mapping = existing ?? new MappingRequest();
        if (TryGetString(parameters, "trip_id_column", out var tripId)) mapping.TripIdColumn = tripId;
        if (TryGetString(parameters, "origin_x_column", out var ox)) mapping.OriginXColumn = ox;
        if (TryGetString(parameters, "origin_y_column", out var oy)) mapping.OriginYColumn = oy;
        if (TryGetString(parameters, "origin_z_column", out var oz)) mapping.OriginZColumn = oz;
        if (TryGetString(parameters, "origin_time_column", out var ot)) mapping.OriginTimeColumn = ot;
        if (TryGetString(parameters, "destination_x_column", out var dx)) mapping.DestinationXColumn = dx;
        if (TryGetString(parameters, "destination_y_column", out var dy)) mapping.DestinationYColumn = dy;
        if (TryGetString(parameters, "destination_z_column", out var dz)) mapping.DestinationZColumn = dz;
        if (TryGetString(parameters, "destination_time_column", out var dt)) mapping.DestinationTimeColumn = dt;
        if (TryGetString(parameters, "x_column", out var x)) mapping.XColumn = x;
        if (TryGetString(parameters, "y_column", out var y)) mapping.YColumn = y;
        if (TryGetString(parameters, "z_column", out var z)) mapping.ZColumn = z;
        if (TryGetString(parameters, "time_column", out var t)) mapping.TimeColumn = t;
        if (TryGetString(parameters, "color_column", out var c)) mapping.ColorColumn = c;
        if (TryGetString(parameters, "size_column", out var s)) mapping.SizeColumn = s;
        if (parameters.TryGetProperty("stc_mode", out var stcMode) && stcMode.ValueKind is JsonValueKind.True or JsonValueKind.False)
            mapping.IsSTCMode = stcMode.GetBoolean();
        return mapping;
    }

    private static List<string> TopologicalSort(ExecutionGraph graph)
    {
        if (graph.Nodes.Count == 0)
            return new List<string>();

        var inDegree = graph.Nodes.ToDictionary(node => node.Id, _ => 0);
        foreach (var edge in graph.Edges)
        {
            if (inDegree.ContainsKey(edge.To))
                inDegree[edge.To]++;
        }

        var queue = new Queue<ExecutionNode>(graph.Nodes.Where(node => inDegree[node.Id] == 0));
        var ordered = new List<string>();

        while (queue.Count > 0)
        {
            var node = queue.Dequeue();
            ordered.Add(MapOperatorType(node.Type));

            foreach (var edge in graph.Edges.Where(edge => edge.From == node.Id))
            {
                inDegree[edge.To]--;
                if (inDegree[edge.To] == 0)
                {
                    var next = graph.Nodes.First(candidate => candidate.Id == edge.To);
                    queue.Enqueue(next);
                }
            }
        }

        if (ordered.Count != graph.Nodes.Count)
            throw new InvalidOperationException("The execution graph contains a cycle or unresolved node references.");

        return ordered;
    }

    public static string MapOperatorType(string operatorType) => operatorType switch
    {
        "Read_Data_Op" => "ReadDataOperator",
        "Filter_Rows_Op" => "FilterRowsOperator",
        "Normalize_Attributes_Op" => "NormalizeAttributesOperator",
        "Encode_Time_Op" => "EncodeTimeOperator",
        "Map_To_Visual_Space_Op" => "MapToVisualSpaceOperator",
        "Build_Point_View_Op" => "BuildPointViewOperator",
        "Build_STC_View_Bundle_Op" => "BuildSTCViewOperator",
        "Build_2D_Projection_View_Op" => "Build2DProjectionViewOperator",
        "Build_Link_View_Op" => "BuildLinkViewOperator",
        "Create_Atomic_Query_Op" => "CreateAtomicQueryOperator",
        "Create_Directional_Query_Op" => "CreateDirectionalQueryOperator",
        "Merge_Queries_Op" => "MergeQueriesOperator",
        "Recurrent_Query_Compose_Op" => "RecurrentQueryComposeOperator",
        "Apply_Spatial_Filter_Op" => "ApplySpatialFilterOperator",
        "Apply_Temporal_Filter_Op" => "ApplyTemporalFilterOperator",
        "Combine_Filters_Op" => "CombineFiltersOperator",
        "Update_View_Encoding_Op" => "UpdateViewEncodingOperator",
        "Adapted_IATK_View_Builder_Op" => "AdaptedIATKViewBuilderOperator",
        _ => operatorType
    };

    private static bool TryGetString(JsonElement element, string propertyName, out string? value)
    {
        if (element.ValueKind == JsonValueKind.Object &&
            element.TryGetProperty(propertyName, out var property) &&
            property.ValueKind == JsonValueKind.String)
        {
            value = property.GetString();
            return true;
        }

        value = null;
        return false;
    }
}

public static class JsonDefaults
{
    public static JsonSerializerOptions Options => new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        PropertyNameCaseInsensitive = true,
        WriteIndented = true,
        Converters = { new JsonStringEnumConverter() }
    };
}
