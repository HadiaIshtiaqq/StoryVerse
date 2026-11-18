// A miniature in the building tray. Pinch it to start placing; it greys out when you can't afford it.
using System.Linq;
using Storyverse.Data;
using Storyverse.Kingdom;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Buildings
{
    public class BuildingCard : MonoBehaviour
    {
        [SerializeField] string buildingType = "farm";
        [SerializeField] GameObject previewPrefab;
        [SerializeField] TMP_Text costLabel;
        [SerializeField] Renderer body;
        [SerializeField] BuildingPlacementManager placement;
        [SerializeField] PinchDetector[] pinchers;
        [SerializeField] float grabRadius = 0.04f;

        CatalogEntry _entry;
        bool _affordable;

        void OnEnable()
        {
            foreach (var p in pinchers) p.PinchStarted += TryGrab;
            KingdomManager.Instance.OnDashboard += Refresh;
        }
        void OnDisable()
        {
            foreach (var p in pinchers) p.PinchStarted -= TryGrab;
            if (KingdomManager.Instance) KingdomManager.Instance.OnDashboard -= Refresh;
        }

        public void SetCatalog(CatalogEntry entry)
        {
            _entry = entry;
            costLabel.text = $"{entry.Label}\n<size=70%>{string.Join("  ", entry.Cost.Select(c => $"{c.Value} {c.Key}"))}</size>";
        }

        void Refresh(Dashboard d)
        {
            if (_entry == null) return;
            _affordable = _entry.Cost.All(c => d.Kingdom.Resources.Get(c.Key) >= c.Value);
            body.material.color = _affordable ? Color.white : new Color(0.4f, 0.4f, 0.4f);
        }

        void TryGrab(PinchDetector hand)
        {
            if (Vector3.Distance(hand.PinchPoint, transform.position) > grabRadius) return;
            if (!_affordable) { Toasts.Show($"Not enough resources for a {_entry?.Label}"); return; }
            placement.BeginPlacement(buildingType, previewPrefab, hand);
        }
    }
}
