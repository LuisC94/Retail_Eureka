using Microsoft.EntityFrameworkCore;
using System.Data;
using OrderManagement.Interfaces;
using OrderManagement.DbContexts;
using OrderManagement.Model;
using OrderManagement.Entity;
using Microsoft.AspNetCore.Mvc;
using Newtonsoft.Json;
using System.Net.Http.Headers;
using OrderManagement.Enums;
using System.Text;
using OrderManagement.Handler;

namespace OrderManagement.Services
{
    public class OrderService : IOrderService
    {
        private readonly OrderManagementContext _dbContext;

        private readonly IConfiguration _configuration;

        private readonly WebSocketHandler _webSocketHandler;

        private readonly IFabricService _fabricService;

        public OrderService(OrderManagementContext dbContext, IConfiguration configuration, WebSocketHandler webSocketHandler, IFabricService fabricService)
        {
            _dbContext = dbContext;
            _configuration = configuration;
            _webSocketHandler = webSocketHandler;
            _fabricService = fabricService;
        }

        public async Task<Result<PagingResult<PagedList<Order>>>> Paginate(PagingParameter pagingParameter, long userId)
        {
            var result = new Result<PagingResult<PagedList<Order>>>();

            string lowerFilterText = string.IsNullOrEmpty(pagingParameter.FilterText) ? null : pagingParameter.FilterText.ToLower();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var queryable = _dbContext.Orders.Include(x => x.Basket).Where(x => x.UserId == userId
                    && (String.IsNullOrEmpty(lowerFilterText) || (x.OrderNo.ToLower().Contains(lowerFilterText))) ).Select(s => new Order
                    {
                        Id = s.Id,
                        Price = s.Price,
                        BasketId = s.BasketId,
                        Basket = s.Basket,
                        UserId = s.UserId,
                        OrderDate = s.OrderDate,
                        OrderNo = s.OrderNo,
                        OrderStatus = s.OrderStatus
                    });

                    var pagination = PagedList<Order>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);

                    result.SetData(new PagingResult<PagedList<Order>>()
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

        public async Task<Result<PagingResult<PagedList<OrderProduct>>>> ComingPaginate(PagingParameter pagingParameter, long userId, string token)
        {
            var result = new Result<PagingResult<PagedList<OrderProduct>>>();

            string lowerFilterText = string.IsNullOrEmpty(pagingParameter.FilterText) ? null : pagingParameter.FilterText.ToLower();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var queryable = _dbContext.OrderProducts.Include(x => x.Order).Where(x => x.VendorId == userId
                    && (String.IsNullOrEmpty(lowerFilterText) || (x.Order.OrderNo.ToLower().Contains(lowerFilterText))) ).Select(s => new OrderProduct
                    {
                        Id = s.Id,
                        VendorId = s.VendorId,
                        ProccessDate = s.ProccessDate,
                        Order = s.Order,
                        OrderStatus = s.OrderStatus,
                        ProductId = s.ProductId
                    });

                    var pagination = PagedList<OrderProduct>.ToPagedList(queryable, pagingParameter.PageNumber, pagingParameter.PageSize);
                    pagination.ForEach(x => x.Product = GetProduct(x.ProductId, token).Result);
                    result.SetData(new PagingResult<PagedList<OrderProduct>>()
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

        public async Task<Result<List<Order>>> GetOrderList(long userId)
        {
            var result = new Result<List<Order>>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var data = await _dbContext.Orders.Where(x => x.UserId == userId).ToListAsync();

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

        public async Task<Result<OrderProduct>> UpdateStatus(OrderProduct orderProduct)
        {
            var result = new Result<OrderProduct>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var orderCompleted = false;

                    var item = await _dbContext.OrderProducts.Where(x => x.Id == orderProduct.Id).FirstOrDefaultAsync();

                    if(item != null)
                    {
                        if(orderProduct.OrderStatus == 3 || orderProduct.OrderStatus == 4)
                        {
                            if(orderProduct.OrderStatus == 3)
                            {
                                item.TrackingNo = orderProduct.TrackingNo;
                                item.TrackingDate = orderProduct.TrackingDate;
                                item.CompletionDate = orderProduct.CompletionDate;
                            }
                            else
                            {
                                item.CompletionDate = orderProduct.CompletionDate;
                            }

                            item.ProccessDate = orderProduct.ProccessDate;
                        }
                        else
                        {
                            item.ProccessDate = DateTime.UtcNow;
                        }

                        item.OrderStatus = orderProduct.OrderStatus;
                        await _dbContext.SaveChangesAsync();

                        if (item.OrderStatus == 4)
                        {
                            if(!(_dbContext.OrderProducts.Where(x => x.OrderId == orderProduct.OrderId && x.OrderStatus != (int)OrderStatus.TeslimEdildi).Any()))
                            {
                                orderCompleted = true;
                                var order = await _dbContext.Orders.Where(x => x.Id == orderProduct.OrderId).FirstOrDefaultAsync();
                                order.OrderStatus = (int)OrderStatus.SiparisTamamlandi;
                                await _dbContext.SaveChangesAsync();
                            }
                        }


                        transaction.Commit();

                        result.SetData(item);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");

                        if(item.OrderStatus == 4)
                        {
                            if (orderCompleted)
                            {
                                await _fabricService.InvokeUpdateOrderStatus(item.OrderId, nameof(OrderStatus.SiparisTamamlandi), item.Id, nameof(OrderStatus.TeslimEdildi), item.ProccessDate.AddHours(3).ToString(), item.TrackingNo);
                            }
                            else
                            {
                                await _fabricService.InvokeUpdateOrderStatus(item.OrderId, nameof(OrderStatus.SiparisTamamlanmadi), item.Id, nameof(OrderStatus.TeslimEdildi), item.ProccessDate.AddHours(3).ToString(), item.TrackingNo);
                            }
                        }
                        else if (item.OrderStatus == 3)
                        {
                            await _fabricService.InvokeUpdateOrderStatus(item.OrderId, nameof(OrderStatus.SiparisTamamlanmadi), item.Id, nameof(OrderStatus.Kargolandi), item.ProccessDate.AddHours(3).ToString(), item.TrackingNo);
                        }
                        else if (item.OrderStatus == 2)
                        {
                            await _fabricService.InvokeUpdateOrderStatus(item.OrderId, nameof(OrderStatus.SiparisTamamlanmadi), item.Id, nameof(OrderStatus.Hazirlaniyor), item.ProccessDate.AddHours(3).ToString(), string.Empty);
                        }
                        else if (item.OrderStatus == 1)
                        {
                            await _fabricService.InvokeUpdateOrderStatus(item.OrderId, nameof(OrderStatus.SiparisTamamlanmadi), item.Id, nameof(OrderStatus.Onaylandi), item.ProccessDate.AddHours(3).ToString(), string.Empty);
                        }
                    }

                }
                catch (Exception exception)
                {
                    transaction.Rollback();

                    result.SetIsSuccess(false);
                    result.SetMessage(exception.Message);
                }
            }

            return result;
        }
        public async Task<Result<Order>> Save(Order order, string token)
        {
            var result = new Result<Order>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    order.OrderDate = DateTime.UtcNow;
                    order.OrderStatus = (int)OrderStatus.SiparisTamamlanmadi;
                    _dbContext.Add(order);
                    await _dbContext.SaveChangesAsync();

                    order.OrderNo = "SAIP-ORDER-" + order.Id.ToString("0000000");
                    await _dbContext.SaveChangesAsync();

                    var basket = await _dbContext.Baskets.Where(x => x.Id == order.BasketId && x.IsActive && !x.IsDeleted).FirstOrDefaultAsync();
                    basket.IsActive = false;

                    var basketProducts = await _dbContext.BasketProducts.Where(x => x.BasketId == order.BasketId && x.IsActive && !x.IsDeleted).ToListAsync();
                    basketProducts.ForEach(x => x.IsActive = false);
                    await _dbContext.SaveChangesAsync();

                    var fabricOrderProducts = new List<Model.Fabric.OrderProduct>();
                    var vendors = new List<long>();
                    foreach (var basketProduct in basketProducts)
                    {
                        OrderProduct orderProduct = new OrderProduct();
                        orderProduct.OrderId = order.Id;
                        orderProduct.ProductId = basketProduct.ProductId;
                        orderProduct.VendorId = (await GetProduct(basketProduct.ProductId, token)).UserId;
                        orderProduct.OrderStatus = (int)OrderStatus.OnayBekliyor;
                        orderProduct.ProccessDate = order.OrderDate.Value;
                        _dbContext.Add(orderProduct);
                        vendors.Add(orderProduct.VendorId);
                        await _dbContext.SaveChangesAsync();

                        var product = await GetProduct(basketProduct.ProductId, token);
                        Model.Fabric.OrderProduct fabricOrderProduct = new Model.Fabric.OrderProduct();
                        fabricOrderProduct.id = orderProduct.Id.ToString();
                        fabricOrderProduct.product = JsonConvert.DeserializeObject<Model.Fabric.Product>(JsonConvert.SerializeObject(product));
                        fabricOrderProduct.product.ownerUserId = product.UserId.ToString();
                        fabricOrderProduct.product.ownerNameSurname = product.UserName;
                        fabricOrderProduct.proccessDate = orderProduct.ProccessDate.AddHours(3).ToString(); 

                        if (orderProduct.OrderStatus == (int)OrderStatus.OnayBekliyor)
                        {
                            fabricOrderProduct.status = nameof(OrderStatus.OnayBekliyor);
                        }
                        else if (orderProduct.OrderStatus == (int)OrderStatus.Onaylandi)
                        {
                            fabricOrderProduct.status = nameof(OrderStatus.Onaylandi);
                        }
                        else if (orderProduct.OrderStatus == (int)OrderStatus.Hazirlaniyor)
                        {
                            fabricOrderProduct.status = nameof(OrderStatus.Hazirlaniyor);
                        }
                        else if (orderProduct.OrderStatus == (int)OrderStatus.Kargolandi)
                        {
                            fabricOrderProduct.status = nameof(OrderStatus.Kargolandi);
                        }
                        else if (orderProduct.OrderStatus == (int)OrderStatus.TeslimEdildi)
                        {
                            fabricOrderProduct.status = nameof(OrderStatus.TeslimEdildi);
                        }

                        fabricOrderProducts.Add(fabricOrderProduct); 
                    }

                    foreach (var vendorId in vendors.Distinct())
                    {
                        Notification notification = new Notification();
                        notification.Message = order.OrderNo + " numaralı yeni bir siparişiniz bulunmaktadır.";
                        notification.Link = "incomingordermanagement/" + order.Id;
                        notification.IsReaded = false;
                        notification.IsDeleted = false;
                        notification.UserId = vendorId;

                        await _webSocketHandler.SendMessageAsync(notification.UserId, notification.Message);
                        await SaveNotification(notification, token);
                    }

                    transaction.Commit();

                    result.SetData(order);
                    result.SetMessage("İşlem başarı ile gerçekleşti.");

                    Model.Fabric.Order fabricOrder = new Model.Fabric.Order();
                    fabricOrder.id = order.Id.ToString();
                    fabricOrder.orderDate = order.OrderDate.Value.AddHours(3).ToString();
                    fabricOrder.orderNo = order.OrderNo;
                    fabricOrder.customerId = order.UserId.ToString();
                    fabricOrder.customerNameSurname = await GetUserName(order.UserId, token);
                    fabricOrder.orderProducts = fabricOrderProducts;

                    if (order.OrderStatus == (int)OrderStatus.SiparisTamamlandi)
                    {
                        fabricOrder.orderStatus = nameof(OrderStatus.SiparisTamamlandi);
                    }
                    else if (order.OrderStatus == (int)OrderStatus.SiparisTamamlanmadi)
                    {
                        fabricOrder.orderStatus = nameof(OrderStatus.SiparisTamamlanmadi);
                    }
                    
                    await _fabricService.InvokeCreateOrder(fabricOrder);
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

        public async Task<Result<Order>> GetById(long id, string token)
        {
            var result = new Result<Order>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var order = await _dbContext.Orders.Include(x => x.Basket).Where(x => x.Id == id).FirstOrDefaultAsync();

                    order.OrderProducts = await _dbContext.OrderProducts
                                                    .Include(x => x.Order)
                                                    .Where(x => x.OrderId == id).ToListAsync();


                    foreach (var orderProduct in order.OrderProducts)
                    {
                        orderProduct.Product = GetProduct(orderProduct.ProductId, token).Result;

                        if(orderProduct.FileId.HasValue)
                        {
                            orderProduct.FileName = GetFile(orderProduct.FileId.Value, token).Result.Key;
                            orderProduct.FileResult = GetFile(orderProduct.FileId.Value, token).Result.Value;
                        }
                    }

                    result.SetData(order);
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

        public async Task<Result<OrderProduct>> GetComingOrderById(long id, string token)
        {
            var result = new Result<OrderProduct>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var orderProduct = await _dbContext.OrderProducts.Include(x => x.Order).Where(x => x.Id == id).FirstOrDefaultAsync();

                    orderProduct.Product = GetProduct(orderProduct.ProductId, token).Result;
                    orderProduct.Order.DeliveryAddress = await GetAddress(orderProduct.Order.DeliveryAddressId, token);
                    orderProduct.Order.InvoiceAddress = await GetAddress(orderProduct.Order.InvoiceAddressId, token);

                    if (orderProduct.FileId.HasValue)
                    {
                        orderProduct.FileName = GetFile(orderProduct.FileId.Value, token).Result.Key;
                        orderProduct.FileResult = GetFile(orderProduct.FileId.Value, token).Result.Value;
                    }

                    result.SetData(orderProduct);
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

        public async Task<Result<OrderProduct>> AddInvoice(OrderProduct orderProduct, string token)
        {
            var result = new Result<OrderProduct>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var item = await _dbContext.OrderProducts.Where(x => x.Id == orderProduct.Id).FirstOrDefaultAsync();

                    if (item != null)
                    {
                        if (item.FileId.HasValue)
                        {
                            var fileDeleteResult = DeleteFile(item.FileId.Value, token).Result;
                        }

                        item.FileId = orderProduct.FileId;

                        await _dbContext.SaveChangesAsync();
                        transaction.Commit();

                        result.SetData(item);
                        result.SetMessage("İşlem başarı ile gerçekleşti.");
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

        public async Task<Result<OrderProduct>> DeleteInvoice(long id, string token)
        {
            var result = new Result<OrderProduct>();

            using (var transaction = _dbContext.Database.BeginTransaction(IsolationLevel.ReadUncommitted))
            {
                try
                {
                    var item = await _dbContext.OrderProducts.Include(x => x.Order).Where(x => x.Id == id).FirstOrDefaultAsync();

                    if (item != null)
                    {
                        var fileDeleteResult = DeleteFile(item.FileId.Value, token).Result;

                        if (fileDeleteResult.Key)
                        {
                            item.FileId = null;
                            item.FileName = null;
                            item.FileResult = null;

                            await _dbContext.SaveChangesAsync();
                            transaction.Commit();

                            item.Product = GetProduct(item.ProductId, token).Result;
                            result.SetData(item);
                            result.SetMessage("İşlem başarı ile gerçekleşti.");
                        }
                        else
                        {
                            result.SetIsSuccess(false);
                            result.SetMessage(fileDeleteResult.Value);
                        }
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
                        Result<Product> result = JsonConvert.DeserializeObject<Result<Product>>(responseStr);

                        if (result.GetIsSuccess().Value)
                        {
                            var product = result.GetData();
                            product.FileResult = GetFile(product.FileId, token).Result.Value;

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

        private async Task<bool> SaveNotification(Notification notification, string token)
        {
            HttpClient client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
            var serializedNotification = JsonConvert.SerializeObject(notification);
            StringContent stringContent = new StringContent(serializedNotification, Encoding.UTF8, "application/json");

            var response = await client.PostAsync(_configuration["AppSettings:ApiUrl"] + "/api/Notification/Save", stringContent);

            if (response.IsSuccessStatusCode)
            {
                var responseStr = await response.Content.ReadAsStringAsync();

                if (!string.IsNullOrEmpty(responseStr))
                {
                    try
                    {
                        Result<Notification> result = JsonConvert.DeserializeObject<Result<Notification>>(responseStr);

                        if (result.GetIsSuccess().Value)
                        {
                            return result.GetIsSuccess().Value;
                        }
                        else
                        {
                            return false;
                        }
                    }
                    catch (Exception ex)
                    {
                        return false;
                    }

                }
                else
                {
                    return false;
                }
            }
            else
            {
                return false;
            }

            return false;
        }

        private async Task<KeyValuePair<bool, string?>> DeleteFile(long id, string token)
        {
            HttpClient client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

            var response = await client.DeleteAsync(_configuration["AppSettings:ApiUrl"] + "/api/File/Delete/" + id);

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
                            return new KeyValuePair<bool, string?>(result.GetIsSuccess().Value, result.GetMessage());
                        }
                        else
                        {
                            return new KeyValuePair<bool, string?>(false, null);
                        }
                    }
                    catch (Exception ex)
                    {
                        return new KeyValuePair<bool, string?>(false, null);
                    }

                }
                else
                {
                    return new KeyValuePair<bool, string?>(false, null);
                }
            }
            else
            {
                return new KeyValuePair<bool, string?>(false, null);
            }

            return new KeyValuePair<bool, string?>(false, null);
        }

        private async Task<KeyValuePair<string, FileContentResult>> GetFile(long id, string token)
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
                            return new KeyValuePair<string, FileContentResult>(result.GetData().Name, new FileContentResult(bytes, result.GetData().ContentType));
                        }
                        else
                        {
                            return new KeyValuePair<string, FileContentResult>(null, null);
                        }
                    }
                    catch (Exception ex)
                    {
                        return new KeyValuePair<string, FileContentResult>(null, null);
                    }

                }
                else
                {
                    return new KeyValuePair<string, FileContentResult>(null, null);
                }
            }
            else
            {
                return new KeyValuePair<string, FileContentResult>(null, null);
            }

            return new KeyValuePair<string, FileContentResult>(null, null);
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

        private async Task<UserAddress> GetAddress(long id, string token)
        {
            HttpClient client = new HttpClient();
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

            var response = await client.GetAsync(_configuration["AppSettings:ApiUrl"] + "/api/User/UserAddressById/" + id);

            if (response.IsSuccessStatusCode)
            {
                var responseStr = await response.Content.ReadAsStringAsync();

                if (!string.IsNullOrEmpty(responseStr))
                {
                    try
                    {
                        Result<UserAddress> result = JsonConvert.DeserializeObject<Result<UserAddress>>(responseStr);

                        return result.GetData();
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
        }
    }
}
