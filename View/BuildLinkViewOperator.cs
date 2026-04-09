using OperatorPackage.Core;

namespace OperatorPackage.View
{
    public class BuildLinkViewOperator : IOperator<VisualPointData, ViewRepresentation>
    {
        public string ViewName { get; set; } = "LinkView";

        public ViewRepresentation Execute(VisualPointData input)
        {
            var view = new ViewRepresentation
            {
                ViewName = ViewName,
                Type = ViewType.Link,
                PointData = input,
                BackendViewObject = null
            };

            view.EncodingState["LinkCount"] = input?.Links?.Count ?? 0;
            view.EncodingState["HasODSemantics"] = input?.HasODSemantics ?? false;
            return view;
        }
    }
}
