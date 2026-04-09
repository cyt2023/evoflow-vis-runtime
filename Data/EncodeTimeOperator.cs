using System;
using System.Collections.Generic;
using OperatorPackage.Core;

namespace OperatorPackage.Data
{
    public class EncodeTimeOperator : IOperator<TabularData, TabularData>
    {
        public string TimeColumn { get; set; }
        public string OutputColumn { get; set; } = "EncodedTime";
        public string MinTimeMetadataKey { get; set; } = "Time.Min";
        public string MaxTimeMetadataKey { get; set; } = "Time.Max";

        public TabularData Execute(TabularData input)
        {
            var output = new TabularData();
            output.Columns.AddRange(input.Columns);

            if (!output.Columns.Contains(OutputColumn))
                output.Columns.Add(OutputColumn);

            DateTime? minTime = null;
            DateTime? maxTime = null;

            foreach (var row in input.Rows)
            {
                if (row.ContainsKey(TimeColumn) && DateTime.TryParse(row[TimeColumn].ToString(), out DateTime dt))
                {
                    if (minTime == null || dt < minTime.Value)
                        minTime = dt;
                    if (maxTime == null || dt > maxTime.Value)
                        maxTime = dt;
                }
            }

            foreach (var row in input.Rows)
            {
                var newRow = new Dictionary<string, object>(row);

                if (row.ContainsKey(TimeColumn) && DateTime.TryParse(row[TimeColumn].ToString(), out DateTime dt) && minTime != null)
                {
                    newRow[OutputColumn] = (float)(dt - minTime.Value).TotalSeconds;
                }
                else
                {
                    newRow[OutputColumn] = 0f;
                }

                output.Rows.Add(newRow);
            }

            if (minTime != null)
                output.Metadata[MinTimeMetadataKey] = minTime.Value;
            if (maxTime != null)
                output.Metadata[MaxTimeMetadataKey] = maxTime.Value;

            return output;
        }
    }
}
