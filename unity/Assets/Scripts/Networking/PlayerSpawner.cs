#if STORYVERSE_FUSION // Requires Photon Fusion 2; see MultiplayerManager.cs
// Put this on the NetworkRunner prefab. In Shared Mode each client spawns its own avatar.
using Fusion;
using UnityEngine;

namespace Storyverse.Networking
{
    public class PlayerSpawner : SimulationBehaviour, IPlayerJoined
    {
        public static string LocalKingdomName = "", LocalKingdomColor = "#C6A15B";
        [SerializeField] NetworkObject avatarPrefab;

        public void PlayerJoined(PlayerRef player)
        {
            if (player != Runner.LocalPlayer) return;
            Runner.Spawn(avatarPrefab, Vector3.zero, Quaternion.identity, player,
                (_, obj) => obj.GetComponent<PlayerAvatar>().Init(LocalKingdomName, LocalKingdomColor));
        }
    }
}

#endif
