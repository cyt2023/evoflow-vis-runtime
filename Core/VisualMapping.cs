namespace OperatorPackage.Core
{
    public class VisualMapping
    {
        public string TripIdColumn { get; set; }
        public string XColumn { get; set; }
        public string YColumn { get; set; }
        public string ZColumn { get; set; }
        public string TimeColumn { get; set; }
        public bool IsSTCMode { get; set; }

        public string OriginXColumn { get; set; }
        public string OriginYColumn { get; set; }
        public string OriginZColumn { get; set; }
        public string OriginTimeColumn { get; set; }

        public string DestinationXColumn { get; set; }
        public string DestinationYColumn { get; set; }
        public string DestinationZColumn { get; set; }
        public string DestinationTimeColumn { get; set; }

        public string ColorColumn { get; set; }
        public string SizeColumn { get; set; }

        public bool HasODColumns =>
            !string.IsNullOrWhiteSpace(OriginXColumn) &&
            !string.IsNullOrWhiteSpace(OriginYColumn) &&
            !string.IsNullOrWhiteSpace(DestinationXColumn) &&
            !string.IsNullOrWhiteSpace(DestinationYColumn);
    }
}
