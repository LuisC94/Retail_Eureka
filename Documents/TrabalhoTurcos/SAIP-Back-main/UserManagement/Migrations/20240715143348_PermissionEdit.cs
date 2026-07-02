using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace UserManagement.Migrations
{
    /// <inheritdoc />
    public partial class PermissionEdit : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.UpdateData(
                table: "Permissions",
                keyColumn: "Id",
                keyValue: 28L,
                columns: new[] { "Code", "Name" },
                values: new object[] { "OrderScene.Paging.Permission", "Sipariş Ekranı Listeleme Yetkisi" });

            migrationBuilder.UpdateData(
                table: "RolePermissions",
                keyColumn: "Id",
                keyValue: 39L,
                columns: new[] { "PermissionId", "RoleId" },
                values: new object[] { 28L, 3L });

            migrationBuilder.UpdateData(
                table: "RolePermissions",
                keyColumn: "Id",
                keyValue: 40L,
                column: "PermissionId",
                value: 21L);

            migrationBuilder.UpdateData(
                table: "UserPermissions",
                keyColumn: "Id",
                keyValue: 39L,
                columns: new[] { "PermissionId", "UserId" },
                values: new object[] { 28L, 3L });

            migrationBuilder.UpdateData(
                table: "UserPermissions",
                keyColumn: "Id",
                keyValue: 40L,
                column: "PermissionId",
                value: 21L);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.UpdateData(
                table: "Permissions",
                keyColumn: "Id",
                keyValue: 28L,
                columns: new[] { "Code", "Name" },
                values: new object[] { "ShoppingScene.List.Permission", "Alışveriş Ekranı Listeleme Yetkisi" });

            migrationBuilder.UpdateData(
                table: "RolePermissions",
                keyColumn: "Id",
                keyValue: 39L,
                columns: new[] { "PermissionId", "RoleId" },
                values: new object[] { 21L, 4L });

            migrationBuilder.UpdateData(
                table: "RolePermissions",
                keyColumn: "Id",
                keyValue: 40L,
                column: "PermissionId",
                value: 28L);

            migrationBuilder.UpdateData(
                table: "UserPermissions",
                keyColumn: "Id",
                keyValue: 39L,
                columns: new[] { "PermissionId", "UserId" },
                values: new object[] { 21L, 4L });

            migrationBuilder.UpdateData(
                table: "UserPermissions",
                keyColumn: "Id",
                keyValue: 40L,
                column: "PermissionId",
                value: 28L);
        }
    }
}
