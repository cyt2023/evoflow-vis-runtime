using OperatorPackage.Core;

namespace OperatorPackage.Filter
{
    public class ApplySpatialFilterOperator : IOperator<VisualPointData, FilterMask>
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

            if (input == null || input.Points == null)
                return mask;

            for (int i = 0; i < input.Points.Count; i++)
            {
                bool keep = true;

                if (Query != null)
                {
                    if (Query.Predicate != null)
                    {
                        keep = Query.Predicate(input.Points[i]);
                    }
                    else if (Query.SpatialRegion != null)
                    {
                        keep = Query.SpatialRegion.Contains(input.Points[i]);
                    }
                    else if (Query.Parameters.ContainsKey("Region"))
                    {
                        var p = input.Points[i];

                        if (Query.Parameters["Region"] is System.ValueTuple<float, float, float, float, float, float> region3D)
                        {
                            var (x0, y0, t0, x1, y1, t1) = region3D;
                            keep = p.X >= x0 && p.X <= x1 &&
                                   p.Y >= y0 && p.Y <= y1 &&
                                   p.Time >= t0 && p.Time <= t1;
                        }
                        else if (Query.Parameters["Region"] is System.ValueTuple<float, float, float, float> region2D)
                        {
                            var (minX, maxX, minY, maxY) = region2D;
                            keep = p.X >= minX && p.X <= maxX &&
                                   p.Y >= minY && p.Y <= maxY;
                        }
                        else
                        {
                            keep = true;
                        }
                    }
                    else
                    {
                        keep = true;
                    }
                }

                mask.Mask.Add(keep);
            }

            return mask;
        }
    }
}
