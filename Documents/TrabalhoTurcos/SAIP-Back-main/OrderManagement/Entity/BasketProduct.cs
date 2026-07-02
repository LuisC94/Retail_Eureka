using System.ComponentModel.DataAnnotations.Schema;

namespace OrderManagement.Entity
{
    public class BasketProduct
    {
        public long Id { get; set; }
        public long ProductId { get; set; }

        [ForeignKey("BasketId")]
        public Basket Basket { get; set; }
        public long BasketId { get; set; }

        public bool IsDeleted { get; set; }
        public bool IsActive { get; set; }

    }
}
