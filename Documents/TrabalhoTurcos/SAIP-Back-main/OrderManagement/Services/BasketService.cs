using Microsoft.EntityFrameworkCore;
using System.Data;
using OrderManagement.Interfaces;
using OrderManagement.DbContexts;
using OrderManagement.Model;
using OrderManagement.Entity;
using Microsoft.AspNetCore.Mvc;
using Newtonsoft.Json;
using System.Net.Http.Headers;

namespace OrderManagement.Services
{
    public class BasketService : IBasketService
    {
        private readonly OrderManagementContext _dbContext;

        private readonly IConfiguration _configuration;

        public BasketService(OrderManagementContext dbContext, IConfiguration configuration)
        {
            _dbContext = dbContext;
            _configuration = configuration;
        }

        public async Task<Result<Basket>> DeleteAll(long id, long productId)
        {
            var result = new Result<Basket>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldBasket = await _dbContext.Baskets.Where(x => x.Id == id && x.IsActive && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldBasket != null)
                    {
                        var oldBasketProducts = await _dbContext.BasketProducts.Where(x => x.BasketId == oldBasket.Id && x.IsActive && !x.IsDeleted).ToListAsync();
                        var toBeDeletedlİST = oldBasketProducts.Where(x => x.ProductId == productId).ToList();
                        toBeDeletedlİST.ForEach(x => x.IsDeleted = true);
                        toBeDeletedlİST.ForEach(x => x.IsActive = false);

                        if (oldBasketProducts.Count == toBeDeletedlİST.Count)
                        {
                            oldBasket.IsDeleted = true;
                            oldBasket.IsActive = false;
                        }

                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldBasket);
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

        public async Task<Result<Basket>> Delete(long id, long productId)
        {
            var result = new Result<Basket>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var oldBasket = await _dbContext.Baskets.Where(x => x.Id == id && x.IsActive && !x.IsDeleted).FirstOrDefaultAsync();
                    if (oldBasket != null)
                    {
                        var oldBasketProducts = await _dbContext.BasketProducts.Where(x => x.BasketId == oldBasket.Id && x.IsActive && !x.IsDeleted).ToListAsync();
                        var toBeDeleted = oldBasketProducts.Where(x => x.ProductId == productId).FirstOrDefault();
                        toBeDeleted.IsDeleted = true;
                        toBeDeleted.IsActive = false;

                        if (oldBasketProducts.Count == 1)
                        {
                            oldBasket.IsDeleted = true;
                            oldBasket.IsActive = false;
                        }

                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(oldBasket);
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

        public async Task<Result<List<Basket>>> GetBasketList(long userId, string token)
        {
            var result = new Result<List<Basket>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var basket = await _dbContext.Baskets.Where(x => x.UserId == userId && x.IsActive && !x.IsDeleted).FirstOrDefaultAsync();
                    if (basket != null)
                    {
                        var productIdList = await _dbContext.BasketProducts.Where(x => x.BasketId == basket.Id && x.IsActive && !x.IsDeleted).Select(s => s.ProductId).ToListAsync();

                        var basketList = new List<Basket>();
                        foreach (var productId in productIdList)
                        {
                            Basket item = new Basket();
                            item.Id = basket.Id;
                            item.UserId = basket.UserId;
                            item.ProductId = productId;
                            item.IsDeleted = false;
                            item.IsActive = true;
                            item.Product = await GetProduct(productId, token);
                            basketList.Add(item);
                        }

                        result.SetData(basketList);
                    }
                    else
                    {
                        result.SetData(null);
                    }

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

        public async Task<Result<Basket>> Save(Basket newBasket)
        {
            var result = new Result<Basket>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var basket = await _dbContext.Baskets.Where(x => x.UserId == newBasket.UserId && x.IsActive && !x.IsDeleted).FirstOrDefaultAsync();

                    if (basket == null)
                    {
                        basket = new Basket();
                        basket.UserId = newBasket.UserId;
                        basket.IsDeleted = false;
                        basket.IsActive = true;
                        _dbContext.Baskets.Add(basket);
                        await _dbContext.SaveChangesAsync();
                    }

                    BasketProduct basketProduct = new BasketProduct();
                    basketProduct.ProductId = newBasket.ProductId;
                    basketProduct.BasketId = basket.Id;
                    basketProduct.IsDeleted = false;
                    basketProduct.IsActive = true;
                    _dbContext.BasketProducts.Add(basketProduct);

                    await _dbContext.SaveChangesAsync();
                    transaction.Commit();

                    result.SetData(newBasket);
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

        public async Task<Result<List<Basket>>> SaveAll(List<Basket> basketList)
        {
            var result = new Result<List<Basket>> ();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var userId = basketList.First().UserId;
                    var basket = await _dbContext.Baskets.Where(x => x.UserId == userId && x.IsActive && !x.IsDeleted).FirstOrDefaultAsync();

                    if(basket == null)
                    {
                        basket = new Basket();
                        basket.UserId = userId;
                        basket.IsDeleted = false;
                        basket.IsActive = true;
                        _dbContext.Baskets.Add(basket);
                        await _dbContext.SaveChangesAsync();
                    }

                    foreach (var item in basketList)
                    {
                        BasketProduct basketProduct = new BasketProduct();
                        basketProduct.ProductId = item.ProductId;
                        basketProduct.BasketId = basket.Id;
                        basketProduct.IsDeleted = false;
                        basketProduct.IsActive = true;
                        _dbContext.BasketProducts.Add(basketProduct);

                        await _dbContext.SaveChangesAsync();
                    }

                    transaction.Commit();

                    result.SetData(basketList);
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

        public async Task<Result<List<Basket>>> GetOrderBasketList(long id, string token)
        {
            var result = new Result<List<Basket>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var basket = await _dbContext.Baskets.Where(x => x.Id == id && !x.IsDeleted).FirstOrDefaultAsync();
                    if (basket != null)
                    {
                        var productIdList = await _dbContext.BasketProducts.Where(x => x.BasketId == basket.Id && !x.IsDeleted).Select(s => s.ProductId).ToListAsync();

                        var basketList = new List<Basket>();
                        foreach (var productId in productIdList)
                        {
                            Basket item = new Basket();
                            item.Id = basket.Id;
                            item.UserId = basket.UserId;
                            item.ProductId = productId;
                            item.IsDeleted = false;
                            item.IsActive = false;
                            item.Product = await GetProduct(productId, token);
                            basketList.Add(item);
                        }

                        result.SetData(basketList);
                    }
                    else
                    {
                        result.SetData(null);
                    }

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

        private async Task<Product> GetProduct(long id, string token)
        {
            HttpClient client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

            var response = await client.GetAsync(_configuration["AppSettings:ApiUrl"] + "/api/Product/GetByIdForBasket/" + id);

            if (response.IsSuccessStatusCode)
            {
                var responseStr = await response.Content.ReadAsStringAsync();

                if (!string.IsNullOrEmpty(responseStr))
                {
                    try
                    {
                        Result<Model.Product> result = JsonConvert.DeserializeObject<Result<Model.Product>>(responseStr);

                        if (result.GetIsSuccess().Value)
                        {
                            var product = result.GetData();  
                            product.FileResult = GetFileResult(product.FileId, token).Result;

                            return product;
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
    }
}
