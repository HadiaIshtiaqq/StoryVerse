// Entry flow for the Quest build:
//   login (or register) -> resume or create a world -> claim a kingdom -> place the realm on the table ->
//   join the Fusion room -> "while you were away" replay -> onboarding on first run.
// The quick-start path ("Solo Court") is what a judge playing alone gets: three NPC rulers, instantly.
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using Storyverse.Data;
using Storyverse.Kingdom;
using Storyverse.Networking;
using Storyverse.Story;
using Storyverse.XR;
using UnityEngine;

namespace Storyverse
{
    public class GameBootstrap : MonoBehaviour
    {
        [SerializeField] TableAnchorPlacer tablePlacer;
        [SerializeField] MultiplayerManager multiplayer;
        [SerializeField] ChronicleWall chronicle;
        [SerializeField] OnboardingDirector onboarding;

        [Header("Dev / judge quick start")]
        [Tooltip("Auto-create a device account so the headset is playable without a keyboard.")]
        [SerializeField] bool autoAccount = true;
        [SerializeField] string preferredKingdom = "Sylvara";
        [SerializeField] string preset = "solo_court";

        async void Start()
        {
            if (Dev.SmokeTest.Requested) gameObject.AddComponent<Dev.SmokeTest>();
            try
            {
                await EnsureLogin();
                var (worldId, kingdomId) = await ResumeOrCreate();
                await KingdomManager.Instance.Enter(worldId, kingdomId);
                if (KingdomManager.Instance.Dashboard == null)
                    throw new GameApiException(0, "load_failed", "Your kingdom could not be loaded");
                var k = KingdomManager.Instance.Dashboard.Kingdom;
                Debug.Log($"[GameBootstrap] Entered world {worldId} as {k.Name} ({k.RulerName}), turn {KingdomManager.Instance.Dashboard.World.Turn}, gold {k.Resources?.Gold}");
                _ = multiplayer.JoinWorld(worldId, k.Name, k.Color);

                var lastSeen = PlayerPrefs.GetInt($"sv_last_turn_{worldId}", 0);
                if (lastSeen > 0) await chronicle.ReplaySince(lastSeen);
                else onboarding.Begin();
                KingdomManager.Instance.OnTurn += t => PlayerPrefs.SetInt($"sv_last_turn_{worldId}", t);
                PlayerPrefs.SetInt($"sv_last_turn_{worldId}", KingdomManager.Instance.Dashboard.World.Turn);
            }
            catch (GameApiException e)
            {
                Toasts.Show($"Could not reach the realm: {e.Message}");
                Debug.LogError(e);
            }
            catch (System.Exception e)        // async void: anything uncaught here would vanish silently
            {
                Toasts.Show("Something went wrong entering the realm. Please restart.");
                Debug.LogException(e);
            }
        }

        async Task EnsureLogin()
        {
            var api = ApiClient.Instance;
            if (!string.IsNullOrEmpty(api.Token))
            {
                try { await api.Get<JToken>("/auth/me"); return; } catch (GameApiException e) when (e.Status == 401) { }
            }
            if (!autoAccount) throw new GameApiException(401, "login_required", "Please log in");
            // Device-local account: random credentials stored in PlayerPrefs (never shared).
            var user = PlayerPrefs.GetString("sv_device_user", "");
            var pass = PlayerPrefs.GetString("sv_device_pass", "");
            if (user != "")
            {
                try { await api.Login(user, pass); return; }
                // The server no longer knows this device (database reset, new server): make a fresh device account
                // instead of failing on every launch.
                catch (GameApiException e) when (e.Status == 401) { Debug.LogWarning("[GameBootstrap] Device account unknown to server; re-registering"); }
            }
            user = "ruler_" + System.Guid.NewGuid().ToString("N")[..10];
            pass = System.Guid.NewGuid().ToString("N");
            await api.Login(user, pass, register: true);
            PlayerPrefs.SetString("sv_device_user", user); PlayerPrefs.SetString("sv_device_pass", pass); PlayerPrefs.Save();
        }

        async Task<(string, string)> ResumeOrCreate()
        {
            var api = ApiClient.Instance;
            var shared = api.SharedWorldName;
            if (shared != "") return await JoinShared(shared);

            var me = await api.Get<JObject>("/auth/me");
            var mine = me["kingdoms"]?.FirstOrDefault();
            if (mine != null) return ((string)mine["world_id"], (string)mine["kingdom_id"]);
            var world = await api.Post<JObject>("/worlds", new { name = "The Continent", preset });
            var kingdom = await api.Post<KingdomData>("/worlds/join", new { world_id = (string)world["id"], kingdom_name = preferredKingdom });
            return ((string)world["id"], kingdom.Id);
        }

        /// <summary>Four headsets, one world: resume my throne there, else take a free one, else create the world.</summary>
        async Task<(string, string)> JoinShared(string name)
        {
            var api = ApiClient.Instance;
            var worlds = await api.Get<JArray>("/worlds");
            // /worlds is newest-first; prefer the OLDEST world with this name so that if two headsets raced to
            // create it, everyone else still converges on the same one.
            var named = worlds.Where(w => (string)w["name"] == name).Reverse().ToList();
            var resumed = named.FirstOrDefault(w => w["my_kingdom_id"]?.Type == JTokenType.String);
            if (resumed != null) return ((string)resumed["id"], (string)resumed["my_kingdom_id"]);

            var open = named.FirstOrDefault(w => w["open_seats"] is JArray seats && seats.Count > 0);
            string worldId;
            if (open != null) worldId = (string)open["id"];
            else worldId = (string)(await api.Post<JObject>("/worlds", new { name, preset = "standard" }))["id"];

            var seatsLeft = open?["open_seats"]?.ToObject<string[]>();
            var seat = seatsLeft == null || seatsLeft.Contains(preferredKingdom) ? preferredKingdom : seatsLeft[0];
            var kingdom = await api.Post<KingdomData>("/worlds/join", new { world_id = worldId, kingdom_name = seat });
            return (worldId, kingdom.Id);
        }
    }
}
