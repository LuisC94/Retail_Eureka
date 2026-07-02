using FileManagement.Entity;
using Microsoft.EntityFrameworkCore;


namespace FileManagement.DbContexts

{
    public class FileManagementContext : DbContext
    {
        public FileManagementContext(DbContextOptions<FileManagementContext> options) : base(options)
        {
        }

        public DbSet<Entity.File> Files { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            modelBuilder.Entity<Entity.File>().HasData(
                new Entity.File { Id = 1, Name = "1", Length = 14086, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "1.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 2, Name = "2", Length = 12481, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "2.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 3, Name = "3", Length = 8663, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "3.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 4, Name = "4", Length = 20976, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "4.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 5, Name = "5", Length = 11770, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "5.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 6, Name = "6", Length = 13585, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "6.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 7, Name = "7", Length = 15732, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "7.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 8, Name = "8", Length = 19896, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "8.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 9, Name = "9", Length = 13939, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "9.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 10, Name = "10", Length = 12552, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "10.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, },
                new Entity.File { Id = 11, Name = "11", Length = 20349, Path = Path.Combine(Directory.GetCurrentDirectory(), "Uploads", "11.png"), ContentType = "image/png", Extension = ".png", IsDeleted = false, }
             );
        }
    }
}
