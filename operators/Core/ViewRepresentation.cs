using System;
using System.Collections.Generic;
using System.Linq;

namespace OperatorPackage.Core
{
    public enum ViewType
    {
        Point,
        STC,
        Projection2D,
        Link
    }

    public class ViewRepresentation
    {
        public string ViewName { get; set; }
        public ViewType Type { get; set; }
        public VisualPointData PointData { get; set; }
        public PointRole? Role { get; set; }
        public string ProjectionKind { get; set; }
        public object BackendViewObject { get; set; }
        public Dictionary<string, object> EncodingState { get; set; } = new Dictionary<string, object>();
        public List<ViewRepresentation> CoordinatedViews { get; set; } = new List<ViewRepresentation>();

        public void ApplyMask(FilterMask mask)
        {
            if (mask == null || PointData == null || PointData.Points == null) return;

            for (int i = 0; i < PointData.Points.Count; i++)
            {
                var point = PointData.Points[i];
                if (mask.TargetRole != null && point.Role != mask.TargetRole.Value)
                    continue;

                var maskIndex = i;
                if (mask.Count != PointData.Points.Count && point.OriginalPointIndex >= 0 && point.OriginalPointIndex < mask.Count)
                    maskIndex = point.OriginalPointIndex;

                if (maskIndex >= 0 && maskIndex < mask.Count)
                    point.IsSelected = mask.Mask[maskIndex];
            }

            EncodingState["MaskApplied"] = true;
            EncodingState["SelectedCount"] = PointData.Points.Count(p => p.IsSelected);
        }
    }
}
