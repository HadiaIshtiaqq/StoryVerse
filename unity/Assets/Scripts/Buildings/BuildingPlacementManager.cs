// Spec §4.4 building flow: pinch a building from the tray -> translucent preview follows the pinch over the
// map -> green/red validity -> release -> server validates -> building appears (or the reason is shown).
using System.Linq;
using Storyverse.Data;
using Storyverse.Kingdom;
using Storyverse.Networking;
using Storyverse.World;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Buildings
{
    public class BuildingPlacementManager : MonoBehaviour
    {
        [SerializeField] RealmMap map;
        [SerializeField] PinchDetector[] pinchers;
        [SerializeField] Material validMat, invalidMat;
        [SerializeField] TMP_Text reasonLabel;              // floats above the preview
        [SerializeField] AudioSource placeSound, denySound;
        [SerializeField] float borderRadius = 0.22f, minSpacing = 0.03f, maxHoverHeight = 0.12f;

        public bool IsPlacing => _preview != null;
        string _type; GameObject _preview; PinchDetector _hand;
        bool _lastValid; string _lastReason;

        /// <summary>Called by a BuildingCard in the tray when it is pinched.</summary>
        public void BeginPlacement(string buildingType, GameObject previewPrefab, PinchDetector hand)
        {
            Cancel();
            _type = buildingType; _hand = hand;
            _lastValid = false; _lastReason = null;
            _preview = Instantiate(previewPrefab, map.Root);
            foreach (var c in _preview.GetComponentsInChildren<Collider>()) c.enabled = false;
            hand.PinchEnded += OnRelease;
            hand.TrackingLost += OnTrackingLost;
        }

        void Update()
        {
            if (!IsPlacing) return;
            var local = map.Root.InverseTransformPoint(_hand.PinchPoint);
            _preview.transform.localPosition = new Vector3(local.x, 0, local.z);
            // InverseTransformPoint already returns map-local units (1 = map width): no extra scale division.
            var (ok, reason) = Validate(map.WorldToMap(_hand.PinchPoint), local.y);
            _lastValid = ok; _lastReason = reason;
            foreach (var r in _preview.GetComponentsInChildren<Renderer>()) r.sharedMaterial = ok ? validMat : invalidMat;
            if (reasonLabel) { reasonLabel.text = ok ? "" : reason; reasonLabel.transform.position = _preview.transform.position + Vector3.up * 0.08f; }
        }

        (bool, string) Validate(Vector2 m, float height)
        {
            var km = KingdomManager.Instance;
            if (km.Map == null) return (false, "The realm is still loading");
            if (height > maxHoverHeight) return (false, "Lower it onto the map");
            if (m.x < 0 || m.x > 1 || m.y < 0 || m.y > 1) return (false, "Off the map");
            var mine = km.Map.Kingdoms.FirstOrDefault(k => k.Id == km.KingdomId);
            if (mine == null) return (false, "Your kingdom is not on this map");
            if (Vector2.Distance(m, new Vector2(mine.MapX, mine.MapY)) > borderRadius) return (false, "Outside your borders");
            if (km.Map.Buildings.Any(b => Vector2.Distance(m, new Vector2(b.X, b.Z)) < minSpacing)) return (false, "Not enough space");
            return (true, null);   // affordability is shown on the tray card; the server has the final word
        }

        async void OnRelease(PinchDetector hand)
        {
            var m = map.WorldToMap(hand.PinchPoint);
            var key = hand.GestureId;                          // one gesture == one transaction (XR-09)
            var rotation = _preview.transform.localEulerAngles.y;
            var type = _type;
            var (valid, why) = (_lastValid, _lastReason);
            Cancel();
            if (!valid)                                        // released over a red preview: explain, commit nothing
            {
                if (denySound) denySound.Play();
                Toasts.Show(why ?? "That spot is not allowed");
                return;
            }
            try
            {
                await ApiClient.Instance.SendWithKey<BuildingData>("POST", "/buildings",
                    new { kingdom_id = KingdomManager.Instance.KingdomId, building_type = type, x = m.x, z = m.y, rotation_y = rotation }, key);
                if (placeSound) placeSound.Play();
                await KingdomManager.Instance.Refresh();
            }
            catch (GameApiException e)
            {
                if (denySound) denySound.Play();
                Toasts.Show(e.Message);                        // e.g. "Insufficient wood: need 100, have 40"
            }
        }

        void OnTrackingLost(PinchDetector _) => Cancel();     // safe pause: nothing is committed

        public void Cancel()
        {
            if (_hand != null) { _hand.PinchEnded -= OnRelease; _hand.TrackingLost -= OnTrackingLost; }
            if (_preview) Destroy(_preview);
            if (reasonLabel) reasonLabel.text = "";
            _preview = null; _hand = null;
        }
    }
}
