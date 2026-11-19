// Drakoria's ultimatums in VR: a lectern at the front-right corner of the table that rises only while a court
// demands tribute. It shows the demand, the deadline and the defence race (yours now vs what deters them at the
// deadline), the Herald reads the demand aloud once, and a crimson seal pays the tribute (palm-hold).
// Paying is an ordinary gift on the server; the NPC answers by letter (the Rookery delivers it).
using System.Linq;
using Storyverse.Data;
using Storyverse.Networking;
using Storyverse.Story;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Diplomacy
{
    public class UltimatumLectern : MonoBehaviour
    {
        [SerializeField] GameObject visual;              // the lectern itself; hidden while nobody threatens you
        [SerializeField] TMP_Text scroll;
        [SerializeField] Renderer threatenerPortrait;    // the demanding ruler's medallion
        [SerializeField] PalmHoldConfirm paySeal;
        [SerializeField] TMP_Text payLabel;
        [SerializeField] Herald herald;                  // optional: reads each new demand aloud
        [SerializeField] AudioSource drum;               // optional: war drum when a demand appears

        UltimatumData _current;
        string _announced;
        bool _busy;

        public UltimatumData Current => _current;

        void OnEnable()
        {
            paySeal.OnConfirmed.AddListener(PayGesture);
            Kingdom.KingdomManager.Instance.OnDashboard += Render;
            Render(Kingdom.KingdomManager.Instance.Dashboard);
        }

        void OnDisable()
        {
            paySeal.OnConfirmed.RemoveListener(PayGesture);
            if (Kingdom.KingdomManager.Instance) Kingdom.KingdomManager.Instance.OnDashboard -= Render;
        }

        void Render(Dashboard d)
        {
            _current = d?.World?.Status == "ENDED" ? null : d?.Ultimatums?.FirstOrDefault();
            visual.SetActive(_current != null);
            if (_current == null) { paySeal.Armed = false; return; }
            var u = _current;
            ArtLibrary.Show(threatenerPortrait, ArtLibrary.Medallion(u.From));

            var when = u.TurnsLeft <= 0 ? "now" : $"in {u.TurnsLeft} End Turn{(u.TurnsLeft == 1 ? "" : "s")}";
            var defence = u.Safe
                ? "<color=#2f6a45>Your defences are strong enough: she will not dare attack.</color>"
                : $"Raise defence to <b>{u.DefenseNeeded}</b> to make her back down: soldiers (Barracks), Watchtowers (+25% each rank), or an ally with mutual defence.";
            scroll.text = $"<b><color=#8c2a33>Ultimatum from {u.From}</color></b>\n" +
                          $"{u.Ruler} demands <b>{u.Amount:N0} gold</b> by turn {u.DeadlineTurn}. Her army marches {when} if it is not paid.\n" +
                          (u.Paid > 0 ? $"<size=85%>Paid so far: {u.Paid:N0} of {u.Amount:N0}.</size>\n" : "") +
                          $"<size=85%>Your defence <b>{u.YourDefense}</b> · needed <b>{u.DefenseNeeded}</b> · her army ~{u.TheirArmy}</size>\n" +
                          $"<size=80%>{defence}</size>";

            var canPay = u.Owed > 0 && d.Kingdom.Resources.Gold >= u.Owed;
            paySeal.Armed = canPay && !_busy;
            if (payLabel)
                payLabel.text = u.Owed <= 0 ? "Tribute paid" : canPay ? $"Pay {u.Owed:N0} gold" : $"Need {u.Owed:N0} gold";

            var key = $"{u.FromId}:{u.DeadlineTurn}";
            if (_announced != key)
            {
                _announced = key;
                if (drum) drum.Play();
                if (herald) herald.Say($"Hear ye! {u.Ruler} of {u.From} demands {u.Amount:N0} gold in tribute by turn {u.DeadlineTurn}, or war.");
                else Toasts.Show($"{u.From} demands {u.Amount:N0} gold by turn {u.DeadlineTurn}.");
            }
        }

        void PayGesture() => _ = Pay();

        /// <summary>Palm-hold on the crimson seal: send the owed gold as a gift. Also used by the smoke test.</summary>
        public async System.Threading.Tasks.Task<bool> Pay()
        {
            var u = _current;
            if (u == null || u.Owed <= 0 || _busy) return false;
            _busy = true; paySeal.Armed = false;
            var ok = false;
            try
            {
                await ApiClient.Instance.Post<GiftResult>("/gifts",
                    new { kingdom_id = Kingdom.KingdomManager.Instance.KingdomId, target_id = u.FromId, gold = u.Owed }, idempotent: true);
                Toasts.Show($"Tribute of {u.Owed:N0} gold sent to {u.From}. Her banners stay furled.");
                ok = true;
            }
            catch (GameApiException e) { Toasts.Show(e.Message); }
            finally { _busy = false; }
            await Kingdom.KingdomManager.Instance.Refresh();
            return ok;
        }
    }
}
