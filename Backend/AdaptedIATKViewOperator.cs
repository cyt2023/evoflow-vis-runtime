using OperatorPackage.Core;

namespace OperatorPackage.Backend
{
    public class AdaptedIATKViewOperator : IAdaptedIATKAdapter
    {
        public ViewRepresentation CreateView(ViewRepresentation view)
        {
            if (view == null)
                return null;

            view.BackendViewObject = new
            {
                Backend = "AdaptedIATK",
                Type = view.Type,
                Role = view.Role?.ToString() ?? "All",
                Projection = view.ProjectionKind ?? "None",
                Points = view.PointData?.Count ?? 0,
                Links = view.PointData?.Links?.Count ?? 0
            };
            view.EncodingState["BackendBuildPending"] = false;
            return view;
        }

        public ViewRepresentation UpdateView(ViewRepresentation view, FilterMask mask)
        {
            view?.ApplyMask(mask);
            if (view != null)
            {
                view.EncodingState["UpdatedByIATK"] = true;
                view.EncodingState["RequiresBackendSync"] = false;
            }
            return view;
        }
    }
}
