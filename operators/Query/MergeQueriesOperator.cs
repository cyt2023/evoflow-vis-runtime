using System.Collections.Generic;
using OperatorPackage.Core;

namespace OperatorPackage.Query
{
    public class MergeQueriesOperator : IOperator<List<QueryDefinition>, QueryDefinition>
    {
        public QueryDefinition Execute(List<QueryDefinition> input)
        {
            var query = new QueryDefinition
            {
                Type = QueryType.Merged
            };

            query.SubQueries.AddRange(input);
            return query;
        }
    }
}