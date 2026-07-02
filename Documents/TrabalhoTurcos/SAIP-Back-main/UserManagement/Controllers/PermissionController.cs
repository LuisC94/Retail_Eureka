using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using UserManagement.Authorization;
using UserManagement.Entity;
using UserManagement.Interfaces;
using UserManagement.Model;

namespace UserManagement.Controllers
{
    [Route("/api/[controller]")]
    [ApiController]
    public class PermissionController : ControllerBase
    {
        private readonly IPermissionService _permissionService;

        public PermissionController(IPermissionService permissionService)
        {
            _permissionService = permissionService;
        }

        [HttpGet("Paginate")]
        [Authorize]
        [HasPermission("PermissionScene.Paging.Permission")]
        public async Task<IActionResult> Paginate([FromQuery] PagingParameter pagingParameter)
        {
            var result = await _permissionService.Paginate(pagingParameter);
            return new OkObjectResult(result);
        }

        [HttpGet("All")]
        [Authorize]

        public async Task<IActionResult> GetAll()
        {
            var result = await _permissionService.GetPermissions();
            return new OkObjectResult(result);
        }

        [HttpPost("Save")]
        [Authorize]
        [HasPermission("PermissionScene.Save.Permission")]

        public async Task<IActionResult> Save([FromBody] Permission permission)
        {
            var result = await _permissionService.Save(permission);
            return new OkObjectResult(result);
        }

        [HttpPost("Update")]
        [Authorize]
        [HasPermission("PermissionScene.Edit.Permission")]

        public async Task<IActionResult> Update([FromBody] Permission permission)
        {
            var result = await _permissionService.Update(permission);
            return new OkObjectResult(result);
        }

        [HttpDelete("Delete/{id}")]
        [Authorize]
        [HasPermission("PermissionScene.Delete.Permission")]

        public async Task<IActionResult> Delete(long id)
        {
            var result = await _permissionService.Delete(id);
            return new OkObjectResult(result);
        }

        [HttpGet("{id}")]
        [Authorize]

        public async Task<IActionResult> GetById(long id)
        {
            var result = await _permissionService.GetById(id);
            return new OkObjectResult(result);
        }
    }
}
