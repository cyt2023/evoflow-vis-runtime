using System;
using System.Collections.Generic;
using System.Linq;
using OperatorPackage.Core;

namespace OperatorPackage.Filter
{
    public class CombineFiltersOperator : IOperator<List<FilterMask>, FilterMask>
    {
        public string Mode { get; set; } = "AND";

        public FilterMask Execute(List<FilterMask> input)
        {
            var result = new FilterMask();
            if (input == null || input.Count == 0) return result;

            int length = input[0].Mask.Count;
            result.TargetRole = input.Select(mask => mask.TargetRole).Distinct().Count() == 1
                ? input[0].TargetRole
                : null;

            for (int i = 0; i < length; i++)
            {
                bool value = (Mode == "AND");

                foreach (var mask in input)
                {
                    if (mask.Mask.Count != length)
                        throw new InvalidOperationException("All filter masks must have the same length before combination.");

                    if (Mode == "AND")
                        value = value && mask.Mask[i];
                    else
                        value = value || mask.Mask[i];
                }

                result.Mask.Add(value);
            }

            return result;
        }
    }
}
