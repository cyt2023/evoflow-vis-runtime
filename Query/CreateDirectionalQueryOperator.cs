using OperatorPackage.Core;

namespace OperatorPackage.Query
{
    public class CreateDirectionalQueryOperator : IOperator<QueryDefinition, QueryDefinition>
    {
        public QueryDefinition DestinationQuery { get; set; }

        public QueryDefinition Execute(QueryDefinition originQuery)
        {
            var query = new QueryDefinition
            {
                Type = QueryType.Directional
            };
            query.OriginQuery = originQuery;
            query.SubQueries.Add(originQuery);
            if (DestinationQuery != null)
            {
                query.DestinationQuery = DestinationQuery;
                query.SubQueries.Add(DestinationQuery);
            }
            
            query.Parameters["Direction"] = "OD";
            query.Parameters["CombineMode"] = "OriginAndDestination";
            return query;
        }
    }
}
