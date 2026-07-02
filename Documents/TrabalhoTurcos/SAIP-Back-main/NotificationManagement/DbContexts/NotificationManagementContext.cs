using Microsoft.EntityFrameworkCore;
using NotificationManagement.Entity;

namespace NotificationManagement.DbContexts
{
    public class NotificationManagementContext : DbContext
    {
        public NotificationManagementContext(DbContextOptions<NotificationManagementContext> options) : base(options)
        {
        }
        public DbSet<Notification> Notifications { get; set; }
        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {

        }
    }
}