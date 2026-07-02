using Microsoft.AspNetCore.Authorization;

namespace OrderManagement.Authorization
{
    public class PermissionRequirement : IAuthorizationRequirement
    {
        public PermissionRequirement(string permission)
        {
            Permission = permission;

        }

        public string Permission { get; }
    }
}
