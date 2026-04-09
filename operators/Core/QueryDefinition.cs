using System;
using System.Collections.Generic;

namespace OperatorPackage.Core
{
    public enum QueryType
    {
        Atomic,
        Directional,
        Merged,
        Recurrent
    }

    public enum AtomicQueryMode
    {
        Origin,
        Destination,
        Either
    }

    public class SpatialRegion3D
    {
        public float MinX { get; set; }
        public float MaxX { get; set; }
        public float MinY { get; set; }
        public float MaxY { get; set; }
        public float MinTime { get; set; }
        public float MaxTime { get; set; }

        public bool Contains(VisualPoint point)
        {
            if (point == null)
                return false;

            return point.X >= MinX && point.X <= MaxX &&
                   point.Y >= MinY && point.Y <= MaxY &&
                   point.Time >= MinTime && point.Time <= MaxTime;
        }
    }

    public class TimeWindow
    {
        public float Start { get; set; }
        public float End { get; set; }

        public bool Contains(float time) => time >= Start && time <= End;
    }

    public class QueryDefinition
    {
        public string QueryId { get; set; } = Guid.NewGuid().ToString();

        public QueryType Type { get; set; }
        public AtomicQueryMode AtomicMode { get; set; } = AtomicQueryMode.Either;

        public Dictionary<string, object> Parameters { get; set; } = new Dictionary<string, object>();

        public List<QueryDefinition> SubQueries { get; set; } = new List<QueryDefinition>();

        public Func<VisualPoint, bool> Predicate { get; set; }

        public SpatialRegion3D SpatialRegion { get; set; }
        public TimeWindow TimeWindow { get; set; }
        public QueryDefinition OriginQuery { get; set; }
        public QueryDefinition DestinationQuery { get; set; }
        public List<int> Years { get; set; } = new List<int>();
        public List<int> Months { get; set; } = new List<int>();
        public List<DayOfWeek> DaysOfWeek { get; set; } = new List<DayOfWeek>();
        public List<int> Hours { get; set; } = new List<int>();

        public string OriginColumn { get; set; }
        public string DestinationColumn { get; set; }
        public string TimeColumn { get; set; }

        public string ToDebugString()
        {
            return $"Query(Id={QueryId}, Type={Type}, Params={Parameters.Count}, SubQueries={SubQueries.Count})";
        }
    }
}
