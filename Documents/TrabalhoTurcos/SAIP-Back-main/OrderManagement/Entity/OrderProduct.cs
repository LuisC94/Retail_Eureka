using Microsoft.AspNetCore.Mvc;
using OrderManagement.Model;
using System.ComponentModel.DataAnnotations.Schema;

namespace OrderManagement.Entity
{
    public class OrderProduct
    {
        public long Id { get; set; }
        public long ProductId { get; set; }

        [ForeignKey("OrderId")]
        public Order Order { get; set; }
        public long OrderId { get; set; }
        public int OrderStatus { get; set; }
        public DateTime ProccessDate { get; set; }
        public long VendorId { get; set; }
        public string? TrackingNo { get; set; }
        public long? FileId { get; set; }
        public DateTime? TrackingDate { get; set; }
        public DateTime? CompletionDate { get; set; }


        [NotMapped]
        public Product? Product { get; set; }

        [NotMapped]
        public FileContentResult? FileResult { get; set; }

        [NotMapped]
        public string? FileName { get; set; }

    }
}
