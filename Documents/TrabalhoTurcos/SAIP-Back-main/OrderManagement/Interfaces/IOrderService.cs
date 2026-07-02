using OrderManagement.Entity;
using OrderManagement.Model;

namespace OrderManagement.Interfaces
{
    public interface IOrderService
    {
        Task<Result<PagingResult<PagedList<Order>>>> Paginate(PagingParameter pagingParameter, long userId);
        Task<Result<PagingResult<PagedList<OrderProduct>>>> ComingPaginate(PagingParameter pagingParameter, long userId, string token);
        Task<Result<List<Order>>> GetOrderList(long userId);
        Task<Result<Order>> Save(Order product, string token);
        Task<Result<OrderProduct>> UpdateStatus(OrderProduct orderProduct);
        Task<Result<Order>> GetById(long id, string token);
        Task<Result<OrderProduct>> GetComingOrderById(long id, string token);
        Task<Result<OrderProduct>> AddInvoice(OrderProduct orderProduct, string token);
        Task<Result<OrderProduct>> DeleteInvoice(long id, string token);


    }
}
