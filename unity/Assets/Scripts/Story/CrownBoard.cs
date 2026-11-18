// The Hall of Crowns: prestige ranking (E + M + D + B + W) and who holds each of the five crowns, updated every turn.
using System.Text;
using Storyverse.Data;
using Storyverse.Kingdom;
using TMPro;
using UnityEngine;

namespace Storyverse.Story
{
    public class CrownBoard : MonoBehaviour
    {
        [SerializeField] TMP_Text board;
        [SerializeField] Renderer leaderPortrait;            // medallion of the realm's most prestigious ruler (optional)

        void OnEnable()
        {
            KingdomManager.Instance.OnDashboard += Render;
            if (KingdomManager.Instance.Dashboard != null) Render(KingdomManager.Instance.Dashboard);
        }

        void OnDisable() { if (KingdomManager.Instance) KingdomManager.Instance.OnDashboard -= Render; }

        void Render(Dashboard d)
        {
            if (d.Leaderboard == null || d.Leaderboard.Count == 0) { board.text = "<b>Hall of Crowns</b>\n<i>No prestige yet</i>"; return; }
            var me = KingdomManager.Instance.KingdomId;
            ArtLibrary.Show(leaderPortrait, ArtLibrary.Medallion(d.Leaderboard[0].Name));
            var sb = new StringBuilder("<b>Hall of Crowns</b>\n");
            foreach (var row in d.Leaderboard)
            {
                var name = row.KingdomId == me ? $"<color=#C6A15B>{row.Name}</color>" : row.Name;
                sb.Append($"{row.Rank}. {name}  {row.Prestige}");
                if (row.Penalty > 0) sb.Append($" <color=#b54a52>(-{row.Penalty} betrayal)</color>");
                if (row.Crowns != null && row.Crowns.Count > 0) sb.Append($"\n   <size=75%><color=#C6A15B>Crowns:</color> {string.Join(", ", row.Crowns)}</size>");
                sb.Append('\n');
            }
            board.text = sb.ToString();
        }
    }
}
