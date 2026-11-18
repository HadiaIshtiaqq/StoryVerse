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
        }

        void OnDisable()
        {
            confirm.OnConfirmed.RemoveListener(EndTurn);
            if (!KingdomManager.Instance) return;
            KingdomManager.Instance.OnTurnReady -= ShowWaiting;
            KingdomManager.Instance.OnTurn -= ShowTurn;
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
            if (status) status.text = $"Turn {turn}";
        }
    }
}
