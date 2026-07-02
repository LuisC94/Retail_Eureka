namespace OrderManagement.Model.Fabric
{
    public class Order
    {
        public string id { get; set; }
        public string orderNo { get; set; }
        public string orderDate  { get; set; }
        public string orderStatus { get; set; }
        public string customerId { get; set; }
        public string customerNameSurname { get; set; }
        public List<OrderProduct> orderProducts { get; set; }
    }
}
