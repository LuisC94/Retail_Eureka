using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using OrderManagement.Entity;
using OrderManagement.Interfaces;
using OrderManagement.Model;

namespace OrderManagement.Controllers
{
    [Route("/api/[controller]")]
    [ApiController]
    public class OrderController : ControllerBase
    {
        private readonly IOrderService _orderService;

        public OrderController(IOrderService orderService)
        {
            _orderService = orderService;
        }

        [HttpGet("Paginate/{userId}")]
        [Authorize]
        public async Task<IActionResult> Paginate([FromQuery] PagingParameter pagingParameter, long userId)
        {
            var result = await _orderService.Paginate(pagingParameter, userId);
            return new OkObjectResult(result);
        }

        [HttpGet("OrderList/{userId}")]
        [Authorize]
        public async Task<IActionResult> GetOrderList(long userId)
        {
            var result = await _orderService.GetOrderList(userId);
            return new OkObjectResult(result);
        }

        [HttpPost("Save")]
        [Authorize]

        public async Task<IActionResult> Save([FromBody] Order order)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();

            var result = await _orderService.Save(order, token);
            return new OkObjectResult(result);
        }

        [HttpPost("UpdateStatus")]
        [Authorize]
        public async Task<IActionResult> UpdateStatus([FromBody] OrderProduct orderProduct)
        {
            var result = await _orderService.UpdateStatus(orderProduct);
            return new OkObjectResult(result);
        }

        [HttpGet("{id}")]
        [Authorize]
        public async Task<IActionResult> GetById(long id)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();

            var result = await _orderService.GetById(id, token);
            return new OkObjectResult(result);
        }

        [HttpGet("ComingOrder/{id}")]
        [Authorize]
        public async Task<IActionResult> GetComingOrderById(long id)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();

            var result = await _orderService.GetComingOrderById(id, token);
            return new OkObjectResult(result);
        }

        [HttpGet("ComingPaginate/{userId}")]
        [Authorize]
        public async Task<IActionResult> ComingPaginate([FromQuery] PagingParameter pagingParameter, long userId)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();

            var result = await _orderService.ComingPaginate(pagingParameter, userId, token);
            return new OkObjectResult(result);
        }

        [HttpPost("AddInvoice")]
        [Authorize]
        public async Task<IActionResult> AddInvoice([FromBody] OrderProduct orderProduct)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();

            var result = await _orderService.AddInvoice(orderProduct, token);
            return new OkObjectResult(result);
        }

        [HttpDelete("DeleteInvoice/{id}")]
        [Authorize]
        public async Task<IActionResult> DeleteInvoice(long id)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();

            var result = await _orderService.DeleteInvoice(id, token);
            return new OkObjectResult(result);
        }
    }
}
