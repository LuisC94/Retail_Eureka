namespace UserManagement.Model
{
    public class ChangePasswordRequest
    {
        public long Id { get; set; }

        public string CurrentPassword { get; set; }

        public string Password { get; set; }
    }
}
