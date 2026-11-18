// Photon Fusion 2 session per world (Shared Mode). Fusion carries presence: heads, hands, pointing.
// It never touches gold. Economic state comes only from the backend (spec §2.1 architectural decision).
// Requires: Photon Fusion 2 SDK with an App Id set in the Fusion Hub, then add the scripting define
// STORYVERSE_FUSION (Project Settings > Player > Scripting Define Symbols). Without it the game still runs:
// everything server-side works, you just don't see other rulers' hands.
using System.Threading.Tasks;
using UnityEngine;
#if STORYVERSE_FUSION
using Fusion;
#endif

namespace Storyverse.Networking
{
    public class MultiplayerManager : MonoBehaviour
    {
#if STORYVERSE_FUSION
        [Tooltip("Prefab with NetworkRunner + PlayerSpawner components.")]
        [SerializeField] NetworkRunner runnerPrefab;

        public NetworkRunner Runner { get; private set; }

        public async Task<bool> JoinWorld(string worldId, string kingdomName, string kingdomColor)
        {
            PlayerSpawner.LocalKingdomName = kingdomName;
            PlayerSpawner.LocalKingdomColor = kingdomColor;
            Runner = Instantiate(runnerPrefab);
            var result = await Runner.StartGame(new StartGameArgs
            {
                GameMode = GameMode.Shared,
                SessionName = $"storyverse-{worldId}",   // one Fusion room per backend world
                PlayerCount = 4,
                SceneManager = Runner.gameObject.AddComponent<NetworkSceneManagerDefault>(),
            });
            if (!result.Ok) Debug.LogError($"[Fusion] Could not join: {result.ShutdownReason}");
            return result.Ok;
        }

        public async Task Leave()
        {
            if (Runner != null) await Runner.Shutdown();
        }
#else
        public Task<bool> JoinWorld(string worldId, string kingdomName, string kingdomColor)
        {
            Debug.LogWarning("[Multiplayer] Photon Fusion 2 not enabled (define STORYVERSE_FUSION). " +
                             "Running without shared presence; the game itself is unaffected.");
            return Task.FromResult(false);
        }

        public Task Leave() => Task.CompletedTask;
#endif
    }
}
