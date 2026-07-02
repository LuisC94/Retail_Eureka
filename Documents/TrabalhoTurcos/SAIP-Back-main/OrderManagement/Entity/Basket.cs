using OrderManagement.Model;
using System.ComponentModel.DataAnnotations.Schema;

namespace OrderManagement.Entity
{
    public class Basket
    {
        public long Id { get; set; }
        public long UserId { get; set; }
        public bool IsActive { get; set; }

        public bool IsDeleted { get; set; }

        [NotMapped] 
        public long ProductId { get; set; }
        
        [NotMapped] 
        public Product? Product { get; set; }
    }
}
