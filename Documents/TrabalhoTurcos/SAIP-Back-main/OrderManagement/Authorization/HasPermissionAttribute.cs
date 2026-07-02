using Microsoft.AspNetCore.Authorization;

namespace OrderManagement.Authorization
{
    public class HasPermissionAttribute : AuthorizeAttribute
    {

        public HasPermissionAttribute(string permission) : base(policy: permission) 
        {
        
        }
    }
}
