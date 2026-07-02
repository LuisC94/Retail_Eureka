using System.Collections.Concurrent;
using System.Text;
using System.Net.WebSockets;

namespace OrderManagement.Handler
{
    public class WebSocketHandler
    {
        private static readonly ConcurrentDictionary<long, WebSocket> _sockets = new ConcurrentDictionary<long, WebSocket>();

        public async Task HandleWebSocketAsync(WebSocket webSocket, long userId)
        {
            _sockets.TryAdd(userId, webSocket);

            var buffer = new byte[1024 * 4];
            var result = await webSocket.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);

            while (!result.CloseStatus.HasValue)
            {
                var message = Encoding.UTF8.GetString(buffer, 0, result.Count);
                // Echo the message back
                await SendMessageAsync(userId, message);

                result = await webSocket.ReceiveAsync(new ArraySegment<byte>(buffer), CancellationToken.None);
            }

            _sockets.TryRemove(userId, out _);
            await webSocket.CloseAsync(result.CloseStatus.Value, result.CloseStatusDescription, CancellationToken.None);
        }

        public async Task SendMessageAsync(long userId, string message)
        {
            if (_sockets.TryGetValue(userId, out var webSocket))
            {
                var buffer = Encoding.UTF8.GetBytes(message);
                await webSocket.SendAsync(new ArraySegment<byte>(buffer), WebSocketMessageType.Text, true, CancellationToken.None);
            }
        }
    }
}
