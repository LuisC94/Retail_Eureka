using System.ComponentModel.DataAnnotations.Schema;

namespace ProductManagement.Entity
{
    public class ProductComment
    {
        public long Id { get; set; }

        public string? Comment { get; set; }

        public long ProductId { get; set; }

        [ForeignKey("ProductId")]
        public Product? Product { get; set; }

        public long UserId { get; set; }
        
        public int VendorRating { get; set; }
        
        public int DeliveryRating { get; set; }
        
        public int QualityRating { get; set; }

        public DateTime? Date { get; set; }

        [NotMapped] 
        public string? UserName { get; set; }
    }
}
