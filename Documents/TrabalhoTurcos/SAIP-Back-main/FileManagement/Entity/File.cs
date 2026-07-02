namespace FileManagement.Entity
{
    public class File
    {
        public long Id { get; set; }
        public string Name { get; set; }
        public string ContentType { get; set; }
        public string Path { get; set; }
        public string Extension { get; set; }
        public decimal Length { get; set; }
        public bool IsDeleted { get; set; }
      
    }
}
