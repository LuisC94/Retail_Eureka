using CsvHelper.Configuration.Attributes;

namespace ProductManagement.Model
{
    public class CSVRatingModel
    {
        [Name("userId")]
        public long UserId { get; set; }

        [Name("productId")]
        public long ProductId {  get; set; }

        [Name("rating")]
        public double Rating { get; set; }

    }
}
