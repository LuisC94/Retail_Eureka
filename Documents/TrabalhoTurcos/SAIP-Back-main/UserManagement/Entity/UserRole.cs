using System.ComponentModel.DataAnnotations.Schema;

namespace UserManagement.Entity
{
    public class UserRole
    {
        public long Id { get; set; }

        public long RoleId { get; set; }

        [ForeignKey("RoleId")]
        public Role Role { get; set; }

        public long UserId { get; set; }

        [ForeignKey("UserId")]
        public User User { get; set; }

        public bool IsDeleted { get; set; }
    }
}
