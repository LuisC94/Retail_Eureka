using System.ComponentModel.DataAnnotations.Schema;

namespace UserManagement.Entity
{
    public class RolePermission
    {
        public long Id { get; set; }

        [ForeignKey("RoleId")]
        public long RoleId { get; set; }
        public Role Role { get; set; }


        [ForeignKey("PermissionId")]
        public long PermissionId { get; set; }
        public Permission Permission { get; set; }

        public bool IsDeleted { get; set; }
    }
}
