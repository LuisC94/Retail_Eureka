using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

#pragma warning disable CA1814 // Prefer jagged arrays over multidimensional

namespace ProductManagement.Migrations
{
    /// <inheritdoc />
    public partial class Initial : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Categories",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Name = table.Column<string>(type: "text", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Categories", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Products",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Name = table.Column<string>(type: "text", nullable: false),
                    FileId = table.Column<long>(type: "bigint", nullable: false),
                    Price = table.Column<double>(type: "double precision", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false),
                    UserId = table.Column<long>(type: "bigint", nullable: false),
                    CategoryId = table.Column<long>(type: "bigint", nullable: false),
                    Brand = table.Column<string>(type: "text", nullable: true),
                    Rating = table.Column<double>(type: "double precision", nullable: true),
                    Description = table.Column<string>(type: "text", nullable: true),
                    Sale = table.Column<double>(type: "double precision", nullable: true),
                    DiscountedPrice = table.Column<double>(type: "double precision", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Products", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Products_Categories_CategoryId",
                        column: x => x.CategoryId,
                        principalTable: "Categories",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Comments",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Comment = table.Column<string>(type: "text", nullable: true),
                    ProductId = table.Column<long>(type: "bigint", nullable: false),
                    UserId = table.Column<long>(type: "bigint", nullable: false),
                    VendorRating = table.Column<int>(type: "integer", nullable: false),
                    DeliveryRating = table.Column<int>(type: "integer", nullable: false),
                    QualityRating = table.Column<int>(type: "integer", nullable: false),
                    Date = table.Column<DateTime>(type: "timestamp with time zone", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Comments", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Comments_Products_ProductId",
                        column: x => x.ProductId,
                        principalTable: "Products",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "Stocks",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    ProductId = table.Column<long>(type: "bigint", nullable: false),
                    Stock = table.Column<double>(type: "double precision", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Stocks", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Stocks_Products_ProductId",
                        column: x => x.ProductId,
                        principalTable: "Products",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.InsertData(
                table: "Categories",
                columns: new[] { "Id", "IsDeleted", "Name" },
                values: new object[,]
                {
                    { 1L, false, "Sebze" },
                    { 2L, false, "Meyve" },
                    { 3L, false, "Kuru Meyve" }
                });

            migrationBuilder.InsertData(
                table: "Products",
                columns: new[] { "Id", "Brand", "CategoryId", "Description", "DiscountedPrice", "FileId", "IsDeleted", "Name", "Price", "Rating", "Sale", "UserId" },
                values: new object[,]
                {
                    { 1L, null, 1L, null, null, 1L, false, "Soğan Kuru Dökme Kg", 9.9000000000000004, null, null, 2L },
                    { 2L, null, 1L, null, null, 2L, false, "Hatay Arsuz Limonu Kg", 17.949999999999999, null, null, 2L },
                    { 3L, null, 2L, null, null, 3L, false, "Muz Yerli Kg", 51.899999999999999, null, null, 2L },
                    { 4L, null, 2L, null, null, 4L, false, "Portakal Sıkma File Kg", 16.899999999999999, null, null, 2L },
                    { 5L, null, 1L, null, null, 5L, false, "Maydonoz Adet", 15.949999999999999, null, null, 2L },
                    { 6L, null, 1L, null, null, 6L, false, "Hıyar Badem Paket Kg", 44.950000000000003, null, null, 2L },
                    { 7L, null, 2L, null, null, 7L, false, "Mandalina Murcot", 39.950000000000003, null, null, 3L },
                    { 8L, null, 1L, null, null, 8L, false, "Domates Kokteyl Kg", 69.950000000000003, null, null, 3L },
                    { 9L, null, 2L, null, null, 9L, false, "Elma Starking Kg", 34.899999999999999, null, null, 3L },
                    { 10L, null, 3L, null, null, 10L, false, "Kabak Sakız Kg", 34.950000000000003, null, null, 3L },
                    { 11L, null, 3L, null, null, 11L, false, "Domates Salkım Kg", 49.950000000000003, null, null, 3L }
                });

            migrationBuilder.InsertData(
                table: "Stocks",
                columns: new[] { "Id", "IsDeleted", "ProductId", "Stock" },
                values: new object[,]
                {
                    { 1L, false, 1L, 100.0 },
                    { 2L, false, 2L, 100.0 },
                    { 3L, false, 3L, 100.0 },
                    { 4L, false, 4L, 100.0 },
                    { 5L, false, 5L, 100.0 },
                    { 6L, false, 6L, 100.0 },
                    { 7L, false, 7L, 100.0 },
                    { 8L, false, 8L, 100.0 },
                    { 9L, false, 9L, 100.0 },
                    { 10L, false, 10L, 100.0 },
                    { 11L, false, 11L, 100.0 }
                });

            migrationBuilder.CreateIndex(
                name: "IX_Comments_ProductId",
                table: "Comments",
                column: "ProductId");

            migrationBuilder.CreateIndex(
                name: "IX_Products_CategoryId",
                table: "Products",
                column: "CategoryId");

            migrationBuilder.CreateIndex(
                name: "IX_Stocks_ProductId",
                table: "Stocks",
                column: "ProductId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Comments");

            migrationBuilder.DropTable(
                name: "Stocks");

            migrationBuilder.DropTable(
                name: "Products");

            migrationBuilder.DropTable(
                name: "Categories");
        }
    }
}
