using OperatorPackage.Core;

namespace OperatorPackage.Data
{
    public class FilterRowsOperator : IOperator<TabularData, TabularData>
    {
        public string FilterColumn { get; set; }
        public string FilterValue { get; set; }

        public TabularData Execute(TabularData input)
        {
            var output = new TabularData();
            output.Columns.AddRange(input.Columns);

            foreach (var row in input.Rows)
            {
                if (row.ContainsKey(FilterColumn) && row[FilterColumn]?.ToString() == FilterValue)
                {
                    output.Rows.Add(row);
                }
            }

            return output;
        }
    }
}
