using System.ComponentModel.DataAnnotations.Schema;

namespace UserManagement.Entity
{
    public class OrganizationUser
    {
        public long Id { get; set; }

        public long OrganizationId { get; set; }

        [ForeignKey("OrganizationId")]
        public Organization Organization { get; set; }

        public long UserId { get; set; }

        [ForeignKey("UserId")]
        public User User { get; set; }

        public bool IsDeleted { get; set; }
    }
}
