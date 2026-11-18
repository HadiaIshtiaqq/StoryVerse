using Storyverse.Data;
using Storyverse.Kingdom;
using UnityEngine;

namespace Storyverse.Diplomacy
{
    /// <summary>Spawns a raven + letter on the table whenever a private letter arrives.</summary>
    public class Rookery : MonoBehaviour
    {
        [SerializeField] LetterObject letterPrefab;
        [SerializeField] Transform landingSpot;          // near the player's edge of the map
        [SerializeField] Animator raven;

        void OnEnable() => KingdomManager.Instance.OnLetter += Deliver;
        void OnDisable() { if (KingdomManager.Instance) KingdomManager.Instance.OnLetter -= Deliver; }

        public void Deliver(MessageData m)
        {
            var sender = KingdomManager.Instance.Map?.Kingdoms?.Find(k => k.Id == m.SenderKingdomId);
            ColorUtility.TryParseHtmlString(sender?.Color ?? "#C6A15B", out var color);
            var letter = Instantiate(letterPrefab, landingSpot.position, landingSpot.rotation);
            letter.Bind(m, sender?.Name ?? "Unknown", color);
            if (raven) raven.SetTrigger("Land");
        }
    }
}
