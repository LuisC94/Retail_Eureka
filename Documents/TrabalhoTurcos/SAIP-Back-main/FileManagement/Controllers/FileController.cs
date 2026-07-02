using FileManagement.Authorization;
using FileManagement.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace FileManagement.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class FileController : ControllerBase
    {
        private readonly IFileService _fileService;

        public FileController(IFileService fileService)
        {
            _fileService = fileService;
        }

        [HttpPost("Save")]
        [Authorize]
        [HasPermission("FileScene.Save.Permission")]
        public async Task<IActionResult> Save(IFormFile file)
        {
            var result = await _fileService.Save(file);
            return new OkObjectResult(result);
        }

        [HttpDelete("Delete/{id}")]
        [HasPermission("FileScene.Delete.Permission")]
        [Authorize]
        public async Task<IActionResult> Delete(long id)
        {
            var result = await _fileService.Delete(id);
            return new OkObjectResult(result);
        }

        [HttpGet("{id}")]
        //[Authorize]

        public async Task<IActionResult> GetById(long id)
        {
            var result = await _fileService.GetById(id);

            return new OkObjectResult(result);
        }

    }
}
