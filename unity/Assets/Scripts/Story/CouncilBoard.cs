// The Royal Council (picture 1): the adviser with the most urgent counsel speaks, portrait and all.
// Advice is computed by the server from the live state of the realm.
using Storyverse.Data;
using Storyverse.Kingdom;
using TMPro;
using UnityEngine;

namespace Storyverse.Story
{
    public class CouncilBoard : MonoBehaviour
    {
        [SerializeField] Renderer portrait;
        [SerializeField] TMP_Text nameplate, counsel;
        [SerializeField] Herald herald;                 // optional: urgent counsel is also spoken aloud

        string _lastSpoken;

        void OnEnable()
        {
            KingdomManager.Instance.OnDashboard += Render;
            if (KingdomManager.Instance.Dashboard != null) Render(KingdomManager.Instance.Dashboard);
        }

        void OnDisable() { if (KingdomManager.Instance) KingdomManager.Instance.OnDashboard -= Render; }

        void Render(Dashboard d)
        {
            var a = d.Council != null && d.Council.Count > 0 ? d.Council[0] : null;   // server sorts by urgency
            if (a == null) { counsel.text = "<i>The council is silent.</i>"; ArtLibrary.Show(portrait, null); return; }
            ArtLibrary.Show(portrait, ArtLibrary.Medallion(a.Portrait));
            nameplate.text = $"<b>{a.Name}</b>\n<size=70%><i>{a.Role}</i></size>";
            var tone = a.Urgency >= 2 ? "#8c2a33" : a.Urgency == 1 ? "#6e4d1d" : "#2a2015";
            counsel.text = $"<color={tone}>\"{a.Advice}\"</color>";
            if (herald && a.Urgency >= 2 && a.Advice != _lastSpoken)
            {
                _lastSpoken = a.Advice;
                herald.Say($"{a.Name} counsels: {a.Advice}");
            }
        }
    }
}
