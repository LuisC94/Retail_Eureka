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
    public class RoleController : ControllerBase
    {
        private readonly IRoleService _roleService;

        public RoleController(IRoleService roleService)
        {
            _roleService = roleService;
        }

        [HttpGet("Paginate")]
        [Authorize]
        [HasPermission("RoleScene.Paging.Permission")]

        public async Task<IActionResult> Paginate([FromQuery] PagingParameter pagingParameter)
        {
            var result = await _roleService.Paginate(pagingParameter);
            return new OkObjectResult(result);
        }

        [HttpGet("All")]
        [Authorize]

        public async Task<IActionResult> GetAll()
        {
            var result = await _roleService.GetRoles();
            return new OkObjectResult(result);
        }

        [HttpPost("Save")]
        [Authorize]
        [HasPermission("RoleScene.Save.Permission")]

        public async Task<IActionResult> Save([FromBody] Role role)
        {
            var result = await _roleService.Save(role);
            return new OkObjectResult(result);
        }

        [HttpPost("Update")]
        [Authorize]
        [HasPermission("RoleScene.Edit.Permission")]

        public async Task<IActionResult> Update([FromBody] Role role)
        {
            var result = await _roleService.Update(role);
            return new OkObjectResult(result);
        }

        [HttpDelete("Delete/{id}")]
        [Authorize]
        [HasPermission("RoleScene.Delete.Permission")]

        public async Task<IActionResult> Delete(long id)
        {
            var result = await _roleService.Delete(id);
            return new OkObjectResult(result);
        }

        [HttpGet("{id}")]
        [Authorize]

        public async Task<IActionResult> GetById(long id)
        {
            var result = await _roleService.GetById(id);
            return new OkObjectResult(result);
        }
    }
}
