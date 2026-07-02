using System;
using Microsoft.EntityFrameworkCore.Migrations;
using Npgsql.EntityFrameworkCore.PostgreSQL.Metadata;

#nullable disable

#pragma warning disable CA1814 // Prefer jagged arrays over multidimensional

namespace UserManagement.Migrations
{
    /// <inheritdoc />
    public partial class Initial : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Organizations",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Name = table.Column<string>(type: "text", nullable: false),
                    ParentId = table.Column<long>(type: "bigint", nullable: true),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Organizations", x => x.Id);
                    table.ForeignKey(
                        name: "FK_Organizations_Organizations_ParentId",
                        column: x => x.ParentId,
                        principalTable: "Organizations",
                        principalColumn: "Id");
                });

            migrationBuilder.CreateTable(
                name: "Permissions",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Name = table.Column<string>(type: "text", nullable: false),
                    Code = table.Column<string>(type: "text", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false),
                    IsSystemData = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Permissions", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Roles",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Name = table.Column<string>(type: "text", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false),
                    IsSystemData = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Roles", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Users",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    Username = table.Column<string>(type: "text", nullable: false),
                    Password = table.Column<string>(type: "text", nullable: false),
                    Salt = table.Column<byte[]>(type: "bytea", nullable: true),
                    Name = table.Column<string>(type: "text", nullable: false),
                    Surname = table.Column<string>(type: "text", nullable: false),
                    Email = table.Column<string>(type: "text", nullable: false),
                    Phone = table.Column<string>(type: "text", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false),
                    IsSystemData = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Users", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "RolePermissions",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    RoleId = table.Column<long>(type: "bigint", nullable: false),
                    PermissionId = table.Column<long>(type: "bigint", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_RolePermissions", x => x.Id);
                    table.ForeignKey(
                        name: "FK_RolePermissions_Permissions_PermissionId",
                        column: x => x.PermissionId,
                        principalTable: "Permissions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_RolePermissions_Roles_RoleId",
                        column: x => x.RoleId,
                        principalTable: "Roles",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ApplicationUsers",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    UserId = table.Column<long>(type: "bigint", nullable: false),
                    RefreshToken = table.Column<string>(type: "text", nullable: false),
                    RefreshTokenExpireDate = table.Column<DateTime>(type: "timestamp with time zone", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ApplicationUsers", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ApplicationUsers_Users_UserId",
                        column: x => x.UserId,
                        principalTable: "Users",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "OrganizationUsers",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    OrganizationId = table.Column<long>(type: "bigint", nullable: false),
                    UserId = table.Column<long>(type: "bigint", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_OrganizationUsers", x => x.Id);
                    table.ForeignKey(
                        name: "FK_OrganizationUsers_Organizations_OrganizationId",
                        column: x => x.OrganizationId,
                        principalTable: "Organizations",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_OrganizationUsers_Users_UserId",
                        column: x => x.UserId,
                        principalTable: "Users",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "UserPermissions",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    PermissionId = table.Column<long>(type: "bigint", nullable: false),
                    UserId = table.Column<long>(type: "bigint", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_UserPermissions", x => x.Id);
                    table.ForeignKey(
                        name: "FK_UserPermissions_Permissions_PermissionId",
                        column: x => x.PermissionId,
                        principalTable: "Permissions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_UserPermissions_Users_UserId",
                        column: x => x.UserId,
                        principalTable: "Users",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "UserRoles",
                columns: table => new
                {
                    Id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("Npgsql:ValueGenerationStrategy", NpgsqlValueGenerationStrategy.IdentityByDefaultColumn),
                    RoleId = table.Column<long>(type: "bigint", nullable: false),
                    UserId = table.Column<long>(type: "bigint", nullable: false),
                    IsDeleted = table.Column<bool>(type: "boolean", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_UserRoles", x => x.Id);
                    table.ForeignKey(
                        name: "FK_UserRoles_Roles_RoleId",
                        column: x => x.RoleId,
                        principalTable: "Roles",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_UserRoles_Users_UserId",
                        column: x => x.UserId,
                        principalTable: "Users",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.InsertData(
                table: "Permissions",
                columns: new[] { "Id", "Code", "IsDeleted", "IsSystemData", "Name" },
                values: new object[,]
                {
                    { 1L, "PermissionScene.Paging.Permission", false, true, "Yetki Ekranı Listeleme Yetkisi" },
                    { 2L, "PermissionScene.Save.Permission", false, true, "Yetki Ekranı Kayıt Yetkisi" },
                    { 3L, "PermissionScene.Edit.Permission", false, true, "Yetki Ekranı Güncelleme Yetkisi" },
                    { 4L, "PermissionScene.Delete.Permission", false, true, "Yetki Ekranı Silme Yetkisi" },
                    { 5L, "RoleScene.Paging.Permission", false, true, "Rol Ekranı Listeleme Yetkisi" },
                    { 6L, "RoleScene.Save.Permission", false, true, "Rol Ekranı Kayıt Yetkisi" },
                    { 7L, "RoleScene.Edit.Permission", false, true, "Rol Ekranı Güncelleme Yetkisi" },
                    { 8L, "RoleScene.Delete.Permission", false, true, "Rol Ekranı Silme Yetkisi" },
                    { 9L, "OrganizationScene.Paging.Permission", false, true, "Organizasyon Ekranı Listeleme Yetkisi" },
                    { 10L, "OrganizationScene.Save.Permission", false, true, "Organizasyon Ekranı Kayıt Yetkisi" },
                    { 11L, "OrganizationScene.Edit.Permission", false, true, "Organizasyon Ekranı Güncelleme Yetkisi" },
                    { 12L, "OrganizationScene.Delete.Permission", false, true, "Organizasyon Ekranı Silme Yetkisi" },
                    { 13L, "UserScene.Paging.Permission", false, true, "Kullanıcı Ekranı Listeleme Yetkisi" },
                    { 14L, "UserScene.Save.Permission", false, true, "Kullanıcı Ekranı Kayıt Yetkisi" },
                    { 15L, "UserScene.Edit.Permission", false, true, "Kullanıcı Ekranı Güncelleme Yetkisi" },
                    { 16L, "UserScene.Delete.Permission", false, true, "Kullanıcı Ekranı Silme Yetkisi" },
                    { 17L, "MenuScene.List.Permission", false, true, "Menü Ekranı Listeleme Yetkisi" },
                    { 18L, "MenuScene.Save.Permission", false, true, "Menü Ekranı Kayıt Yetkisi" },
                    { 19L, "MenuScene.Edit.Permission", false, true, "Menü Ekranı Güncelleme Yetkisi" },
                    { 20L, "MenuScene.Delete.Permission", false, true, "Menü Ekranı Silme Yetkisi" },
                    { 21L, "DashboardScene.View.Permission", false, true, "Dashboard Görüntüleme Yetkisi" },
                    { 22L, "ProductScene.Paging.Permission", false, true, "Ürün Ekranı Listeleme Yetkisi" },
                    { 23L, "ProductScene.Save.Permission", false, true, "Ürün Ekranı Kayıt Yetkisi" },
                    { 24L, "ProductScene.Edit.Permission", false, true, "Ürün Ekranı Güncelleme Yetkisi" },
                    { 25L, "ProductScene.Delete.Permission", false, true, "Ürün Ekranı Silme Yetkisi" },
                    { 26L, "FileScene.Save.Permission", false, true, "Dosya Ekranı Kayıt Yetkisi" },
                    { 27L, "FileScene.Delete.Permission", false, true, "Dosya Ekranı Silme Yetkisi" },
                    { 28L, "ShoppingScene.List.Permission", false, true, "Alışveriş Ekranı Listeleme Yetkisi" }
                });

            migrationBuilder.InsertData(
                table: "Roles",
                columns: new[] { "Id", "IsDeleted", "IsSystemData", "Name" },
                values: new object[,]
                {
                    { 1L, false, true, "SuperAdmin" },
                    { 2L, false, true, "Firm" },
                    { 3L, false, true, "Producer" },
                    { 4L, false, true, "EndUser" }
                });

            migrationBuilder.InsertData(
                table: "Users",
                columns: new[] { "Id", "Email", "IsDeleted", "IsSystemData", "Name", "Password", "Phone", "Salt", "Surname", "Username" },
                values: new object[,]
                {
                    { 1L, "super@test.com", false, true, "SuperAdmin", "DBD9DCE9DB51E56E1468B18F44233EB1FF625ADCECAAE2D7E9776BC714AF69D2A360B57CDB7C4E098C6225543BF83C50DAEC23A8DAADF9212BADF6F26760911C", "+905077352772", new byte[] { 3, 251, 182, 108, 1, 165, 5, 95, 117, 7, 42, 45, 196, 160, 190, 194, 65, 169, 48, 49, 99, 22, 120, 177, 165, 246, 57, 186, 94, 216, 59, 80, 48, 229, 210, 31, 5, 173, 219, 134, 83, 73, 90, 196, 220, 216, 163, 14, 219, 106, 52, 183, 13, 250, 15, 143, 154, 208, 85, 45, 29, 52, 13, 105 }, "SuperAdmin", "superadmin" },
                    { 2L, "firm@test.com", false, true, "Firm", "DBD9DCE9DB51E56E1468B18F44233EB1FF625ADCECAAE2D7E9776BC714AF69D2A360B57CDB7C4E098C6225543BF83C50DAEC23A8DAADF9212BADF6F26760911C", "+905077352772", new byte[] { 3, 251, 182, 108, 1, 165, 5, 95, 117, 7, 42, 45, 196, 160, 190, 194, 65, 169, 48, 49, 99, 22, 120, 177, 165, 246, 57, 186, 94, 216, 59, 80, 48, 229, 210, 31, 5, 173, 219, 134, 83, 73, 90, 196, 220, 216, 163, 14, 219, 106, 52, 183, 13, 250, 15, 143, 154, 208, 85, 45, 29, 52, 13, 105 }, "Firm", "firm" },
                    { 3L, "producer@test.com", false, true, "Producer", "DBD9DCE9DB51E56E1468B18F44233EB1FF625ADCECAAE2D7E9776BC714AF69D2A360B57CDB7C4E098C6225543BF83C50DAEC23A8DAADF9212BADF6F26760911C", "+905077352772", new byte[] { 3, 251, 182, 108, 1, 165, 5, 95, 117, 7, 42, 45, 196, 160, 190, 194, 65, 169, 48, 49, 99, 22, 120, 177, 165, 246, 57, 186, 94, 216, 59, 80, 48, 229, 210, 31, 5, 173, 219, 134, 83, 73, 90, 196, 220, 216, 163, 14, 219, 106, 52, 183, 13, 250, 15, 143, 154, 208, 85, 45, 29, 52, 13, 105 }, "Producer", "producer" },
                    { 4L, "enduser@test.com", false, true, "End User", "DBD9DCE9DB51E56E1468B18F44233EB1FF625ADCECAAE2D7E9776BC714AF69D2A360B57CDB7C4E098C6225543BF83C50DAEC23A8DAADF9212BADF6F26760911C", "+905077352772", new byte[] { 3, 251, 182, 108, 1, 165, 5, 95, 117, 7, 42, 45, 196, 160, 190, 194, 65, 169, 48, 49, 99, 22, 120, 177, 165, 246, 57, 186, 94, 216, 59, 80, 48, 229, 210, 31, 5, 173, 219, 134, 83, 73, 90, 196, 220, 216, 163, 14, 219, 106, 52, 183, 13, 250, 15, 143, 154, 208, 85, 45, 29, 52, 13, 105 }, "End User", "enduser" }
                });

            migrationBuilder.InsertData(
                table: "RolePermissions",
                columns: new[] { "Id", "IsDeleted", "PermissionId", "RoleId" },
                values: new object[,]
                {
                    { 1L, false, 1L, 1L },
                    { 2L, false, 2L, 1L },
                    { 3L, false, 3L, 1L },
                    { 4L, false, 4L, 1L },
                    { 5L, false, 5L, 1L },
                    { 6L, false, 6L, 1L },
                    { 7L, false, 7L, 1L },
                    { 8L, false, 8L, 1L },
                    { 9L, false, 9L, 1L },
                    { 10L, false, 10L, 1L },
                    { 11L, false, 11L, 1L },
                    { 12L, false, 12L, 1L },
                    { 13L, false, 13L, 1L },
                    { 14L, false, 14L, 1L },
                    { 15L, false, 15L, 1L },
                    { 16L, false, 16L, 1L },
                    { 17L, false, 17L, 1L },
                    { 18L, false, 18L, 1L },
                    { 19L, false, 19L, 1L },
                    { 20L, false, 20L, 1L },
                    { 21L, false, 21L, 1L },
                    { 22L, false, 26L, 1L },
                    { 23L, false, 27L, 1L },
                    { 24L, false, 21L, 2L },
                    { 25L, false, 22L, 2L },
                    { 26L, false, 23L, 2L },
                    { 27L, false, 24L, 2L },
                    { 28L, false, 25L, 2L },
                    { 29L, false, 26L, 2L },
                    { 30L, false, 27L, 2L },
                    { 31L, false, 28L, 2L },
                    { 32L, false, 21L, 3L },
                    { 33L, false, 22L, 3L },
                    { 34L, false, 23L, 3L },
                    { 35L, false, 24L, 3L },
                    { 36L, false, 25L, 3L },
                    { 37L, false, 26L, 3L },
                    { 38L, false, 27L, 3L },
                    { 39L, false, 21L, 4L },
                    { 40L, false, 28L, 4L }
                });

            migrationBuilder.InsertData(
                table: "UserPermissions",
                columns: new[] { "Id", "IsDeleted", "PermissionId", "UserId" },
                values: new object[,]
                {
                    { 1L, false, 1L, 1L },
                    { 2L, false, 2L, 1L },
                    { 3L, false, 3L, 1L },
                    { 4L, false, 4L, 1L },
                    { 5L, false, 5L, 1L },
                    { 6L, false, 6L, 1L },
                    { 7L, false, 7L, 1L },
                    { 8L, false, 8L, 1L },
                    { 9L, false, 9L, 1L },
                    { 10L, false, 10L, 1L },
                    { 11L, false, 11L, 1L },
                    { 12L, false, 12L, 1L },
                    { 13L, false, 13L, 1L },
                    { 14L, false, 14L, 1L },
                    { 15L, false, 15L, 1L },
                    { 16L, false, 16L, 1L },
                    { 17L, false, 17L, 1L },
                    { 18L, false, 18L, 1L },
                    { 19L, false, 19L, 1L },
                    { 20L, false, 20L, 1L },
                    { 21L, false, 21L, 1L },
                    { 22L, false, 26L, 1L },
                    { 23L, false, 27L, 1L },
                    { 24L, false, 21L, 2L },
                    { 25L, false, 22L, 2L },
                    { 26L, false, 23L, 2L },
                    { 27L, false, 24L, 2L },
                    { 28L, false, 25L, 2L },
                    { 29L, false, 26L, 2L },
                    { 30L, false, 27L, 2L },
                    { 31L, false, 28L, 2L },
                    { 32L, false, 21L, 3L },
                    { 33L, false, 22L, 3L },
                    { 34L, false, 23L, 3L },
                    { 35L, false, 24L, 3L },
                    { 36L, false, 25L, 3L },
                    { 37L, false, 26L, 3L },
                    { 38L, false, 27L, 3L },
                    { 39L, false, 21L, 4L },
                    { 40L, false, 28L, 4L }
                });

            migrationBuilder.InsertData(
                table: "UserRoles",
                columns: new[] { "Id", "IsDeleted", "RoleId", "UserId" },
                values: new object[,]
                {
                    { 1L, false, 1L, 1L },
                    { 2L, false, 2L, 2L },
                    { 3L, false, 3L, 3L },
                    { 4L, false, 4L, 4L }
                });

            migrationBuilder.CreateIndex(
                name: "IX_ApplicationUsers_UserId",
                table: "ApplicationUsers",
                column: "UserId");

            migrationBuilder.CreateIndex(
                name: "IX_OrganizationUsers_OrganizationId",
                table: "OrganizationUsers",
                column: "OrganizationId");

            migrationBuilder.CreateIndex(
                name: "IX_OrganizationUsers_UserId",
                table: "OrganizationUsers",
                column: "UserId");

            migrationBuilder.CreateIndex(
                name: "IX_Organizations_ParentId",
                table: "Organizations",
                column: "ParentId");

            migrationBuilder.CreateIndex(
                name: "IX_RolePermissions_PermissionId",
                table: "RolePermissions",
                column: "PermissionId");

            migrationBuilder.CreateIndex(
                name: "IX_RolePermissions_RoleId",
                table: "RolePermissions",
                column: "RoleId");

            migrationBuilder.CreateIndex(
                name: "IX_UserPermissions_PermissionId",
                table: "UserPermissions",
                column: "PermissionId");

            migrationBuilder.CreateIndex(
                name: "IX_UserPermissions_UserId",
                table: "UserPermissions",
                column: "UserId");

            migrationBuilder.CreateIndex(
                name: "IX_UserRoles_RoleId",
                table: "UserRoles",
                column: "RoleId");

            migrationBuilder.CreateIndex(
                name: "IX_UserRoles_UserId",
                table: "UserRoles",
                column: "UserId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "ApplicationUsers");

            migrationBuilder.DropTable(
                name: "OrganizationUsers");

            migrationBuilder.DropTable(
                name: "RolePermissions");

            migrationBuilder.DropTable(
                name: "UserPermissions");

            migrationBuilder.DropTable(
                name: "UserRoles");

            migrationBuilder.DropTable(
                name: "Organizations");

            migrationBuilder.DropTable(
                name: "Permissions");

            migrationBuilder.DropTable(
                name: "Roles");

            migrationBuilder.DropTable(
                name: "Users");
        }
    }
}
