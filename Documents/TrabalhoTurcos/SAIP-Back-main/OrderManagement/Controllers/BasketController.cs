using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using OrderManagement.Entity;
using OrderManagement.Interfaces;

namespace OrderManagement.Controllers
{
    [Route("/api/[controller]")]
    [ApiController]
    public class BasketController : ControllerBase
    {
        private readonly IBasketService _basketService;

        public BasketController(IBasketService basketService)
        {
            _basketService = basketService;
        }

        [HttpGet("BasketList/{userId}")]
        [Authorize]
        public async Task<IActionResult> GetBasketList(long userId)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();
            var result = await _basketService.GetBasketList(userId, token);
            return new OkObjectResult(result);
        }

        [HttpPost("Save")]
        [Authorize]

        public async Task<IActionResult> Save([FromBody] Basket basket)
        {
            var result = await _basketService.Save(basket);
            return new OkObjectResult(result);
        }

        [HttpPost("SaveAll")]
        [Authorize]

        public async Task<IActionResult> SaveAll([FromBody] List<Basket> basketList)
        {
            var result = await _basketService.SaveAll(basketList);
            return new OkObjectResult(result);
        }

        [HttpDelete("Delete/{id}/{productId}")]
        [Authorize]
        public async Task<IActionResult> Delete(long id, long productId)
        {
            var result = await _basketService.Delete(id, productId);
            return new OkObjectResult(result);
        }

        [HttpDelete("DeleteAll/{id}/{productId}")]
        [Authorize]

        public async Task<IActionResult> DeleteAll(long id, long productId)
        {
            var result = await _basketService.DeleteAll(id, productId);
            return new OkObjectResult(result);
        }

        [HttpGet("OrderBasketList/{id}")]
        [Authorize]
        public async Task<IActionResult> GetOrderBasketList(long id)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();
            var result = await _basketService.GetOrderBasketList(id, token);
            return new OkObjectResult(result);
        }
    }
}
