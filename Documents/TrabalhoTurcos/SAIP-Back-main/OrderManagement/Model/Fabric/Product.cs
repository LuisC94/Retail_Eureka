using Microsoft.AspNetCore.Mvc;
using System.ComponentModel.DataAnnotations.Schema;

namespace OrderManagement.Model.Fabric
{
    public class Product
    {
        public string id { get; set; }
        public string name { get; set; }
        public string price  { get; set; }
        public string ownerUserId { get; set; }
        public string ownerNameSurname { get; set; }

    }
}
