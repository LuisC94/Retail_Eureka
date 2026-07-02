using System.ComponentModel.DataAnnotations.Schema;

namespace UserManagement.Entity
{
    public class UserPermission
    {
        public long Id { get; set; }

        public long PermissionId { get; set; }

        [ForeignKey("PermissionId")]
        public Permission Permission { get; set; }

        public long UserId { get; set; }

        [ForeignKey("UserId")]
        public User User { get; set; }

        public bool IsDeleted { get; set; }
    }
}
