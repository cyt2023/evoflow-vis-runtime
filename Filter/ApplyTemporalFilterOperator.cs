using OperatorPackage.Core;

namespace OperatorPackage.Filter
{
    public class ApplyTemporalFilterOperator : IOperator<VisualPointData, FilterMask>
    {
        public QueryDefinition Query { get; set; }

        public FilterMask Execute(VisualPointData input)
        {
            var mask = new FilterMask
            {
                TargetRole = Query == null || Query.AtomicMode == AtomicQueryMode.Either
                    ? null
                    : (Query.AtomicMode == AtomicQueryMode.Origin ? PointRole.Origin : PointRole.Destination)
            };
            if (input == null || input.Points == null) return mask;

            foreach (var point in input.Points)
            {
                bool keep;
                if (Query?.TimeWindow != null)
                {
                    keep = Query.TimeWindow.Contains(point.Time);
                }
                else if (Query?.Parameters != null && Query.Parameters.TryGetValue("TimeWindow", out var tw) && tw is System.ValueTuple<float, float> window)
                {
                    keep = point.Time >= window.Item1 && point.Time <= window.Item2;
                }
                else if (Query?.Predicate != null)
                {
                    keep = Query.Predicate(point);
                }
                else
                {
                    keep = point.Time >= 0f;
                }

                mask.Mask.Add(keep);
            }

            return mask;
        }
    }
}
