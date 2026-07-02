using CsvHelper.Configuration;
using Microsoft.VisualBasic;
using ProductManagement.Model;

namespace ProductManagement.Mappers
{
    public class CSVProductMapper : ClassMap<CSVProductModel>
    {
        public CSVProductMapper()
        {
            Map(m => m.Name).Name("name");
            Map(m => m.ProductId).Name("productId");
            Map(m => m.Category).Name("category");
        }
    }
}
