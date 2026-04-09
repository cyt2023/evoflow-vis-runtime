using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using OperatorPackage.Core;

namespace OperatorPackage.Data
{
    public class ReadDataOperator : IOperator<string, TabularData>
    {
        public TabularData Execute(string filePath)
        {
            var table = new TabularData();

            if (!File.Exists(filePath))
            {
                throw new FileNotFoundException($"File not found: {filePath}");
            }

            using var reader = new StreamReader(filePath);
            var headerLine = reader.ReadLine();
            if (headerLine == null) return table;

            var rawColumns = ParseCsvLine(headerLine);
            for (var columnIndex = 0; columnIndex < rawColumns.Length; columnIndex++)
            {
                var columnName = rawColumns[columnIndex]?.Trim() ?? string.Empty;
                table.Columns.Add(string.IsNullOrWhiteSpace(columnName) ? $"column_{columnIndex}" : columnName);
            }

            string? line;
            while ((line = reader.ReadLine()) != null)
            {
                if (string.IsNullOrWhiteSpace(line))
                    continue;

                var values = ParseCsvLine(line);
                var row = new Dictionary<string, object>();

                for (int j = 0; j < table.Columns.Count && j < values.Length; j++)
                {
                    row[table.Columns[j]] = values[j];
                }

                table.Rows.Add(row);
            }

            return table;
        }

        private static string[] ParseCsvLine(string line)
        {
            var values = new List<string>();
            var buffer = new StringBuilder();
            var inQuotes = false;

            for (var i = 0; i < line.Length; i++)
            {
                var current = line[i];

                if (current == '"')
                {
                    if (inQuotes && i + 1 < line.Length && line[i + 1] == '"')
                    {
                        buffer.Append('"');
                        i++;
                    }
                    else
                    {
                        inQuotes = !inQuotes;
                    }
                    continue;
                }

                if (current == ',' && !inQuotes)
                {
                    values.Add(buffer.ToString());
                    buffer.Clear();
                    continue;
                }

                buffer.Append(current);
            }

            values.Add(buffer.ToString());
            return values.ToArray();
        }
    }
}
