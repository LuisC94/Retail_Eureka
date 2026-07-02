using Microsoft.EntityFrameworkCore;
using ProductManagement.DbContexts;
using ProductManagement.Entity;
using ProductManagement.Interfaces;
using ProductManagement.Model;
using System.Data;
using Microsoft.AspNetCore.Mvc;
using System.Net.Http.Headers;
using Newtonsoft.Json;
using Python.Runtime;
using Newtonsoft.Json.Linq;
using System.Diagnostics;
using System.Reflection;
using System.Linq.Expressions;

namespace ProductManagement.Services
{
    public class ProductService : IProductService
    {
        private readonly ProductManagementContext _dbContext;

        private readonly IConfiguration _configuration;

        public ProductService(ProductManagementContext dbContext, IConfiguration configuration)
        {
            _dbContext = dbContext;
            _configuration = configuration;
        }

        public async Task<Result<Product>> Delete(long id)
        {
            var result = new Result<Product>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldProduct = await _dbContext.Products.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldProduct != null)
                    {
                        oldProduct.IsDeleted = true;

                        var stockRecords = await _dbContext.Stocks.Where(x => x.ProductId == id).ToListAsync();
                        stockRecords.ForEach(x => x.IsDeleted = true);

                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldProduct);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<Product>> GetById(long id, string token)
        {
            var result = new Result<Product>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var product = await _dbContext.Products.Include(x => x.Category).Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (product != null)
                    {
                        product.FileResult = await GetFileResult(product.FileId, token);
                        product.Stock = await _dbContext.Stocks.Where(x => x.ProductId == id && !x.IsDeleted).Select(s => s.Stock).FirstOrDefaultAsync();
                        product.Comments = await _dbContext.Comments.Where(x => x.ProductId == id).ToListAsync();
                        product.CommentsCount = await _dbContext.Comments.Where(x => x.ProductId == id).CountAsync();

                        product.Comments.ForEach(x => x.UserName = GetUserName(x.UserId, token).Result);
                        product.UserName = await GetUserName(product.UserId, token);

                        result.SetData(product);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();
                }
            }

            return result;
        }

        public async Task<Result<List<Product>>> GetProducts()
        {
            var result = new Result<List<Product>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Products.Include(x => x.Category).Where(x => !x.IsDeleted).ToListAsync();
                    data.ForEach(x => x.Stock = _dbContext.Stocks.Where(s => s.ProductId == x.Id && !x.IsDeleted).Select(s => s.Stock).FirstOrDefault());

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<PagingResult<PagedList<Product>>>> Paginate(PagingParameter pagingParameter, long userId, string token)
        {
            var result = new Result<PagingResult<PagedList<Product>>>();

            string lowerFilterText = string.IsNullOrEmpty(pagingParameter.FilterText) ? null : pagingParameter.FilterText.ToLower();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var queryable = _dbContext.Products.Include(x => x.Category).Where(x => x.UserId == userId
                    && (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText))) ).Select(s => new Product
                    {
                        Id = s.Id,
                        Name = s.Name,
                        Price = s.Price,
                        FileId = s.FileId,
                        UserId = s.UserId,
                        IsDeleted = s.IsDeleted,
                        Category = s.Category,
                        CategoryId = s.CategoryId,
                        Brand = s.Brand,
                        Description = s.Description,
                        DiscountedPrice = s.DiscountedPrice,
                        Sale = s.Sale,
                        Rating = s.Rating,
                        IsMostRating = s.Rating != null ? !_dbContext.Products.Any(x => x.Rating > s.Rating) : false,
                        CommentsCount = _dbContext.Comments.Where(x => x.ProductId == s.Id).Count()
                    });

                    var pagination = PagedList<Product>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);

                    pagination.ForEach(x => x.FileResult = GetFileResult(x.FileId, token).Result);
                    pagination.ForEach(x => x.Stock = _dbContext.Stocks.Where(s => s.ProductId == x.Id && !x.IsDeleted).Select(s => s.Stock).FirstOrDefault());

                    result.SetData(new PagingResult<PagedList<Product>>()
                    {
                        Items = pagination,
                        TotalCount = pagination.TotalCount,
                    });

                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<PagingResult<PagedList<Product>>>> ShoppingPaginate(PagingParameter pagingParameter, string token, long categoryId, long userId)
        {
            var result = new Result<PagingResult<PagedList<Product>>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    string lowerFilterText = string.IsNullOrEmpty(pagingParameter.FilterText) ? null : pagingParameter.FilterText.ToLower();

                    //Tüm ürünler
                    if (categoryId == 0)
                    {
                        var queryable = _dbContext.Products.Include(x => x.Category).Where(x => !x.IsDeleted
                        && (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText)))
                        && (userId != 0 ? (x.UserId != userId) : true)).Select(s => new Product
                        {
                            Id = s.Id,
                            Name = s.Name,
                            Price = s.Price,
                            FileId = s.FileId,
                            UserId = s.UserId,
                            IsDeleted = s.IsDeleted,
                            Category = s.Category,
                            CategoryId = s.CategoryId,
                            Brand = s.Brand,
                            Description = s.Description,
                            DiscountedPrice = s.DiscountedPrice,
                            Sale = s.Sale,
                            Rating = s.Rating,
                            IsMostRating = s.Rating != null ? !_dbContext.Products.Any(x => x.Rating > s.Rating) : false,
                            CommentsCount = _dbContext.Comments.Where(x => x.ProductId == s.Id).Count()
                        });

                        var pagination = PagedList<Product>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);
                        pagination.ForEach(x => x.Stock = _dbContext.Stocks.Where(s => s.ProductId == x.Id && !x.IsDeleted).Select(s => s.Stock).FirstOrDefault());
                        pagination.ForEach(x => x.FileResult = GetFileResult(x.FileId, token).Result);

                        result.SetData(new PagingResult<PagedList<Product>>()
                        {
                            Items = pagination,
                            TotalCount = pagination.TotalCount,
                        });

                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    //Ürün kategorilerine göre
                    else if (categoryId > 0 && categoryId < 4)
                    {
                        var queryable = _dbContext.Products.Include(x => x.Category).Where(x => !x.IsDeleted && x.CategoryId == categoryId
                        && (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText)))
                        && (userId != 0 ? (x.UserId != userId) : true)).Select(s => new Product
                        {
                            Id = s.Id,
                            Name = s.Name,
                            Price = s.Price,
                            FileId = s.FileId,
                            UserId = s.UserId,
                            IsDeleted = s.IsDeleted,
                            Category = s.Category,
                            CategoryId = s.CategoryId,
                            Brand = s.Brand,
                            Description = s.Description,
                            DiscountedPrice = s.DiscountedPrice,
                            Sale = s.Sale,
                            Rating = s.Rating,
                            IsMostRating = s.Rating != null ? !_dbContext.Products.Any(x => x.Rating > s.Rating) : false,
                            CommentsCount = _dbContext.Comments.Where(x => x.ProductId == s.Id).Count()
                        });

                        var pagination = PagedList<Product>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);
                        pagination.ForEach(x => x.Stock = _dbContext.Stocks.Where(s => s.ProductId == x.Id && !x.IsDeleted).Select(s => s.Stock).FirstOrDefault());
                        pagination.ForEach(x => x.FileResult = GetFileResult(x.FileId, token).Result);

                        result.SetData(new PagingResult<PagedList<Product>>()
                        {
                            Items = pagination,
                            TotalCount = pagination.TotalCount,
                        });

                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    //Yüksek puanlı ürünler
                    else if (categoryId == 5)
                    {
                        var queryable = _dbContext.Products.Include(x => x.Category).Where(x => !x.IsDeleted && (x.Rating != null && x.Rating > 4)
                        && (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText)))
                        && (userId != 0 ? (x.UserId != userId) : true)).Select(s => new Product
                        {
                            Id = s.Id,
                            Name = s.Name,
                            Price = s.Price,
                            FileId = s.FileId,
                            UserId = s.UserId,
                            IsDeleted = s.IsDeleted,
                            Category = s.Category,
                            CategoryId = s.CategoryId,
                            Brand = s.Brand,
                            Description = s.Description,
                            DiscountedPrice = s.DiscountedPrice,
                            Sale = s.Sale,
                            Rating = s.Rating,
                            IsMostRating = s.Rating != null ? !_dbContext.Products.Any(x => x.Rating > s.Rating) : false,
                            CommentsCount = _dbContext.Comments.Where(x => x.ProductId == s.Id).Count()
                        }).OrderByDescending(o => o.Rating);

                        var pagination = PagedList<Product>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);
                        pagination.ForEach(x => x.Stock = _dbContext.Stocks.Where(s => s.ProductId == x.Id && !x.IsDeleted).Select(s => s.Stock).FirstOrDefault());
                        pagination.ForEach(x => x.FileResult = GetFileResult(x.FileId, token).Result);

                        result.SetData(new PagingResult<PagedList<Product>>()
                        {
                            Items = pagination,
                            TotalCount = pagination.TotalCount,
                        });

                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    //İndirimli ürünler
                    else if (categoryId == 6)
                    {
                        var queryable = _dbContext.Products.Include(x => x.Category).Where(x => !x.IsDeleted && (x.Sale != null && x.Sale > 0)
                        && (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText)))
                        && (userId != 0 ? (x.UserId != userId) : true)).Select(s => new Product
                        {
                            Id = s.Id,
                            Name = s.Name,
                            Price = s.Price,
                            FileId = s.FileId,
                            UserId = s.UserId,
                            IsDeleted = s.IsDeleted,
                            Category = s.Category,
                            CategoryId = s.CategoryId,
                            Brand = s.Brand,
                            Description = s.Description,
                            DiscountedPrice = s.DiscountedPrice,
                            Sale = s.Sale,
                            Rating = s.Rating,
                            IsMostRating = s.Rating != null ? !_dbContext.Products.Any(x => x.Rating > s.Rating) : false,
                            CommentsCount = _dbContext.Comments.Where(x => x.ProductId == s.Id).Count()
                        }).OrderByDescending(o => o.Sale);

                        var pagination = PagedList<Product>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);
                        pagination.ForEach(x => x.Stock = _dbContext.Stocks.Where(s => s.ProductId == x.Id && !x.IsDeleted).Select(s => s.Stock).FirstOrDefault());
                        pagination.ForEach(x => x.FileResult = GetFileResult(x.FileId, token).Result);

                        result.SetData(new PagingResult<PagedList<Product>>()
                        {
                            Items = pagination,
                            TotalCount = pagination.TotalCount,
                        });

                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else if (categoryId == 7 || categoryId == 8 || categoryId == 9)
                    {
                        if (_dbContext.Comments.Any(x => x.UserId == userId))
                        {
                            var idList = RunScript(userId, categoryId == 7 ? "product-suggestion-vendor" : (categoryId == 8 ? "product-suggestion-quality" : "product-suggestion-delivery"));

                            var queryable = _dbContext.Products.Include(x => x.Category).Where(x => !x.IsDeleted && idList.Contains(x.Id)
                            && (userId != 0 ? (x.UserId != userId) : true)
                            && (String.IsNullOrEmpty(lowerFilterText) || (x.Name.ToLower().Contains(lowerFilterText)))).Select(s => new Product
                            {
                                Id = s.Id,
                                Name = s.Name,
                                Price = s.Price,
                                FileId = s.FileId,
                                UserId = s.UserId,
                                IsDeleted = s.IsDeleted,
                                Category = s.Category,
                                CategoryId = s.CategoryId,
                                Brand = s.Brand,
                                Description = s.Description,
                                DiscountedPrice = s.DiscountedPrice,
                                Sale = s.Sale,
                                Rating = s.Rating,
                                IsMostRating = s.Rating != null ? !_dbContext.Products.Any(x => x.Rating > s.Rating) : false,
                                CommentsCount = _dbContext.Comments.Where(x => x.ProductId == s.Id).Count()
                            }).OrderByDescending(o => o.Sale);

                            var pagination = PagedList<Product>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);
                            pagination.ForEach(x => x.Stock = _dbContext.Stocks.Where(s => s.ProductId == x.Id && !x.IsDeleted).Select(s => s.Stock).FirstOrDefault());
                            pagination.ForEach(x => x.FileResult = GetFileResult(x.FileId, token).Result);

                            result.SetData(new PagingResult<PagedList<Product>>()
                            {
                                Items = pagination,
                                TotalCount = pagination.TotalCount,
                            });

                            result.SetMessage("İşlem başarı ile gerçekleşti.");
                        }
                    }
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<Product>> Save(Product product)
        {
            var result = new Result<Product>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    if (!_dbContext.Products.Where(x => (x.Name == product.Name) && !x.IsDeleted).Any())
                    {
                        _dbContext.Products.Add(product);
                        await _dbContext.SaveChangesAsync();

                        ProductStock stock = new ProductStock();
                        stock.ProductId = product.Id;
                        stock.IsDeleted = false;
                        stock.Stock = product.Stock;
                        _dbContext.Stocks.Add(stock);

                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(product);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Aynı isim veya kodla tanımlı bir yetki bulunmaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<Product>> Update(Product product)
        {
            var result = new Result<Product>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldProduct = await _dbContext.Products.Where(x => x.Id == product.Id && !x.IsDeleted).FirstOrDefaultAsync();

                    if (oldProduct != null)
                    {
                        if (!_dbContext.Products.Where(x => x.Id != oldProduct.Id && (x.Name == product.Name) && !x.IsDeleted).Any())
                        {
                            oldProduct.Name = product.Name;
                            oldProduct.FileId = product.FileId;
                            oldProduct.Price = product.Price;
                            oldProduct.Brand = product.Brand;
                            oldProduct.Rating = product.Rating;
                            oldProduct.Sale = product.Sale;
                            oldProduct.DiscountedPrice = product.DiscountedPrice;
                            oldProduct.CategoryId = product.CategoryId;
                            oldProduct.Description = product.Description;

                            var stockRecord = await _dbContext.Stocks.Where(x => x.ProductId == oldProduct.Id).FirstOrDefaultAsync();
                            stockRecord.Stock = product.Stock;

                            await _dbContext.SaveChangesAsync();
                            transaction.Commit();

                            result.SetData(product);
                            result.SetMessage("İşlem başarı ile gerçekleşti.");
                        }
                        else
                        {
                            result.SetIsSuccess(false);
                            result.SetMessage("Aynı isim veya kodla tanımlı bir yetki bulunmaktadır.");
                        }
                    }
                    else
                    {
                        result.SetIsSuccess(false);
                        result.SetMessage("Böyle bir kayıt bulunmamaktadır.");
                    }
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<PagingResult<PagedList<ProductComment>>>> CommentPaginate(PagingParameter pagingParameter, string token, long productId)
        {
            var result = new Result<PagingResult<PagedList<ProductComment>>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var queryable = _dbContext.Comments.Include(x => x.Product)
                                        .Where(x => x.ProductId == productId && (!string.IsNullOrEmpty(x.Comment) && !string.IsNullOrWhiteSpace(x.Comment)))
                                        .OrderByDescending(o => o.Product.Rating);

                    var pagination = PagedList<ProductComment>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);
                    pagination.ForEach(x => x.UserName = GetUserName(x.UserId, token).Result);
                    pagination.ForEach(x => x.Product.FileResult = GetFileResult(x.Product.FileId, token).Result);
                    pagination.ForEach(x => x.Product.Stock = _dbContext.Stocks.Where(s => s.ProductId == x.ProductId).Select(s => s.Stock).FirstOrDefault());
                    pagination.ForEach(x => x.Product.CommentsCount = _dbContext.Comments.Where(x => x.ProductId == productId).Count());

                    result.SetData(new PagingResult<PagedList<ProductComment>>()
                    {
                        Items = pagination,
                        TotalCount = pagination.TotalCount,
                    });

                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }
        public async Task<Result<ProductComment>> AddComment(ProductComment productComment)
        {
            var result = new Result<ProductComment>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    productComment.Date = DateTime.UtcNow;
                    _dbContext.Comments.Add(productComment);
                    await _dbContext.SaveChangesAsync();

                    var productComments = await _dbContext.Comments.Where(x => x.ProductId == productComment.ProductId).ToListAsync();

                    double totalAverageRating = 0;
                    double averageRating = 0;
                    foreach(var comments in productComments)
                    {
                        totalAverageRating += (double)((comments.VendorRating + comments.DeliveryRating + comments.QualityRating) / 3.0);
                    }

                    averageRating = (double) (totalAverageRating / productComments.Count);
                    var product = await _dbContext.Products.Where(x => x.Id == productComment.ProductId).FirstOrDefaultAsync();
                    product.Rating = averageRating;
                    await _dbContext.SaveChangesAsync();

                    transaction.Commit();

                    result.SetData(productComment);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        private async Task<string> GetUserName(long id, string token)
        {
            HttpClient client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

            var response = await client.GetAsync(_configuration["AppSettings:ApiUrl"] + "/api/User/" + id);

            if (response.IsSuccessStatusCode)
            {
                var responseStr = await response.Content.ReadAsStringAsync();

                if (!string.IsNullOrEmpty(responseStr))
                {
                    try
                    {
                        Result<User> result = JsonConvert.DeserializeObject<Result<User>>(responseStr);
                        string userName = result.GetData().Name + " " + result.GetData().Surname;

                        return userName;
                    }
                    catch (Exception ex)
                    {
                        return "";
                    }

                }
                else
                {
                    return "";
                }
            }
            else
            {
                return "";
            }
        }

        private async Task<FileContentResult> GetFileResult(long id, string token)
        {
            HttpClient client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

            var response = await client.GetAsync(_configuration["AppSettings:ApiUrl"] + "/api/File/" + id);

            if (response.IsSuccessStatusCode)
            {
                var responseStr = await response.Content.ReadAsStringAsync();

                if (!string.IsNullOrEmpty(responseStr))
                {
                    try
                    {
                        Result<Model.File> result = JsonConvert.DeserializeObject<Result<Model.File>>(responseStr);

                        if (result != null)
                        {
                            byte[] bytes = System.IO.File.ReadAllBytes(result.GetData().Path);
                            return new FileContentResult(bytes, result.GetData().ContentType);
                        }
                        else
                        {
                            return null;
                        }
                    }
                    catch (Exception ex)
                    {
                        return null;
                    }

                }
                else
                {
                    return null;
                }
            }
            else
            {
                return null;
            }

            return null;
        }

        public async Task<Result<List<CSVProductModel>>> GetProductsCSVFormat()
        {
            var result = new Result<List<CSVProductModel>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Products.Include(x => x.Category).Where(x => !x.IsDeleted)
                                                .Select(s => new CSVProductModel
                                                {
                                                    ProductId = s.Id,
                                                    Category = s.Category.Name,
                                                    Name = s.Name
                                                }).ToListAsync();

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<List<CSVRatingModel>>> GetDeliveryRatingsCSVFormat()
        {
            var result = new Result<List<CSVRatingModel>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Comments
                                                .Where(x => x.DeliveryRating >= 4)
                                                .Select(s => new CSVRatingModel
                                                {
                                                    ProductId = s.ProductId,
                                                    UserId = s.UserId,
                                                    Rating = s.DeliveryRating
                                                }).ToListAsync();

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }


        public async Task<Result<List<CSVRatingModel>>> GetVendorRatingsCSVFormat()
        {
            var result = new Result<List<CSVRatingModel>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Comments
                                                .Where(x => x.VendorRating >= 4)
                                                .Select(s => new CSVRatingModel
                                                {
                                                    ProductId = s.ProductId,
                                                    UserId = s.UserId,
                                                    Rating = s.VendorRating
                                                }).ToListAsync();

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        public async Task<Result<List<CSVRatingModel>>> GetQualityRatingsCSVFormat()
        {
            var result = new Result<List<CSVRatingModel>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Comments
                                                .Where(x => x.QualityRating >= 4)
                                                .Select(s => new CSVRatingModel
                                                {
                                                    ProductId = s.ProductId,
                                                    UserId = s.UserId,
                                                    Rating = s.QualityRating
                                                }).ToListAsync();

                    result.SetData(data);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");
                }
                catch (Exception ex)
                {
                    result.SetIsSuccess(false);
                    result.SetMessage(ex.Message);
                }
            }

            return result;
        }

        private long[] RunScript(long userId, string scriptName)
        {
            PythonEngine.Initialize();

            try
            {
                using (Py.GIL()) // Acquire the Python GIL
                {
                    dynamic script = Py.Import(scriptName); // Import the Python script (must be in PYTHONPATH)
                    dynamic result = script.run(userId); // Get the method from the script

                    long[] idList = result;
                    return idList; // Convert the result to string
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(ex.Message);
            }
            finally
            {
                PythonEngine.Shutdown();
            }

            return Array.Empty<long>();
        }
    }
}
