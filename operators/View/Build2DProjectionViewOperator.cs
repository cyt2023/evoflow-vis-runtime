using OperatorPackage.Core;

namespace OperatorPackage.View
{
    public class Build2DProjectionViewOperator : IOperator<VisualPointData, ViewRepresentation>
    {
        public string Plane { get; set; } = "XY";
        public PointRole Role { get; set; } = PointRole.Generic;
        public string ProjectionKind { get; set; } = "Spatial";
        public string ViewName { get; set; } = "Projection2DView";

        public ViewRepresentation Execute(VisualPointData input)
        {
            var pointData = Role == PointRole.Generic ? input : input?.CreateSubset(Role);
            var view = new ViewRepresentation
            {
                ViewName = ViewName,
                Type = ViewType.Projection2D,
                PointData = pointData,
                Role = Role == PointRole.Generic ? null : Role,
                ProjectionKind = ProjectionKind,
                BackendViewObject = null
            };

            view.EncodingState["Plane"] = Plane;
            return view;
        }
    }
}
