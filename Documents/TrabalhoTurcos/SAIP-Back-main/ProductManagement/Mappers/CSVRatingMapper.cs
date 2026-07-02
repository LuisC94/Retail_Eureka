using CsvHelper.Configuration;
using Microsoft.VisualBasic;
using ProductManagement.Model;

namespace ProductManagement.Mappers
{
    public class CSVRatingMapper : ClassMap<CSVRatingModel>
    {
        public CSVRatingMapper()
        {
            Map(m => m.UserId).Name("userId");
            Map(m => m.ProductId).Name("productId");
            Map(m => m.Rating).Name("rating");
        }
    }
}
