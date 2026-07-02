using ProductManagement.Entity;
using Microsoft.EntityFrameworkCore;


namespace ProductManagement.DbContexts

{
    public class ProductManagementContext : DbContext
    {
        public ProductManagementContext(DbContextOptions<ProductManagementContext> options) : base(options)
        {
        }

        public DbSet<Product> Products { get; set; }
        public DbSet<Category> Categories { get; set; }
        public DbSet<ProductStock> Stocks { get; set; }
        public DbSet<ProductComment> Comments { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            modelBuilder.Entity<Category>().HasData(
                new Category { Id = 1, Name = "Sebze", IsDeleted = false },
                new Category { Id = 2, Name = "Meyve", IsDeleted = false },
                new Category { Id = 3, Name = "Kuru Meyve",IsDeleted = false }
             );

            modelBuilder.Entity<Product>().HasData(
                new Product { Id = 1, Name = "Soğan Kuru Dökme Kg", Price = 9.90, IsDeleted = false, FileId = 1, UserId = 2, CategoryId = 1 },
                new Product { Id = 2, Name = "Hatay Arsuz Limonu Kg", Price = 17.95, IsDeleted = false, FileId = 2, UserId = 2, CategoryId = 1 },
                new Product { Id = 3, Name = "Muz Yerli Kg", Price = 51.90, IsDeleted = false, FileId = 3, UserId = 2, CategoryId = 2 },
                new Product { Id = 4, Name = "Portakal Sıkma File Kg", Price = 16.90, IsDeleted = false, FileId = 4, UserId = 2, CategoryId = 2 },
                new Product { Id = 5, Name = "Maydonoz Adet", Price = 15.95, IsDeleted = false, FileId = 5, UserId = 2, CategoryId = 1 },
                new Product { Id = 6, Name = "Hıyar Badem Paket Kg", Price = 44.95, IsDeleted = false, FileId = 6, UserId = 2, CategoryId = 1 },
                new Product { Id = 7, Name = "Mandalina Murcot", Price = 39.95, IsDeleted = false, FileId = 7, UserId = 3, CategoryId = 2 },
                new Product { Id = 8, Name = "Domates Kokteyl Kg", Price = 69.95, IsDeleted = false, FileId = 8, UserId = 3, CategoryId = 1 },
                new Product { Id = 9, Name = "Elma Starking Kg", Price = 34.90, IsDeleted = false, FileId = 9, UserId = 3, CategoryId = 2 },
                new Product { Id = 10, Name = "Kabak Sakız Kg", Price = 34.95, IsDeleted = false, FileId = 10, UserId = 3, CategoryId = 3 },
                new Product { Id = 11, Name = "Domates Salkım Kg", Price = 49.95, IsDeleted = false, FileId = 11, UserId = 3, CategoryId = 3 }
             );

            modelBuilder.Entity<ProductStock>().HasData(
                new ProductStock { Id = 1, ProductId = 1, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 2, ProductId = 2, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 3, ProductId = 3, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 4, ProductId = 4, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 5, ProductId = 5, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 6, ProductId = 6, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 7, ProductId = 7, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 8, ProductId = 8, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 9, ProductId = 9, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 10, ProductId = 10, Stock = 100, IsDeleted = false },
                new ProductStock { Id = 11, ProductId = 11, Stock = 100, IsDeleted = false }
             );
        }
    }
}
