using System.Collections.Generic;
using System.Linq;

namespace OperatorPackage.Core
{
    public class FilterMask
    {
        public List<bool> Mask { get; set; } = new List<bool>();
        public PointRole? TargetRole { get; set; }
        public int Count => Mask?.Count ?? 0;
        public IEnumerable<int> SelectedIndices => Mask?.Select((v, i) => v ? i : -1).Where(i => i >= 0) ?? Enumerable.Empty<int>();
        public int SelectedCount => SelectedIndices.Count();

        public FilterMask Combine(FilterMask other, string mode = "AND")
        {
            if (other == null) return this;
            var result = new FilterMask();
            result.TargetRole = TargetRole == other.TargetRole ? TargetRole : null;
            int length = Math.Min(this.Count, other.Count);
            for (int i = 0; i < length; i++)
            {
                bool value = mode == "AND" ? (this.Mask[i] && other.Mask[i]) : (this.Mask[i] || other.Mask[i]);
                result.Mask.Add(value);
            }
            return result;
        }
    }
}
