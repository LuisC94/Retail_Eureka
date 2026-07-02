using Microsoft.AspNetCore.Mvc;
using ProductManagement.Entity;
using ProductManagement.Model;

namespace ProductManagement.Interfaces
{
    public interface IProductService
    {
        Task<Result<PagingResult<PagedList<Product>>>> Paginate(PagingParameter pagingParameter, long userId, string token);
        Task<Result<PagingResult<PagedList<Product>>>> ShoppingPaginate(PagingParameter pagingParameter, string token, long categoryId, long userId);
        Task<Result<List<Product>>> GetProducts();
        Task<Result<Product>> Save(Product product);
        Task<Result<Product>> Update(Product product);
        Task<Result<Product>> Delete(long id);
        Task<Result<Product>> GetById(long id, string token);
        Task<Result<ProductComment>> AddComment(ProductComment productComment);
        Task<Result<PagingResult<PagedList<ProductComment>>>> CommentPaginate(PagingParameter pagingParameter, string token, long productId);
        Task<Result<List<CSVProductModel>>> GetProductsCSVFormat();
        Task<Result<List<CSVRatingModel>>> GetDeliveryRatingsCSVFormat();
        Task<Result<List<CSVRatingModel>>> GetQualityRatingsCSVFormat();
        Task<Result<List<CSVRatingModel>>> GetVendorRatingsCSVFormat();

    }
}
