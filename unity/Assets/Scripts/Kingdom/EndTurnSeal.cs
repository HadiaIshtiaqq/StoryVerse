// The hourglass on the desk: palm-hold it to end your turn (production, loan installments, NPC moves, chronicle).
// In a shared world it marks you ready and shows who the court is still waiting for.
using Storyverse.Networking;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Kingdom
{
    public class EndTurnSeal : MonoBehaviour
    {
        [SerializeField] PalmHoldConfirm confirm;
        [SerializeField] TMP_Text status;

        bool _busy;

        void OnEnable()
        {
            confirm.OnConfirmed.AddListener(EndTurn);
            KingdomManager.Instance.OnTurnReady += ShowWaiting;
            KingdomManager.Instance.OnTurn += ShowTurn;
            KingdomManager.Instance.OnDashboard += ShowReign;
        }

        // Keep "Turn 5 / 20" current from every dashboard refresh, not only when a turn event arrives.
        void ShowReign(Data.Dashboard d) { if (d?.World != null && !_busy) ShowTurn(d.World.Turn); }

        void OnDisable()
        {
            confirm.OnConfirmed.RemoveListener(EndTurn);
            if (!KingdomManager.Instance) return;
            KingdomManager.Instance.OnTurnReady -= ShowWaiting;
            KingdomManager.Instance.OnTurn -= ShowTurn;
            KingdomManager.Instance.OnDashboard -= ShowReign;
        }

        async void EndTurn()
        {
            if (_busy || string.IsNullOrEmpty(KingdomManager.Instance.WorldId)) return;
            _busy = true;
            try
            {
                var r = await KingdomManager.Instance.AdvanceTurn();
                if (r.Advanced) ShowTurn(r.Turn);
                else ShowWaiting(r.WaitingFor?.ToArray() ?? System.Array.Empty<string>());
            }
            catch (GameApiException e) { Toasts.Show(e.Message); }
            finally { _busy = false; }
        }

        void ShowWaiting(string[] waitingFor)
        {
            if (status) status.text = waitingFor.Length == 0 ? "" : $"Waiting for\n{string.Join(", ", waitingFor)}";
        }

        void ShowTurn(int turn)
        {
            if (!status) return;
            var w = KingdomManager.Instance.Dashboard?.World;
            if (w != null && w.Status == "ENDED") { status.text = "The reign\nhas ended"; return; }
            var limit = w != null && w.TurnLimit > 0 ? w.TurnLimit : 0;
            var left = limit - turn;
            status.text = limit == 0 ? $"Turn {turn}"
                : left <= 3 ? $"Turn {turn} / {limit}\n<color=#ef8a8a>{left} to the coronation</color>"
                : $"Turn {turn} / {limit}";
        }
    }
}
