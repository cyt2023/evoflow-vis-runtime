using System.Collections.Generic;

namespace OperatorPackage.Core
{
    public class TabularData
    {
        public List<string> Columns { get; set; } = new List<string>();
        public List<Dictionary<string, object>> Rows { get; set; } = new List<Dictionary<string, object>>();
        public Dictionary<string, object> Metadata { get; set; } = new Dictionary<string, object>();

        public int RowCount => Rows?.Count ?? 0;

        public object GetValue(int rowIndex, string columnName)
        {
            if (rowIndex < 0 || rowIndex >= RowCount || string.IsNullOrWhiteSpace(columnName))
                return null;

            var row = Rows[rowIndex];
            return row != null && row.TryGetValue(columnName, out var value) ? value : null;
        }
    }
}
