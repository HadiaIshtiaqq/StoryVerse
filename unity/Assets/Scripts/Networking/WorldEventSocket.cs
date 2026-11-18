// Live world events from the backend WebSocket (balances, letters, chronicle, turns).
// Photon Fusion carries hands/avatars; this socket carries committed game results.
using System;
using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Storyverse.Networking
{
    public class WorldEventSocket : MonoBehaviour
    {
        /// <summary>(eventType, payload). Raised on the Unity main thread.</summary>
        public event Action<string, JObject> OnEvent;

        readonly ConcurrentQueue<JObject> _inbox = new();
        ClientWebSocket _socket;
        CancellationTokenSource _cts;
        string _worldId;

        public void Connect(string worldId)
        {
            _worldId = worldId;
            Disconnect();
            _cts = new CancellationTokenSource();
            _ = RunAsync(_cts.Token);
        }

        public void Disconnect()
        {
            _cts?.Cancel();
            _socket?.Dispose();
            _socket = null;
        }

        async Task RunAsync(CancellationToken ct)
        {
            var api = ApiClient.Instance;
            while (!ct.IsCancellationRequested)
            {
                // Rebuilt every attempt: LAN discovery may have moved the server since the last connection.
                var url = api.BaseUrl.Replace("https://", "wss://").Replace("http://", "ws://") +
                          $"/ws/worlds/{_worldId}?token={Uri.EscapeDataString(api.Token)}";
                try
                {
                    _socket?.Dispose();               // never leak the previous connection on reconnect
                    _socket = new ClientWebSocket();
                    _socket.Options.KeepAliveInterval = TimeSpan.FromSeconds(20);   // detects dead Wi-Fi links
                    await _socket.ConnectAsync(new Uri(url), ct);
                    var buffer = new byte[64 * 1024];
                    var sb = new StringBuilder();
                    while (_socket.State == WebSocketState.Open && !ct.IsCancellationRequested)
                    {
                        var result = await _socket.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
                        if (result.MessageType == WebSocketMessageType.Close) break;
                        sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                        if (!result.EndOfMessage) continue;
                        try { _inbox.Enqueue(JObject.Parse(sb.ToString())); }
                        catch (Newtonsoft.Json.JsonException e) { Debug.LogWarning($"[WorldEventSocket] skipped bad frame: {e.Message}"); }
                        sb.Clear();
                    }
                }
                catch (OperationCanceledException) { return; }
                catch (Exception e)
                {
                    Debug.LogWarning($"[WorldEventSocket] {e.Message}; reconnecting");
                    await api.Discover();             // no-op unless the server answers from a new address
                }
                try { await Task.Delay(2000, ct); } catch (OperationCanceledException) { return; }
            }
        }

        void Update()
        {
            while (_inbox.TryDequeue(out var evt))
                OnEvent?.Invoke((string)evt["type"], evt);
        }

        void OnDestroy() => Disconnect();
    }
}
