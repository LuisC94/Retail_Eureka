using System.ComponentModel.DataAnnotations.Schema;

namespace UserManagement.Entity
{
    public class ApplicationUser
    {
        public long Id { get; set; }
        public long UserId { get; set; }

        [ForeignKey("UserId")]
        public User User { get; set; }

        public string RefreshToken { get; set; }

        public DateTime RefreshTokenExpireDate { get; set; }

    }
}
