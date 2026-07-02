using System.ComponentModel.DataAnnotations.Schema;

namespace ProductManagement.Entity
{
    public class ProductStock
    {
        public long Id { get; set; }

        public long ProductId { get; set; }

        [ForeignKey("ProductId")]
        public Product Product { get; set; }

        public double Stock { get; set; }

        public bool IsDeleted { get; set; }

    }
}
