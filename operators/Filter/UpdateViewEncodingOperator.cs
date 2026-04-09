using OperatorPackage.Core;

namespace OperatorPackage.Filter
{
    public class UpdateViewEncodingOperator : IOperator<FilterMask, ViewRepresentation>
    {
        public ViewRepresentation TargetView { get; set; }

        public ViewRepresentation Execute(FilterMask input)
        {
            if (TargetView == null || input == null)
                return TargetView;

            TargetView.ApplyMask(input);
            TargetView.EncodingState["LastFilterMaskCount"] = input.Mask.Count;
            TargetView.EncodingState["SelectedCount"] = input.SelectedCount;
            TargetView.EncodingState["RequiresBackendSync"] = true;
            TargetView.EncodingState["FilterTargetRole"] = input.TargetRole?.ToString() ?? "All";

            return TargetView;
        }
    }
}
