namespace UserManagement.Entity
{
    public class Permission
    {
        public long Id { get; set; }

        public string Name { get; set; }

        public string Code { get; set; }

        public bool IsDeleted { get; set; }

        public bool IsSystemData { get; set; }

    }
}
