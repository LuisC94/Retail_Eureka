namespace OrderManagement.Model.Fabric
{
    public class OrderProduct
    {
        public string id { get; set; }
        public Product product {  get; set; }
        public string status { get; set; }
        public string proccessDate { get; set; }
    }
}
