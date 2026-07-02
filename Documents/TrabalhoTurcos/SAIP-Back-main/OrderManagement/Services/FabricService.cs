using OrderManagement.Interfaces;
using Newtonsoft.Json;
using OrderManagement.Model.Fabric;

namespace OrderManagement.Services
{
    public class FabricService : IFabricService
    {
        private readonly IConfiguration _configuration;

        public FabricService(IConfiguration configuration)
        {
            _configuration = configuration;
        }

        public async Task InvokeCreateOrder(Order order)
        {
            var formData = new List<KeyValuePair<string, string>>
            {
                new KeyValuePair<string, string>("channelid", _configuration["AppSettings:FabricChannelId"]),
                new KeyValuePair<string, string>("chaincodeid", _configuration["AppSettings:FabricChainCodeId"]),
                new KeyValuePair<string, string>("function", "CreateOrder"),
                new KeyValuePair<string, string>("args", JsonConvert.SerializeObject(order))
            };

            HttpContent content = new FormUrlEncodedContent(formData);
            HttpClient client = new HttpClient();

            try
            {
                HttpResponseMessage response = await client.PostAsync(_configuration["AppSettings:FabricApiUrl"] + "/invoke", content);

            }
            catch (HttpRequestException e)
            {
                Console.WriteLine("Error: " + e.Message);
            }
        }

        public async Task InvokeUpdateOrderStatus(long orderId, string orderStatus, long orderProductId, string status, string proccessDate, string? trackingNo)
        {
            var formData = new List<KeyValuePair<string, string>>
            {
                new KeyValuePair<string, string>("channelid", _configuration["AppSettings:FabricChannelId"]),
                new KeyValuePair<string, string>("chaincodeid", _configuration["AppSettings:FabricChainCodeId"]),
                new KeyValuePair<string, string>("function", "UpdateOrderStatus"),
                new KeyValuePair<string, string>("args", orderId.ToString()),
                new KeyValuePair<string, string>("args", orderStatus),
                new KeyValuePair<string, string>("args", orderProductId.ToString()),
                new KeyValuePair<string, string>("args", status),
                new KeyValuePair<string, string>("args", proccessDate),
                new KeyValuePair<string, string>("args", trackingNo),            };

            HttpContent content = new FormUrlEncodedContent(formData);
            HttpClient client = new HttpClient();

            try
            {
                HttpResponseMessage response = await client.PostAsync(_configuration["AppSettings:FabricApiUrl"] + "/invoke", content);

            }
            catch (HttpRequestException e)
            {
                Console.WriteLine("Error: " + e.Message);
            }
        }
    }
}
