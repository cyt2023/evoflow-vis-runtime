using OperatorPackage.Core;

namespace OperatorPackage.View
{
    public class BuildSTCViewOperator : IOperator<VisualPointData, ViewRepresentation>
    {
        public ViewRepresentation Execute(VisualPointData input)
        {
            var stcView = new ViewRepresentation
            {
                ViewName = "STCView",
                Type = ViewType.STC,
                PointData = input
            };

            if (input != null && input.HasODSemantics)
            {
                stcView.CoordinatedViews.Add(new BuildPointViewOperator
                {
                    Role = PointRole.Origin,
                    ViewName = "STC-OriginView"
                }.Execute(input));

                stcView.CoordinatedViews.Add(new BuildPointViewOperator
                {
                    Role = PointRole.Destination,
                    ViewName = "STC-DestinationView"
                }.Execute(input));

                stcView.CoordinatedViews.Add(new BuildLinkViewOperator
                {
                    ViewName = "STC-LinkView"
                }.Execute(input));
            }

            return stcView;
        }
    }
}
