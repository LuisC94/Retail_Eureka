using OrderManagement.Model.Fabric;

namespace OrderManagement.Interfaces
{
    public interface IFabricService
    {

        Task InvokeCreateOrder(Order order);
        Task InvokeUpdateOrderStatus(long orderId, string orderStatus, long orderProductId, string status, string proccessDate, string? trackingNo);
    }
}
