using OperatorPackage.Core;

namespace OperatorPackage.Query
{
    public class CreateAtomicQueryOperator : IOperator<object, QueryDefinition>
    {
        public string Shape { get; set; } = "Box";
        public AtomicQueryMode Mode { get; set; } = AtomicQueryMode.Either;

        public QueryDefinition Execute(object input)
        {
            var query = new QueryDefinition
            {
                Type = QueryType.Atomic,
                AtomicMode = Mode
            };

            query.Parameters["Shape"] = Shape;
            query.Parameters["Region"] = input;

            if (input is ValueTuple<float, float, float, float, float, float> region)
            {
                var (x0, y0, z0, x1, y1, z1) = region;
                query.SpatialRegion = new SpatialRegion3D
                {
                    MinX = x0,
                    MaxX = x1,
                    MinY = y0,
                    MaxY = y1,
                    MinTime = z0,
                    MaxTime = z1
                };
                query.TimeWindow = new TimeWindow { Start = z0, End = z1 };
                query.Predicate = p => query.SpatialRegion.Contains(p);
            }

            return query;
        }
    }
}
