using OrderManagement.Entity;
using OrderManagement.Model;

namespace OrderManagement.Interfaces
{
    public interface IBasketService
    {

        Task<Result<List<Basket>>> GetBasketList(long userId, string token);
        Task<Result<Basket>> Save(Basket product);

        Task<Result<List<Basket>>> SaveAll(List<Basket> basketList);
        Task<Result<Basket>> Delete(long id, long productId);

        Task<Result<Basket>> DeleteAll(long id, long productId);

        Task<Result<List<Basket>>> GetOrderBasketList(long id, string token);
    }
}
