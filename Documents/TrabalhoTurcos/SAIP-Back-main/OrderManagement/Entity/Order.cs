using OrderManagement.Model;
using System.ComponentModel.DataAnnotations.Schema;

namespace OrderManagement.Entity
{
    public class Order
    {
        public long Id { get; set; }
        public double Price { get; set; }
        public string? OrderNo { get; set; }
        public DateTime? OrderDate { get; set; }
        public int? OrderStatus { get; set; }
        public long UserId { get; set; }
        public Basket? Basket { get; set; }
        [ForeignKey("BasketId")]
        public long BasketId { get; set; }
        public long DeliveryAddressId { get; set; }
        public long InvoiceAddressId { get; set; }


        [NotMapped]
        public List<OrderProduct>? OrderProducts { get; set; }

        [NotMapped]
        public UserAddress? DeliveryAddress { get; set; }

        [NotMapped]
        public UserAddress? InvoiceAddress { get; set; }
    }
}
