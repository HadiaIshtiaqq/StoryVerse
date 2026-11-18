// Royal Decrees in VR: a hanging scroll lists the next objectives with progress bars (text), and a wax seal claims
// the first completed one (palm-hold, like every other commitment). Rewards are paid by the server.
using System.Linq;
using System.Text;
using Storyverse.Data;
using Storyverse.Networking;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Kingdom
{
    public class DecreeBoard : MonoBehaviour
    {
        [SerializeField] TMP_Text list;
        [SerializeField] PalmHoldConfirm claimSeal;
        [SerializeField] TMP_Text claimLabel;

        DecreeData _ready;
        bool _busy;

        void OnEnable()
        {
            claimSeal.OnConfirmed.AddListener(Claim);
            KingdomManager.Instance.OnDashboard += Render;
            if (KingdomManager.Instance.Dashboard != null) Render(KingdomManager.Instance.Dashboard);
        }

        void OnDisable()
        {
            claimSeal.OnConfirmed.RemoveListener(Claim);
            if (KingdomManager.Instance) KingdomManager.Instance.OnDashboard -= Render;
        }

        static string Bar(int have, int need)
        {
            var filled = need <= 0 ? 10 : Mathf.Clamp(Mathf.RoundToInt(10f * have / need), 0, 10);
            return $"<color=#d6b066>{new string('|', filled)}</color><color=#5a4a30>{new string('|', 10 - filled)}</color>";
        }

        void Render(Dashboard d)
        {
            var decrees = d.Decrees ?? new System.Collections.Generic.List<DecreeData>();
            _ready = decrees.FirstOrDefault(x => x.Complete);
            var sb = new StringBuilder("<b>Royal Decrees</b>\n");
            foreach (var x in decrees)
            {
                var reward = string.Join(", ", x.Reward.Select(r => $"+{r.Value:N0} {r.Key}"));
                sb.Append(x.Complete ? "<color=#7fd1a3>»</color> " : "· ")
                  .Append($"<b>{x.Title}</b>  <size=80%>{x.Goal}</size>\n")
                  .Append($"<size=75%>{Bar(x.Progress, x.Need)}  {x.Progress:N0}/{x.Need:N0}  ·  {reward}</size>\n");
            }
            if (decrees.Count == 0) sb.Append("<i>Every decree is fulfilled.</i>");
            list.text = sb.ToString();
            claimSeal.Armed = _ready != null && !_busy;
            if (claimLabel) claimLabel.text = _ready != null ? $"Claim: {_ready.Title}" : "";
        }

        async void Claim()
        {
            if (_ready == null || _busy) return;
            _busy = true;
            try
            {
                await ApiClient.Instance.Post<Newtonsoft.Json.Linq.JObject>($"/decrees/{_ready.Key}/claim",
                    new { kingdom_id = KingdomManager.Instance.KingdomId });
                Toasts.Show($"Decree fulfilled: {_ready.Title}. The crown is rewarded.");
            }
            catch (GameApiException e) { Toasts.Show(e.Message); }
            finally { _busy = false; }
            await KingdomManager.Instance.Refresh();
        }
    }
}
