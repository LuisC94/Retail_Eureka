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
    public class OrganizationController : ControllerBase
    {
        private readonly IOrganizationService _organizationService;

        public OrganizationController(IOrganizationService organizationService)
        {
            _organizationService = organizationService;
        }

        [HttpGet("Paginate")]
        [Authorize]
        [HasPermission("OrganizationScene.Paging.Permission")]

        public async Task<IActionResult> Paginate([FromQuery] PagingParameter pagingParameter)
        {
            var result = await _organizationService.Paginate(pagingParameter);
            return new OkObjectResult(result);
        }

        [HttpGet("All")]
        [Authorize]

        public async Task<IActionResult> GetAll()
        {
            var result = await _organizationService.GetOrganizations();
            return new OkObjectResult(result);
        }

        [HttpPost("Save")]
        [Authorize]
        [HasPermission("OrganizationScene.Save.Permission")]

        public async Task<IActionResult> Save([FromBody] Organization organization)
        {
            var result = await _organizationService.Save(organization);
            return new OkObjectResult(result);
        }

        [HttpPost("Update")]
        [Authorize]
        [HasPermission("OrganizationScene.Edit.Permission")]

        public async Task<IActionResult> Update([FromBody] Organization organization)
        {
            var result = await _organizationService.Update(organization);
            return new OkObjectResult(result);
        }

        [HttpDelete("Delete/{id}")]
        [Authorize]
        [HasPermission("OrganizationScene.Delete.Permission")]

        public async Task<IActionResult> Delete(long id)
        {
            var result = await _organizationService.Delete(id);
            return new OkObjectResult(result);
        }

        [HttpGet("{id}")]
        [Authorize]

        public async Task<IActionResult> GetById(long id)
        {
            var result = await _organizationService.GetById(id);
            return new OkObjectResult(result);
        }
    }
}
