// Three coin chests whose size is the gift tier. Each floats its exact effect *before* you commit
// ("+6 Standing"), fixing the reference game's "+0" preview. Push a chest onto the envoy plate, then palm-hold to send.
using Storyverse.Data;
using Storyverse.Networking;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Diplomacy
{
    public class GiftTray : MonoBehaviour
    {
        [SerializeField] DiplomaticDesk desk;
        [SerializeField] TMP_Text[] chestLabels = new TMP_Text[3];
        [SerializeField] Collider envoyPlate;
        [SerializeField] Rigidbody[] chests = new Rigidbody[3];
        [SerializeField] PalmHoldConfirm confirm;

        GiftPreview _preview;
        int _chosen = -1;
        string _gestureKey;

        void OnEnable()
        {
            confirm.OnConfirmed.AddListener(Send);
            desk.OnTargetChanged += OnTargetChanged;        // the tiers depend on who you are gifting to
        }

        void OnDisable()
        {
            confirm.OnConfirmed.RemoveListener(Send);
            desk.OnTargetChanged -= OnTargetChanged;
        }

        void OnTargetChanged(RelationData _)
        {
            _preview = null;
            _gestureKey = null;                              // a key belongs to one gift to one kingdom
            foreach (var l in chestLabels) if (l) l.text = "";
            Refresh();
        }

        public async void Refresh()
        {
            if (desk.Target == null) return;
            var target = desk.Target.KingdomId;
            try
            {
                var preview = await ApiClient.Instance.Get<GiftPreview>(
                    $"/gifts/tiers?kingdom_id={Kingdom.KingdomManager.Instance.KingdomId}&target_id={target}");
                if (desk.Target == null || desk.Target.KingdomId != target) return;   // target changed while loading
                _preview = preview;
                for (int i = 0; i < chestLabels.Length && i < preview.Tiers.Count; i++)
                    chestLabels[i].text = $"{preview.Tiers[i].Gold:N0} gold" + (preview.Tiers[i].Iron > 0 ? $" + {preview.Tiers[i].Iron:N0} iron" : "") +
                                          $"\n<color=#4fb38a>+{preview.Tiers[i].StandingGain} Standing</color>";
            }
            catch (GameApiException e) { Toasts.Show(e.Message); }
        }

        void Update()
        {
            _chosen = -1;
            // "On the plate" = over the plate's footprint. The plate is a thin disc, so its 3D bounds never
            // contain a chest's centre of mass.
            var plate = envoyPlate.bounds;
            var radius = Mathf.Max(plate.extents.x, plate.extents.z);
            for (int i = 0; i < chests.Length; i++)
            {
                var c = chests[i].worldCenterOfMass;
                var flat = new Vector2(c.x - plate.center.x, c.z - plate.center.z).magnitude;
                if (flat <= radius && c.y >= plate.min.y - 0.01f && c.y <= plate.max.y + 0.12f) _chosen = i;
            }
            confirm.Armed = _chosen >= 0 && _preview != null && _chosen < _preview.Tiers.Count;
            if (_chosen < 0) _gestureKey = null;
            else _gestureKey ??= System.Guid.NewGuid().ToString();   // one key per placed chest: a repeated hold replays, never re-charges
        }

        async void Send()
        {
            if (_chosen < 0 || _preview == null || desk.Target == null) return;
            try
            {
                var tier = _preview.Tiers[_chosen];
                var result = await desk.SendGift(tier.Gold, tier.Iron, _gestureKey);   // exactly the chest that was previewed
                Toasts.Show($"Gift delivered: +{result.StandingGain} Standing (now {result.Standing})");
                Refresh();
            }
            catch (GameApiException e) { Toasts.Show(e.Message); }
        }
    }
}
