using Microsoft.AspNetCore.Mvc;
using NotificationManagement.Entity;
using NotificationManagement.Interfaces;
using Microsoft.AspNetCore.Authorization;

namespace NotificationManagement.Controllers
{
    [Route("/api/[controller]")]
    [ApiController]
    public class NotificationController : ControllerBase
    {
        private readonly INotificationService _notificationService;

        public NotificationController(INotificationService notificationService)
        {
            _notificationService = notificationService;
        }

        [HttpGet("All/{userId}")]
        [Authorize]
        public async Task<IActionResult> GetAll(long userId)
        {
            var result = await _notificationService.GetNotifications(userId);
            return new OkObjectResult(result);
        }

        [HttpPost("Save")]
        [Authorize]
        public async Task<IActionResult> Save([FromBody] Notification notification)
        {
            var result = await _notificationService.Save(notification);
            return new OkObjectResult(result);
        }

        [HttpDelete("Delete/{id}")]
        [Authorize]
        public async Task<IActionResult> Delete(long id)
        {
            var result = await _notificationService.Delete(id);
            return new OkObjectResult(result);
        }

        [HttpGet("Read/{id}")]
        [Authorize]

        public async Task<IActionResult> Read(long id)
        {
            var result = await _notificationService.Read(id);
            return new OkObjectResult(result);
        }
    }
}
