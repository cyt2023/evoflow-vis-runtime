using System.Globalization;
using OperatorPackage.Core;

namespace OperatorPackage.Data
{
    public class MapToVisualSpaceOperator : IOperator<TabularData, VisualPointData>
    {
        public VisualMapping Mapping { get; set; }

        public VisualPointData Execute(TabularData input)
        {
            var output = new VisualPointData();
            if (input == null || input.Rows == null || Mapping == null)
                return output;

            for (int rowIndex = 0; rowIndex < input.Rows.Count; rowIndex++)
            {
                var row = input.Rows[rowIndex];

                if (Mapping.HasODColumns)
                {
                    string rowId = GetRowId(row, rowIndex);
                    var originPoint = new VisualPoint
                    {
                        OriginalPointIndex = output.Points.Count,
                        SourceRowIndex = rowIndex,
                        RowId = rowId,
                        Role = PointRole.Origin,
                        X = GetFloat(row, Mapping.OriginXColumn),
                        Y = GetFloat(row, Mapping.OriginYColumn),
                        Z = Mapping.IsSTCMode ? GetFloat(row, Mapping.OriginTimeColumn) : GetFloat(row, Mapping.OriginZColumn),
                        Time = GetFloat(row, Mapping.OriginTimeColumn),
                        ColorValue = GetFloat(row, Mapping.ColorColumn),
                        SizeValue = GetFloat(row, Mapping.SizeColumn)
                    };
                    output.Points.Add(originPoint);

                    var destinationPoint = new VisualPoint
                    {
                        OriginalPointIndex = output.Points.Count,
                        SourceRowIndex = rowIndex,
                        RowId = rowId,
                        Role = PointRole.Destination,
                        X = GetFloat(row, Mapping.DestinationXColumn),
                        Y = GetFloat(row, Mapping.DestinationYColumn),
                        Z = Mapping.IsSTCMode ? GetFloat(row, Mapping.DestinationTimeColumn) : GetFloat(row, Mapping.DestinationZColumn),
                        Time = GetFloat(row, Mapping.DestinationTimeColumn),
                        ColorValue = GetFloat(row, Mapping.ColorColumn),
                        SizeValue = GetFloat(row, Mapping.SizeColumn)
                    };
                    output.Points.Add(destinationPoint);

                    output.Links.Add(new ODLink
                    {
                        OriginIndex = output.Points.Count - 2,
                        DestinationIndex = output.Points.Count - 1,
                        Weight = 1f
                    });
                    output.HasODSemantics = true;
                }
                else
                {
                    var point = new VisualPoint
                    {
                        OriginalPointIndex = output.Points.Count,
                        SourceRowIndex = rowIndex,
                        RowId = GetRowId(row, rowIndex),
                        Role = PointRole.Generic,
                        X = GetFloat(row, Mapping.XColumn),
                        Y = GetFloat(row, Mapping.YColumn),
                        Z = Mapping.IsSTCMode ? GetFloat(row, Mapping.TimeColumn) : GetFloat(row, Mapping.ZColumn),
                        Time = GetFloat(row, Mapping.TimeColumn),
                        ColorValue = GetFloat(row, Mapping.ColorColumn),
                        SizeValue = GetFloat(row, Mapping.SizeColumn)
                    };

                    output.Points.Add(point);
                }
            }

            output.UpdateTimeRange();
            return output;
        }

        private string GetRowId(System.Collections.Generic.Dictionary<string, object> row, int rowIndex)
        {
            if (!string.IsNullOrWhiteSpace(Mapping.TripIdColumn) &&
                row != null &&
                row.TryGetValue(Mapping.TripIdColumn, out var value) &&
                value != null)
            {
                return value.ToString();
            }

            return $"row-{rowIndex}";
        }

        private float GetFloat(System.Collections.Generic.Dictionary<string, object> row, string columnName)
        {
            if (string.IsNullOrEmpty(columnName) || row == null || !row.ContainsKey(columnName))
                return 0f;

            var rawValue = row[columnName];
            var stringValue = rawValue switch
            {
                IFormattable formattable => formattable.ToString(null, CultureInfo.InvariantCulture),
                _ => rawValue?.ToString()
            };

            return float.TryParse(
                stringValue,
                NumberStyles.Float | NumberStyles.AllowThousands,
                CultureInfo.InvariantCulture,
                out float value)
                ? value
                : 0f;
        }
    }
}
