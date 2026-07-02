using Microsoft.AspNetCore.Mvc;
using System.ComponentModel.DataAnnotations.Schema;

namespace OrderManagement.Model
{
    public class Product
    {
        public long Id { get; set; }
        public string Name { get; set; }
        public long FileId { get; set; }
        public double Price { get; set; }
        public bool IsDeleted { get; set; }
        public long UserId { get; set; }
        public string UserName { get; set; }
        public long CategoryId { get; set; }
        public string? Brand { get; set; }
        public double? Rating { get; set; }
        public string? Description { get; set; }
        public double? Sale { get; set; }
        public double? DiscountedPrice { get; set; }
        public FileContentResult? FileResult { get; set; }
        public double Stock { get; set; }
        public long CommentsCount { get; set; }

    }
}
