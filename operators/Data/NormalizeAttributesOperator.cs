using System;
using System.Collections.Generic;
using System.Globalization;
using OperatorPackage.Core;

namespace OperatorPackage.Data
{
    public class NormalizeAttributesOperator : IOperator<TabularData, TabularData>
    {
        public List<string> TargetColumns { get; set; } = new List<string>();

        public TabularData Execute(TabularData input)
        {
            var output = new TabularData();
            output.Columns.AddRange(input.Columns);

            var minValues = new Dictionary<string, float>();
            var maxValues = new Dictionary<string, float>();

            foreach (var col in TargetColumns)
            {
                minValues[col] = float.MaxValue;
                maxValues[col] = float.MinValue;
            }

            foreach (var row in input.Rows)
            {
                foreach (var col in TargetColumns)
                {
                    if (row.ContainsKey(col) && float.TryParse(
                        row[col].ToString(),
                        NumberStyles.Float | NumberStyles.AllowThousands,
                        CultureInfo.InvariantCulture,
                        out float value))
                    {
                        if (value < minValues[col]) minValues[col] = value;
                        if (value > maxValues[col]) maxValues[col] = value;
                    }
                }
            }

            foreach (var row in input.Rows)
            {
                var newRow = new Dictionary<string, object>(row);

                foreach (var col in TargetColumns)
                {
                    if (row.ContainsKey(col) && float.TryParse(
                        row[col].ToString(),
                        NumberStyles.Float | NumberStyles.AllowThousands,
                        CultureInfo.InvariantCulture,
                        out float value))
                    {
                        float min = minValues[col];
                        float max = maxValues[col];
                        float normalized = (Math.Abs(max - min) < 1e-6f) ? 0f : (value - min) / (max - min);
                        newRow[col] = normalized;
                    }
                }

                output.Rows.Add(newRow);
            }

            return output;
        }
    }
}
