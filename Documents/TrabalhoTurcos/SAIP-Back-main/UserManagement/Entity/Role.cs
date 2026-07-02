using System.ComponentModel.DataAnnotations.Schema;

namespace UserManagement.Entity
{
    public class Role
    {
        public long Id { get; set; }

        public string Name { get; set; }

        public bool IsDeleted { get; set; }

        public bool IsSystemData { get; set; }

        [NotMapped]
        public List<long> Permissions { get; set; } = new List<long>();
    }
}
