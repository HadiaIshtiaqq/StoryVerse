// HTTP client for the authoritative FastAPI backend.
// Rule (spec §3.3): the client sends *intents* and renders *results*. It never edits balances itself.
// Requires: com.unity.nuget.newtonsoft-json
using System;
using System.Text;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Newtonsoft.Json.Serialization;
using Storyverse.Data;
using UnityEngine;
using UnityEngine.Networking;

namespace Storyverse.Networking
{
    public class GameApiException : Exception
    {
        public readonly long Status; public readonly string Code;
        public GameApiException(long status, string code, string message) : base(message) { Status = status; Code = code; }
    }

    public static class UnityWebRequestExtensions
    {
        public static Task<UnityWebRequest> SendAsync(this UnityWebRequest request)
        {
            var tcs = new TaskCompletionSource<UnityWebRequest>();
            request.SendWebRequest().completed += _ => tcs.TrySetResult(request);
            return tcs.Task;
        }
    }

    public class ApiClient
    {
        public static readonly JsonSerializerSettings Json = new()
        {
            ContractResolver = new DefaultContractResolver { NamingStrategy = new SnakeCaseNamingStrategy() },
            NullValueHandling = NullValueHandling.Ignore,
        };
        public static readonly JsonSerializer Serializer = JsonSerializer.Create(Json);

        static ApiClient _instance;
        public static ApiClient Instance => _instance ??= new ApiClient(UnityEngine.Resources.Load<ApiSettings>("ApiSettings"));

        readonly ApiSettings _settings;
        public string Token { get; private set; }
        /// <summary>The server found by LAN discovery wins over the address baked into ApiSettings (laptop IPs change).</summary>
        public string BaseUrl
        {
            get
            {
                var found = PlayerPrefs.GetString("sv_discovered_url", "");
                if (found != "") return found;
                return _settings != null ? _settings.BaseUrl.TrimEnd('/') : "http://localhost:8000";
            }
        }

        bool _discovering;

        /// <summary>Broadcast "STORYVERSE?" on the LAN (UDP 47800) and adopt the server that answers.</summary>
        public async Task<bool> Discover(float seconds = 2f)
        {
            if (_discovering) return false;
            _discovering = true;
            try
            {
                using var udp = new System.Net.Sockets.UdpClient { EnableBroadcast = true };
                var question = Encoding.ASCII.GetBytes("STORYVERSE?");
                await udp.SendAsync(question, question.Length, new System.Net.IPEndPoint(System.Net.IPAddress.Broadcast, 47800));
                var receive = udp.ReceiveAsync();
                if (await Task.WhenAny(receive, Task.Delay(TimeSpan.FromSeconds(seconds))) != receive) return false;
                var reply = Encoding.ASCII.GetString(receive.Result.Buffer).Trim();
                if (!reply.StartsWith("STORYVERSE http")) return false;
                var url = reply.Substring("STORYVERSE ".Length).TrimEnd('/');
                if (url == BaseUrl) return false;               // same address: discovery can't help
                PlayerPrefs.SetString("sv_discovered_url", url); PlayerPrefs.Save();
                Debug.Log($"[ApiClient] Found the realm's server on this network: {url}");
                return true;
            }
            catch (Exception e) { Debug.LogWarning($"[ApiClient] LAN discovery failed: {e.Message}"); return false; }
            finally { _discovering = false; }
        }
        public string SharedWorldName => _settings != null ? (_settings.SharedWorldName ?? "").Trim() : "";

        public ApiClient(ApiSettings settings)
        {
            _settings = settings;
            Token = PlayerPrefs.GetString("sv_token", null);
        }

        public void SetToken(string token) { Token = token; PlayerPrefs.SetString("sv_token", token); PlayerPrefs.Save(); }

        public Task<T> Get<T>(string path) => Send<T>("GET", path, null, false);
        public Task<T> Post<T>(string path, object body = null, bool idempotent = false) => Send<T>("POST", path, body, idempotent);
        public Task<T> Patch<T>(string path, bool idempotent = true) => Send<T>("PATCH", path, null, idempotent);

        /// <summary>
        /// idempotent=true attaches a fresh Idempotency-Key. For VR gestures that may fire twice (double pinch),
        /// create the key once per *gesture* and pass it via SendWithKey so retries replay instead of duplicating.
        /// </summary>
        public Task<T> SendWithKey<T>(string method, string path, object body, string idempotencyKey) => Send<T>(method, path, body, false, idempotencyKey);

        async Task<T> Send<T>(string method, string path, object body, bool idempotent, string key = null)
        {
            if (idempotent) key ??= Guid.NewGuid().ToString();   // fixed before any retry, so a retry can't double-apply
            try { return await SendOnce<T>(method, path, body, key); }
            catch (GameApiException e) when (e.Code == "offline")
            {
                if (!await Discover()) throw;
                return await SendOnce<T>(method, path, body, key);  // the server moved: retry once at its new address
            }
        }

        async Task<T> SendOnce<T>(string method, string path, object body, string key)
        {
            using var req = new UnityWebRequest(BaseUrl + path, method) { downloadHandler = new DownloadHandlerBuffer() };
            req.timeout = _settings != null ? _settings.TimeoutSeconds : 10;
            if (body != null)
            {
                req.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(JsonConvert.SerializeObject(body, Json)));
                req.SetRequestHeader("Content-Type", "application/json");
            }
            if (!string.IsNullOrEmpty(Token)) req.SetRequestHeader("Authorization", "Bearer " + Token);
            if (key != null) req.SetRequestHeader("Idempotency-Key", key);

            // Every failure surfaces as GameApiException, so callers' catch blocks (and the player's toast) see it.
            try { await req.SendAsync(); }
            catch (InvalidOperationException e)   // e.g. "Insecure connection not allowed" (Player Settings > Allow HTTP)
            {
                throw new GameApiException(0, "blocked", $"The connection to the realm was blocked: {e.Message}");
            }
            var text = req.downloadHandler.text;
            if (req.result == UnityWebRequest.Result.ConnectionError)
                throw new GameApiException(0, "offline", $"The royal couriers cannot reach the server ({req.error})");
            if (req.responseCode >= 400)
            {
                string code = "error", message = req.error;
                try { var err = JObject.Parse(text)["error"]; code = (string)err?["code"] ?? code; message = (string)err?["message"] ?? message; }
                catch (JsonException) { }
                throw new GameApiException(req.responseCode, code, message);
            }
            try { return typeof(T) == typeof(JToken) ? (T)(object)JToken.Parse(text) : JsonConvert.DeserializeObject<T>(text, Json); }
            catch (JsonException e)
            {
                throw new GameApiException(req.responseCode, "bad_response", $"The server sent an unreadable reply ({e.Message})");
            }
        }

        // ---- typed helpers used across the game ------------------------------------------------------------
        public async Task<AuthResponse> Login(string user, string pass, bool register = false)
        {
            var r = await Post<AuthResponse>(register ? "/auth/register" : "/auth/login", new { username = user, password = pass });
            SetToken(r.Token);
            return r;
        }
        public Task<Dashboard> Dashboard(string kingdomId) => Get<Dashboard>($"/kingdoms/{kingdomId}/dashboard");
        public Task<WorldMap> Map(string worldId) => Get<WorldMap>($"/worlds/{worldId}/map");
        public Task<SinceReport> Since(string kingdomId, int turn) => Get<SinceReport>($"/kingdoms/{kingdomId}/since?turn={turn}");
    }
}
