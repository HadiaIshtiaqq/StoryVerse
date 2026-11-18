// Local representation of *my* kingdom and the shared world. Single source for UI/3D views.
// Refreshes from the server on every relevant WebSocket event; never invents state locally.
using System;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using Storyverse.Data;
using Storyverse.Networking;
using UnityEngine;

namespace Storyverse.Kingdom
{
    // Runs before every other script: map, desk, cards, ledger, rookery and chronicle subscribe to its events
    // in OnEnable, and Unity does not otherwise guarantee which object wakes first.
    [DefaultExecutionOrder(-1000)]
    public class KingdomManager : MonoBehaviour
    {
        public static KingdomManager Instance { get; private set; }

        [SerializeField] WorldEventSocket socket;

        public string WorldId { get; private set; }
        public string KingdomId { get; private set; }
        public Dashboard Dashboard { get; private set; }
        public WorldMap Map { get; private set; }

        public event Action<Dashboard> OnDashboard;
        public event Action<WorldMap> OnMap;
        public event Action<StoryEventData> OnChronicle;
        public event Action<NotificationData> OnNotification;
        public event Action<MessageData> OnLetter;
        public event Action<BattleData> OnBattle;
        public event Action<int> OnTurn;

        bool _refreshQueued;

        void Awake()
        {
            if (Instance != null) { Destroy(gameObject); return; }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        public async Task Enter(string worldId, string kingdomId)
        {
            WorldId = worldId; KingdomId = kingdomId;
            PlayerPrefs.SetString("sv_world", worldId); PlayerPrefs.SetString("sv_kingdom", kingdomId);
            socket.OnEvent -= HandleEvent;
            socket.OnEvent += HandleEvent;
            socket.Connect(worldId);
            await Refresh();
        }

        public async Task Refresh()
        {
            try
            {
                var dashTask = ApiClient.Instance.Dashboard(KingdomId);
                var mapTask = ApiClient.Instance.Map(WorldId);
                Dashboard = await dashTask; Map = await mapTask;
                OnDashboard?.Invoke(Dashboard);
                OnMap?.Invoke(Map);
            }
            catch (GameApiException e) { Debug.LogWarning($"[KingdomManager] {e.Message}"); }
            catch (Exception e) when (!(e is OperationCanceledException)) { Debug.LogException(e); }  // a bad listener must not stop refreshes
        }

        void HandleEvent(string type, JObject e)
        {
            try
            {
                switch (type)
                {
                    case "chronicle": OnChronicle?.Invoke(e["event"].ToObject<StoryEventData>(ApiClient.Serializer)); break;
                    case "notification": OnNotification?.Invoke(e["notification"].ToObject<NotificationData>(ApiClient.Serializer)); break;
                    case "letter": OnLetter?.Invoke(e["message"].ToObject<MessageData>(ApiClient.Serializer)); break;
                    case "battle": OnBattle?.Invoke(e["battle"].ToObject<BattleData>(ApiClient.Serializer)); break;
                    case "turn_advanced": OnTurn?.Invoke((int)e["turn"]); break;
                    case "turn_ready": OnTurnReady?.Invoke(e["waiting_for"]?.ToObject<string[]>() ?? Array.Empty<string>()); return;
                    case "pong": return;
                    // "connected" also fires after every reconnect: re-sync whatever happened while we were offline.
                }
            }
            catch (Exception ex) { Debug.LogWarning($"[KingdomManager] Bad '{type}' event: {ex.Message}"); }
            QueueRefresh();
        }

        async void QueueRefresh()
        {
            if (_refreshQueued) return;           // coalesce bursts (a turn emits many events)
            _refreshQueued = true;
            await Task.Delay(250);
            _refreshQueued = false;
            if (this) await Refresh();
        }

        public event Action<string[]> OnTurnReady;

        /// <summary>End turn. Solo worlds advance at once; shared worlds advance when every human ruler is ready.</summary>
        public async Task<TurnResult> AdvanceTurn()
        {
            var r = await ApiClient.Instance.Post<TurnResult>($"/worlds/{WorldId}/turn");
            await Refresh();
            return r;
        }
    }
}
