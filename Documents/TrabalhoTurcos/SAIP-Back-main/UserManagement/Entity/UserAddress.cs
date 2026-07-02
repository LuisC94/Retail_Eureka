using System.ComponentModel.DataAnnotations.Schema;

namespace UserManagement.Entity
{
    public class UserAddress
    {
        public long Id { get; set; }
        public string Name { get; set; }
        public string Surname { get; set; }

        public string Country { get; set; }

        public string City { get; set; }

        public string District { get; set; }

        public string Address { get; set; }
        public string Phone { get; set; }
        public string AddressHeader { get; set; }
        public long InvoiceType { get; set; }
        public string? VKN { get; set; }
        public string? VergiDairesi { get; set; }
        public string? FirmaAdi { get; set; }
        public long UserId { get; set; }

        [ForeignKey("UserId")]
        public User? User { get; set; }

        public bool IsDeleted { get; set; }
    }
}
