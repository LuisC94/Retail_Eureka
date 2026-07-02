using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

#pragma warning disable CA1814 // Prefer jagged arrays over multidimensional

namespace FileManagement.Migrations
{
    /// <inheritdoc />
    public partial class Initial : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Files",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Name = table.Column<string>(type: "text", nullable: false),
                    ContentType = table.Column<string>(type: "text", nullable: false),
                    Path = table.Column<string>(type: "text", nullable: false),
                    Extension = table.Column<string>(type: "text", nullable: false),
                    Length = table.Column<decimal>(type: "numeric", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Files", x => x.Id);
                });

            migrationBuilder.InsertData(
                table: "Files",
                columns: new[] { "Id", "ContentType", "Extension", "IsDeleted", "Length", "Name", "Path" },
                values: new object[,]
                {
                    { 1L, "image/png", ".png", false, 14086m, "1", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\1.png" },
                    { 2L, "image/png", ".png", false, 12481m, "2", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\2.png" },
                    { 3L, "image/png", ".png", false, 8663m, "3", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\3.png" },
                    { 4L, "image/png", ".png", false, 20976m, "4", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\4.png" },
                    { 5L, "image/png", ".png", false, 11770m, "5", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\5.png" },
                    { 6L, "image/png", ".png", false, 13585m, "6", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\6.png" },
                    { 7L, "image/png", ".png", false, 15732m, "7", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\7.png" },
                    { 8L, "image/png", ".png", false, 19896m, "8", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\8.png" },
                    { 9L, "image/png", ".png", false, 13939m, "9", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\9.png" },
                    { 10L, "image/png", ".png", false, 12552m, "10", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\10.png" },
                    { 11L, "image/png", ".png", false, 20349m, "11", "C:\\Users\\Asus\\Documents\\GitHub\\SAIP-Back\\FileManagement\\Uploads\\11.png" }
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Files");
        }
    }
}
