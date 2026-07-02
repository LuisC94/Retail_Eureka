using System.ComponentModel.DataAnnotations.Schema;

namespace OrderManagement.Model
{
        public class User
        {
            public long Id { get; set; }

            public string Username { get; set; }

            public string Password { get; set; }

            public byte[]? Salt { get; set; }

            public string Name { get; set; }

            public string Surname { get; set; }

            public string Email { get; set; }

            public string Phone { get; set; }

            public bool IsDeleted { get; set; }
            public bool IsSystemData { get; set; }
        }
}
