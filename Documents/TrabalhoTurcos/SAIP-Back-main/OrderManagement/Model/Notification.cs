namespace OrderManagement.Model
{
    public class Notification
    {
        public long Id { get; set; }

        public string Message { get; set; }
        public string Link { get; set; }

        public long UserId { get; set; }

        public bool IsDeleted { get; set; }

        public bool IsReaded { get; set; } = false;

        public DateTime? Date {  get; set; }
    }
}
