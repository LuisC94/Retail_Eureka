using System.ComponentModel.DataAnnotations.Schema;

namespace UserManagement.Entity
{
    public class Organization
    {
        public long Id { get; set; }

        public string Name { get; set; }

        public long? ParentId { get; set; }

        [ForeignKey("ParentId")]
        public Organization? ParentOrganization { get; set; }

        public bool IsDeleted { get; set; }
    }
}
