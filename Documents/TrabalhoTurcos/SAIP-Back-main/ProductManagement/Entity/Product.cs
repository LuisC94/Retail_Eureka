using Microsoft.AspNetCore.Mvc;
using System.ComponentModel.DataAnnotations.Schema;

namespace ProductManagement.Entity
{
    public class Product
    {
        public long Id { get; set; }
        public string Name { get; set; }
        public long FileId { get; set; }
        public double Price { get; set; }
        public bool IsDeleted { get; set; }
        public long UserId { get; set; }
        public long CategoryId {  get; set; }

        [ForeignKey("CategoryId")]
        public Category? Category { get; set; }
        public string? Brand { get; set; }
        public double? Rating { get; set; }
        public string? Description { get; set; }
        public double? Sale { get; set; }
        public double? DiscountedPrice { get; set; }


        [NotMapped]
        public FileContentResult? FileResult { get; set; }
        
        [NotMapped]
        public double Stock { get; set; }

        [NotMapped]
        public bool IsMostRating {  get; set; }

        [NotMapped]
        public List<ProductComment>? Comments { get; set; }

        [NotMapped]
        public long CommentsCount { get; set; }

        [NotMapped]
        public string UserName {  get; set; }
    }
}
