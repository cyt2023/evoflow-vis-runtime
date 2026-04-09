using System.Collections.Generic;
using System.Linq;

namespace OperatorPackage.Core
{
    public enum PointRole
    {
        Generic,
        Origin,
        Destination
    }

    public class VisualPoint
    {
        public int OriginalPointIndex { get; set; } = -1;
        public int SourceRowIndex { get; set; }
        public string RowId { get; set; }
        public PointRole Role { get; set; } = PointRole.Generic;
        public float X { get; set; }
        public float Y { get; set; }
        public float Z { get; set; }
        public float Time { get; set; }
        public float ColorValue { get; set; }
        public float SizeValue { get; set; }
        public bool IsSelected { get; set; }
    }

    public class ODLink
    {
        public int OriginIndex { get; set; }
        public int DestinationIndex { get; set; }
        public float Weight { get; set; } = 1f;
    }

    public class VisualPointData
    {
        public List<VisualPoint> Points { get; set; } = new List<VisualPoint>();
        public List<ODLink> Links { get; set; } = new List<ODLink>();
        public float TimeMin { get; set; }
        public float TimeMax { get; set; }
        public bool HasODSemantics { get; set; }

        public int Count => Points.Count;
        public IEnumerable<VisualPoint> OriginPoints => Points.Where(p => p.Role == PointRole.Origin);
        public IEnumerable<VisualPoint> DestinationPoints => Points.Where(p => p.Role == PointRole.Destination);

        public VisualPointData CreateSubset(PointRole role)
        {
            return new VisualPointData
            {
                Points = Points.Where(p => p.Role == role)
                    .Select(p => new VisualPoint
                    {
                        OriginalPointIndex = p.OriginalPointIndex,
                        SourceRowIndex = p.SourceRowIndex,
                        RowId = p.RowId,
                        Role = p.Role,
                        X = p.X,
                        Y = p.Y,
                        Z = p.Z,
                        Time = p.Time,
                        ColorValue = p.ColorValue,
                        SizeValue = p.SizeValue,
                        IsSelected = p.IsSelected
                    })
                    .ToList(),
                Links = role == PointRole.Generic ? new List<ODLink>(Links) : new List<ODLink>(),
                TimeMin = TimeMin,
                TimeMax = TimeMax,
                HasODSemantics = HasODSemantics
            };
        }

        public void UpdateTimeRange()
        {
            if (Points.Count == 0)
            {
                TimeMin = 0;
                TimeMax = 0;
                return;
            }

            TimeMin = float.MaxValue;
            TimeMax = float.MinValue;
            foreach (var p in Points)
            {
                if (p.Time < TimeMin) TimeMin = p.Time;
                if (p.Time > TimeMax) TimeMax = p.Time;
            }
        }
    }
}
