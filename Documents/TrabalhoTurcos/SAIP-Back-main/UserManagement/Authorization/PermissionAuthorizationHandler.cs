using Microsoft.AspNetCore.Authorization;
using Newtonsoft.Json;
using System.Net.Http.Headers;
using UserManagement.Model;

namespace UserManagement.Authorization
{
    public class PermissionAuthorizationHandler : AuthorizationHandler<PermissionRequirement>
    {
        private readonly IConfiguration _configuration;

        public PermissionAuthorizationHandler(IConfiguration configuration) 
        { 
            _configuration = configuration;
        }

        protected override async Task HandleRequirementAsync(AuthorizationHandlerContext context, PermissionRequirement requirement)
        {
            HttpClient client = new HttpClient();
            var httpContext = context.Resource as HttpContext;
            var token = httpContext.Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

            var response = await client.GetAsync(_configuration["AppSettings:ApiUrl"] + "/api/User/GetUserPermissions");

            if (response.IsSuccessStatusCode)
            {
                var responseStr = await response.Content.ReadAsStringAsync();

                if (!string.IsNullOrEmpty(responseStr))
                {
                    try
                    {
                        Result<List<string>> result = JsonConvert.DeserializeObject<Result<List<string>>>(responseStr);

                        if (result.GetIsSuccess().Value)
                        {
                            if (result.GetData().Contains(requirement.Permission))
                            {
                                context.Succeed(requirement);
                            }
                        }
                        else
                        {
                            context.Fail();
                        }
                    }
                    catch(Exception ex)
                    {
                        context.Fail();
                    }

                }
                else
                {
                    context.Fail();
                }
            }
            else
            {
                context.Fail();
            }
        }
    }
}
