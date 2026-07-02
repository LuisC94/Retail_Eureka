using Newtonsoft.Json;
using System.Text.Json.Serialization;

namespace UserManagement.Model
{
    public class Result<T>
    {
        [JsonInclude]
        [JsonProperty("Message")]

        private string? Message { get; set; }

        [JsonInclude]
        [JsonProperty("IsSuccess")]

        private bool? IsSuccess { get; set; } = true;

        [JsonInclude]
        [JsonProperty("Data")]

        private T? Data { get; set; }

        public void SetMessage(string message)
        {
            Message = message;
        }

        public string? GetMessage()
        {
            return Message;
        }

        public void SetIsSuccess(bool isSuccess = true) 
        {  
            IsSuccess = isSuccess; 
        }

        public bool? GetIsSuccess()
        {
            return IsSuccess;
        }

        public void SetData(T data)
        {
            Data = data;
        }

        public T? GetData()
        {
            return Data;
        }
    }
}
