using OperatorPackage.Backend;
using OperatorPackage.Core;
using OperatorPackage.Data;
using OperatorPackage.Filter;
using OperatorPackage.Query;
using OperatorPackage.View;
using OperatorRunner;

var requestPath = GetArgument(args, "--request");
var saveOutputPath = GetArgument(args, "--save-output");

if (string.IsNullOrWhiteSpace(requestPath))
{
    Console.Error.WriteLine("Usage: OperatorRunner --request <path-to-request.json> [--save-output <path-to-output.json>]");
    return 1;
}

try
{
    var requestJson = await File.ReadAllTextAsync(requestPath);
    var plan = RequestNormalizer.Parse(requestJson, JsonDefaults.Options);
    var response = ExecuteWorkflow(plan);
    var output = System.Text.Json.JsonSerializer.Serialize(response, JsonDefaults.Options);

    if (!string.IsNullOrWhiteSpace(saveOutputPath))
        await File.WriteAllTextAsync(saveOutputPath, output);

    Console.WriteLine(output);
    return 0;
}
catch (Exception ex)
{
    var error = new RunnerResponse
    {
        Success = false,
        Errors = new List<string> { ex.Message }
    };
    var output = System.Text.Json.JsonSerializer.Serialize(error, JsonDefaults.Options);

    if (!string.IsNullOrWhiteSpace(saveOutputPath))
        await File.WriteAllTextAsync(saveOutputPath, output);

    Console.WriteLine(output);
    return 2;
}

static string? GetArgument(string[] args, string key)
{
    for (var i = 0; i < args.Length - 1; i++)
    {
        if (string.Equals(args[i], key, StringComparison.OrdinalIgnoreCase))
            return args[i + 1];
    }

    return null;
}

static RunnerResponse ExecuteWorkflow(ExecutionPlan plan)
{
    if (string.IsNullOrWhiteSpace(plan.DataPath))
        throw new InvalidOperationException("Execution plan is missing a data path.");

    var context = new ExecutionContext();
    context.Store.Set(plan.DataPath, plan.DataPath);

    foreach (var opName in plan.Workflow)
    {
        switch (opName)
        {
            case "ReadDataOperator":
                context.Table = new ReadDataOperator().Execute(plan.DataPath);
                context.Store.Set("tabular://current", context.Table);
                break;

            case "NormalizeAttributesOperator":
                context.Table = new NormalizeAttributesOperator
                {
                    TargetColumns = plan.NormalizeColumns ?? new List<string>()
                }.Execute(context.Table);
                context.Store.Set("tabular://current", context.Table);
                break;

            case "FilterRowsOperator":
                context.Table = new FilterRowsOperator
                {
                    FilterColumn = plan.FilterColumn ?? string.Empty,
                    FilterValue = plan.FilterValue ?? string.Empty
                }.Execute(context.Table);
                context.Store.Set("tabular://current", context.Table);
                break;

            case "EncodeTimeOperator":
                context.Table = new EncodeTimeOperator
                {
                    TimeColumn = plan.TimeColumn ?? "pickup_datetime",
                    OutputColumn = plan.EncodedTimeColumn ?? "EncodedTime"
                }.Execute(context.Table);
                context.Store.Set("tabular://current", context.Table);
                break;

            case "MapToVisualSpaceOperator":
                context.VisualData = new MapToVisualSpaceOperator
                {
                    Mapping = plan.Mapping?.ToVisualMapping() ?? new VisualMapping()
                }.Execute(context.Table);
                context.Store.Set("visual://current", context.VisualData);
                break;

            case "BuildSTCViewOperator":
                context.View = new BuildSTCViewOperator().Execute(context.VisualData!);
                context.Store.Set("view://current", context.View);
                break;

            case "BuildPointViewOperator":
                context.View = new BuildPointViewOperator
                {
                    Role = plan.AtomicMode switch
                    {
                        AtomicQueryMode.Origin => PointRole.Origin,
                        AtomicQueryMode.Destination => PointRole.Destination,
                        _ => PointRole.Generic
                    }
                }.Execute(context.VisualData!);
                context.Store.Set("view://current", context.View);
                break;

            case "Build2DProjectionViewOperator":
                context.View = new Build2DProjectionViewOperator().Execute(context.VisualData!);
                context.Store.Set("view://current", context.View);
                break;

            case "BuildLinkViewOperator":
                context.View = new BuildLinkViewOperator().Execute(context.VisualData!);
                context.Store.Set("view://current", context.View);
                break;

            case "CreateAtomicQueryOperator":
                context.SpatialQuery = new CreateAtomicQueryOperator
                {
                    Mode = plan.AtomicMode
                }.Execute((
                    plan.SpatialRegion?.MinX ?? 0f,
                    plan.SpatialRegion?.MinY ?? 0f,
                    plan.SpatialRegion?.MinTime ?? 0f,
                    plan.SpatialRegion?.MaxX ?? 0f,
                    plan.SpatialRegion?.MaxY ?? 0f,
                    plan.SpatialRegion?.MaxTime ?? 0f
                ));
                context.CurrentQuery = context.SpatialQuery;
                context.Store.Set("query://current", context.CurrentQuery);
                break;

            case "CreateDirectionalQueryOperator":
                context.CurrentQuery = new CreateDirectionalQueryOperator
                {
                    DestinationQuery = context.SpatialQuery
                }.Execute(context.CurrentQuery ?? context.SpatialQuery ?? new QueryDefinition());
                context.Store.Set("query://current", context.CurrentQuery);
                break;

            case "RecurrentQueryComposeOperator":
                context.CurrentQuery = new RecurrentQueryComposeOperator
                {
                    Hours = plan.RecurrentHours ?? new List<int>()
                }.Execute(new List<QueryDefinition> { context.CurrentQuery ?? context.SpatialQuery ?? new QueryDefinition() });
                context.Store.Set("query://current", context.CurrentQuery);
                break;

            case "MergeQueriesOperator":
                context.CurrentQuery = new MergeQueriesOperator().Execute(
                    new List<QueryDefinition> { context.CurrentQuery ?? context.SpatialQuery ?? new QueryDefinition() });
                context.Store.Set("query://current", context.CurrentQuery);
                break;

            case "ApplySpatialFilterOperator":
                context.SpatialMask = new ApplySpatialFilterOperator
                {
                    Query = context.SpatialQuery ?? context.CurrentQuery
                }.Execute(context.VisualData!);
                context.Store.Set("mask://spatial", context.SpatialMask);
                break;

            case "ApplyTemporalFilterOperator":
                var temporalQuery = new QueryDefinition
                {
                    AtomicMode = plan.AtomicMode,
                    TimeWindow = new TimeWindow
                    {
                        Start = plan.TimeWindow?.Start ?? 0f,
                        End = plan.TimeWindow?.End ?? float.MaxValue
                    }
                };
                context.TemporalMask = new ApplyTemporalFilterOperator
                {
                    Query = temporalQuery
                }.Execute(context.VisualData!);
                context.Store.Set("mask://temporal", context.TemporalMask);
                break;

            case "CombineFiltersOperator":
                var availableMasks = new List<FilterMask>();
                if (context.SpatialMask != null) availableMasks.Add(context.SpatialMask);
                if (context.TemporalMask != null) availableMasks.Add(context.TemporalMask);
                context.FinalMask = new CombineFiltersOperator
                {
                    Mode = "AND"
                }.Execute(availableMasks);
                context.Store.Set("mask://final", context.FinalMask);
                break;

            case "UpdateViewEncodingOperator":
                context.FinalMask ??= context.SpatialMask ?? context.TemporalMask;
                context.View = new UpdateViewEncodingOperator
                {
                    TargetView = context.View
                }.Execute(context.FinalMask!);
                context.Store.Set("view://current", context.View!);
                break;

            case "AdaptedIATKViewBuilderOperator":
                context.View = ApplyBackendBuild(context.View);
                context.Store.Set("view://current", context.View!);
                break;

            default:
                throw new InvalidOperationException($"Unsupported operator '{opName}'.");
        }
    }

    context.FinalMask ??= context.SpatialMask ?? context.TemporalMask;
    var selectedRowIds = GetSelectedRowIds(context.View);

    return new RunnerResponse
    {
        Success = true,
        WorkflowId = plan.WorkflowId,
        Workflow = plan.Workflow,
        ViewType = context.View?.Type.ToString() ?? "None",
        TotalRows = context.Table.RowCount,
        SelectedPointCount = context.View?.PointData?.Points?.Count(p => p.IsSelected) ?? 0,
        SelectedRowIds = selectedRowIds,
        BackendBuilt = context.View?.BackendViewObject != null,
        EncodingState = context.View?.EncodingState?.ToDictionary(
            kvp => kvp.Key,
            kvp => kvp.Value?.ToString() ?? string.Empty) ?? new Dictionary<string, string>(),
        SelfEvaluation = Evaluate(plan, selectedRowIds, context),
        VisualizationPayload = BuildVisualizationPayload(plan, context, selectedRowIds),
        Diagnostics = BuildDiagnostics(context)
    };
}

static ViewRepresentation? ApplyBackendBuild(ViewRepresentation? view)
{
    if (view == null)
        return null;

    var builder = new AdaptedIATKViewBuilderOperator();
    var backend = new AdaptedIATKViewOperator();

    view = builder.Build(view);
    view = backend.CreateView(view);

    foreach (var coordinatedView in view.CoordinatedViews)
    {
        builder.Build(coordinatedView);
        backend.CreateView(coordinatedView);
    }

    return view;
}

static List<string> GetSelectedRowIds(ViewRepresentation? view)
{
    return view?.PointData?.Points?
        .Where(p => p.IsSelected)
        .Select(p => p.RowId)
        .Distinct()
        .ToList() ?? new List<string>();
}

static SelfEvaluation Evaluate(ExecutionPlan plan, List<string> selectedRowIds, ExecutionContext context)
{
    var expectedSet = new HashSet<string>(plan.ExpectedRowIds ?? new List<string>());
    var selectedSet = new HashSet<string>(selectedRowIds);
    var notes = new List<string>();
    var structuralBonus = 0f;
    var f1 = 0f;
    var precision = 0f;
    var recall = 0f;

    if (expectedSet.Count > 0)
    {
        var overlap = expectedSet.Intersect(selectedSet).Count();
        precision = selectedSet.Count == 0 ? 0f : (float)overlap / selectedSet.Count;
        recall = (float)overlap / expectedSet.Count;
        f1 = (precision + recall) == 0f ? 0f : (2f * precision * recall) / (precision + recall);
    }
    else
    {
        var selectedRatio = context.Table.RowCount == 0 ? 0f : (float)selectedSet.Count / context.Table.RowCount;
        var hotspotBonus = plan.TaskHints?.HotspotFocus == true && selectedRatio <= 0.1f ? 0.25f : 0.12f;
        var nonEmptyBonus = selectedSet.Count > 0 ? 0.1f : 0f;
        var temporalBonus = context.TemporalMask?.SelectedCount > 0 ? 0.08f : 0f;
        var spatialBonus = context.SpatialMask?.SelectedCount > 0 ? 0.08f : 0f;
        f1 = Math.Clamp(hotspotBonus + nonEmptyBonus + temporalBonus + spatialBonus, 0f, 0.35f);
        precision = f1;
        recall = f1;
        notes.Add("No expected row ids were provided; heuristic selection-quality evaluation was used.");
    }

    if (plan.RequiredViewType == null || string.Equals(context.View?.Type.ToString(), plan.RequiredViewType, StringComparison.OrdinalIgnoreCase))
    {
        structuralBonus += 0.15f;
        notes.Add("View type matches task.");
    }

    if (context.SpatialMask != null)
    {
        structuralBonus += 0.10f;
        notes.Add("Spatial filtering was included.");
    }

    if (context.TemporalMask != null)
    {
        structuralBonus += 0.10f;
        notes.Add("Temporal filtering was included.");
    }

    if (context.View?.EncodingState?.ContainsKey("MaskApplied") == true)
    {
        structuralBonus += 0.10f;
        notes.Add("View encoding was updated.");
    }

    if (plan.RequireBackendBuild)
    {
        if (context.View?.BackendViewObject != null)
        {
            structuralBonus += 0.10f;
            notes.Add("Backend build completed.");
        }
        else
        {
            notes.Add("Backend build is missing.");
        }
    }

    var costPenalty = Math.Max(0, plan.Workflow.Count - 8) * 0.02f;
    return new SelfEvaluation
    {
        Precision = precision,
        Recall = recall,
        F1 = f1,
        Score = Math.Clamp((0.55f * f1) + structuralBonus - costPenalty, 0f, 1f),
        Notes = notes
    };
}

static Dictionary<string, object> BuildVisualizationPayload(ExecutionPlan plan, ExecutionContext context, List<string> selectedRowIds)
{
    var activeData = context.View?.PointData ?? context.VisualData ?? new VisualPointData();
    return new Dictionary<string, object>
    {
        ["primaryView"] = SerializeView(context.View),
        ["coordinatedViews"] = context.View?.CoordinatedViews?.Select(SerializeView).ToList() ?? new List<Dictionary<string, object>>(),
        ["points"] = SerializePoints(activeData.Points),
        ["links"] = SerializeLinks(activeData),
        ["encodingState"] = context.View?.EncodingState?.ToDictionary(kvp => kvp.Key, kvp => kvp.Value?.ToString() ?? string.Empty)
            ?? new Dictionary<string, string>(),
        ["selectionState"] = new Dictionary<string, object>
        {
            ["selectedRowIds"] = selectedRowIds,
            ["selectedPointCount"] = activeData.Points.Count(p => p.IsSelected),
            ["spatialSelectedCount"] = context.SpatialMask?.SelectedCount ?? 0,
            ["temporalSelectedCount"] = context.TemporalMask?.SelectedCount ?? 0,
            ["finalSelectedCount"] = context.FinalMask?.SelectedCount ?? 0
        },
        ["queryContext"] = new Dictionary<string, object?>
        {
            ["atomicMode"] = plan.AtomicMode.ToString(),
            ["requiredViewType"] = plan.RequiredViewType,
            ["spatialRegion"] = plan.SpatialRegion,
            ["timeWindow"] = plan.TimeWindow,
            ["activeQueryType"] = context.CurrentQuery?.Type.ToString() ?? context.SpatialQuery?.Type.ToString()
        },
        ["sourceDataSummary"] = new Dictionary<string, object>
        {
            ["pointCount"] = activeData.Points.Count,
            ["linkCount"] = activeData.Links.Count,
            ["timeMin"] = activeData.TimeMin,
            ["timeMax"] = activeData.TimeMax,
            ["hasODSemantics"] = activeData.HasODSemantics
        }
    };
}

static Dictionary<string, object> SerializeView(ViewRepresentation? view) => new()
{
    ["viewName"] = view?.ViewName ?? "None",
    ["viewType"] = view?.Type.ToString() ?? "None",
    ["role"] = view?.Role?.ToString() ?? "All",
    ["projectionKind"] = view?.ProjectionKind ?? string.Empty,
    ["pointCount"] = view?.PointData?.Points?.Count ?? 0,
    ["linkCount"] = view?.PointData?.Links?.Count ?? 0,
    ["backendBuilt"] = view?.BackendViewObject != null
};

static List<Dictionary<string, object>> SerializePoints(List<VisualPoint> points)
{
    return points.Select((point, index) => new Dictionary<string, object>
    {
        ["index"] = index,
        ["originalPointIndex"] = point.OriginalPointIndex,
        ["sourceRowIndex"] = point.SourceRowIndex,
        ["rowId"] = point.RowId,
        ["role"] = point.Role.ToString(),
        ["x"] = point.X,
        ["y"] = point.Y,
        ["z"] = point.Z,
        ["time"] = point.Time,
        ["colorValue"] = point.ColorValue,
        ["sizeValue"] = point.SizeValue,
        ["isSelected"] = point.IsSelected
    }).ToList();
}

static List<Dictionary<string, object>> SerializeLinks(VisualPointData data)
{
    return data.Links.Select((link, index) => new Dictionary<string, object>
    {
        ["index"] = index,
        ["originIndex"] = link.OriginIndex,
        ["destinationIndex"] = link.DestinationIndex,
        ["originRowId"] = link.OriginIndex >= 0 && link.OriginIndex < data.Points.Count ? data.Points[link.OriginIndex].RowId : string.Empty,
        ["destinationRowId"] = link.DestinationIndex >= 0 && link.DestinationIndex < data.Points.Count ? data.Points[link.DestinationIndex].RowId : string.Empty,
        ["weight"] = link.Weight
    }).ToList();
}

static Dictionary<string, object> BuildDiagnostics(ExecutionContext context)
{
    return new Dictionary<string, object>
    {
        ["tableRows"] = context.Table.RowCount,
        ["pointCount"] = context.VisualData?.Points?.Count ?? 0,
        ["linkCount"] = context.VisualData?.Links?.Count ?? 0,
        ["spatialSelectedCount"] = context.SpatialMask?.SelectedCount ?? 0,
        ["temporalSelectedCount"] = context.TemporalMask?.SelectedCount ?? 0,
        ["finalSelectedCount"] = context.FinalMask?.SelectedCount ?? 0,
        ["backendBuilt"] = context.View?.BackendViewObject != null
    };
}
