using OperatorPackage.Core;

namespace OperatorPackage.View
{
    public class BuildPointViewOperator : IOperator<VisualPointData, ViewRepresentation>
    {
        public PointRole Role { get; set; } = PointRole.Generic;
        public string ViewName { get; set; } = "PointView";

        public ViewRepresentation Execute(VisualPointData input)
        {
            var pointData = Role == PointRole.Generic ? input : input?.CreateSubset(Role);
            return new ViewRepresentation
            {
                ViewName = ViewName,
                Type = ViewType.Point,
                Role = Role == PointRole.Generic ? null : Role,
                PointData = pointData
            };
        }
    }
}
