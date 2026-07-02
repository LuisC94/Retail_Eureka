using CsvHelper;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using ProductManagement.Authorization;
using ProductManagement.Entity;
using ProductManagement.Interfaces;
using ProductManagement.Mappers;
using ProductManagement.Model;
using System.Globalization;
using System.Text;

namespace ProductManagement.Controllers
{
    [Route("/api/[controller]")]
    [ApiController]
    public class ProductController : ControllerBase
    {
        private readonly IProductService _productService;

        public ProductController(IProductService productService)
        {
            _productService = productService;
        }

        [HttpGet("ShoppingPaginate/{categoryId}/{userId}")]
        //[Authorize]
        //[HasPermission("ShoppingScene.List.Permission")]
        public async Task<IActionResult> ShoppimngPaginate([FromQuery] PagingParameter pagingParameter, long categoryId, long userId)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();
            var result = await _productService.ShoppingPaginate(pagingParameter, token, categoryId, userId);
            return new OkObjectResult(result);
        }

        [HttpGet("Paginate/{userId}")]
        [Authorize]
        [HasPermission("ProductScene.Paging.Permission")]
        public async Task<IActionResult> Paginate([FromQuery] PagingParameter pagingParameter, long userId)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();
            var result = await _productService.Paginate(pagingParameter, userId, token);
            return new OkObjectResult(result);
        }

        [HttpGet("All")]
        [Authorize]

        public async Task<IActionResult> GetAll()
        {
            var result = await _productService.GetProducts();
            return new OkObjectResult(result);
        }

        [HttpPost("Save")]
        [Authorize]
        [HasPermission("ProductScene.Save.Permission")]

        public async Task<IActionResult> Save([FromBody] Product product)
        {
            var result = await _productService.Save(product);
            return new OkObjectResult(result);
        }

        [HttpPost("Update")]
        [Authorize]
        [HasPermission("ProductScene.Edit.Permission")]

        public async Task<IActionResult> Update([FromBody] Product product)
        {
            var result = await _productService.Update(product);
            return new OkObjectResult(result);
        }

        [HttpDelete("Delete/{id}")]
        [Authorize]
        [HasPermission("ProductScene.Delete.Permission")]

        public async Task<IActionResult> Delete(long id)
        {
            var result = await _productService.Delete(id);
            return new OkObjectResult(result);
        }

        [HttpGet("{id}")]
        [Authorize]

        public async Task<IActionResult> GetById(long id)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();

            var result = await _productService.GetById(id, token);
            return new OkObjectResult(result);
        }

        [HttpGet("GetByIdForBasket/{id}")]
        [Authorize]

        public async Task<IActionResult> GetByIdForBasket(long id)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();

            var result = await _productService.GetById(id, token);
            result.GetData().FileResult = null;
            return new OkObjectResult(result);
        }

        [HttpGet("CommentPaginate/{productId}")]
        [Authorize]
        public async Task<IActionResult> CommentPaginate([FromQuery] PagingParameter pagingParameter, long productId)
        {
            var token = Request.Headers["Authorization"].FirstOrDefault()?.Split(' ').Last();
            var result = await _productService.CommentPaginate(pagingParameter, token, productId);
            return new OkObjectResult(result);
        }

        [HttpPost("AddComment")]
        [Authorize]
        public async Task<IActionResult> AddComment([FromBody] ProductComment productComment)
        {
            var result = await _productService.AddComment(productComment);
            return new OkObjectResult(result);
        }

        [HttpGet("GetProductsCSVFormat")]

        public async Task<IActionResult> GetProductsCSVFormat()
        {
            var result = await _productService.GetProductsCSVFormat();

            var stream = new MemoryStream();
            using (var writeFile = new StreamWriter(stream, new UTF8Encoding(true), leaveOpen: true))
            {

                var csv = new CsvWriter(writeFile, CultureInfo.InvariantCulture);
                csv.WriteRecords(result.GetData());
            }
            stream.Position = 0; //reset stream
            return File(stream, "application/octet-stream", "products.csv");
        }

        [HttpGet("GetQualityRatingsCSVFormat")]

        public async Task<IActionResult> GetQualityRatingsCSVFormat()
        {
            var result = await _productService.GetQualityRatingsCSVFormat();

            var stream = new MemoryStream();
            using (var writeFile = new StreamWriter(stream, new UTF8Encoding(true), leaveOpen: true))
            {

                var csv = new CsvWriter(writeFile, CultureInfo.InvariantCulture);
                csv.WriteRecords(result.GetData());
            }
            stream.Position = 0; //reset stream
            return File(stream, "application/octet-stream", "ratings.csv");
        }

        [HttpGet("GetVendorRatingsCSVFormat")]

        public async Task<IActionResult> GetVendorRatingsCSVFormat()
        {
            var result = await _productService.GetVendorRatingsCSVFormat();

            var stream = new MemoryStream();
            using (var writeFile = new StreamWriter(stream, new UTF8Encoding(true), leaveOpen: true))
            {

                var csv = new CsvWriter(writeFile, CultureInfo.InvariantCulture);
                csv.WriteRecords(result.GetData());
            }
            stream.Position = 0; //reset stream
            return File(stream, "application/octet-stream", "ratings.csv");
        }

        [HttpGet("GetDeliveryRatingsCSVFormat")]

        public async Task<IActionResult> GetDeliveryRatingsCSVFormat()
        {
            var result = await _productService.GetDeliveryRatingsCSVFormat();

            var stream = new MemoryStream();
            using (var writeFile = new StreamWriter(stream, new UTF8Encoding(true), leaveOpen: true))
            {

                var csv = new CsvWriter(writeFile, CultureInfo.InvariantCulture);
                csv.WriteRecords(result.GetData());
            }
            stream.Position = 0; //reset stream
            return File(stream, "application/octet-stream", "ratings.csv");
        }
    }
}
