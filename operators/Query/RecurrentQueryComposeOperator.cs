using System.Collections.Generic;
using OperatorPackage.Core;

namespace OperatorPackage.Query
{
    public class RecurrentQueryComposeOperator : IOperator<List<QueryDefinition>, QueryDefinition>
    {
        public List<int> Years { get; set; } = new List<int>();
        public List<int> Months { get; set; } = new List<int>();
        public List<System.DayOfWeek> DaysOfWeek { get; set; } = new List<System.DayOfWeek>();
        public List<int> Hours { get; set; } = new List<int>();

        public QueryDefinition Execute(List<QueryDefinition> input)
        {
            var query = new QueryDefinition
            {
                Type = QueryType.Recurrent
            };

            query.SubQueries.AddRange(input);
            query.Years.AddRange(Years);
            query.Months.AddRange(Months);
            query.DaysOfWeek.AddRange(DaysOfWeek);
            query.Hours.AddRange(Hours);
            return query;
        }
    }
}
