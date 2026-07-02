using CsvHelper.Configuration.Attributes;

namespace ProductManagement.Model
{
    public class CSVProductModel
    {
        [Name("productId")]
        public long ProductId {  get; set; }

        [Name("name")]
        public string Name { get; set; }

        [Name("category")]
        public string Category { get; set; }
    }
}
