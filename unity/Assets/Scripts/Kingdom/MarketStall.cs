// The Royal Market in VR: a merchant's stall at the front-left corner of the table.
// Pinch (or look + pinch) one of four crates to choose the goods, then palm-hold BUY or SELL to trade a lot
// with the crown's merchants at fixed prices. The server sets prices, checks the treasury and the per-turn
// capacity, and writes the ledger; this stall only shows the numbers and sends the intent (spec §3.3).
using System;
using System.Linq;
using Storyverse.Data;
using Storyverse.Networking;
using Storyverse.XR;
using TMPro;
using UnityEngine;
using UnityEngine.Events;

namespace Storyverse.Kingdom
{
    public class MarketStall : MonoBehaviour
    {
        [Serializable]
        public class Crate
        {
            public string resource;             // food, wood, stone or iron
            public GazeTarget target;           // pinch / gaze-select picks these goods
            public GameObject selectedMarker;   // glow under the chosen crate
            public TMP_Text priceTag;           // "4 / 1" painted on the crate's board
        }

        [SerializeField] Crate[] crates = Array.Empty<Crate>();
        [SerializeField] TMP_Text board;                 // the merchant's slate above the stall
        [SerializeField] PalmHoldConfirm buySeal, sellSeal;
        [SerializeField] TMP_Text buyLabel, sellLabel;
        [SerializeField] int lot = 50;                   // units per palm-hold
        [SerializeField] AudioSource coins;

        string _chosen = "wood";
        bool _busy;
        readonly UnityAction[] _pickers = new UnityAction[8];

        void OnEnable()
        {
            for (int i = 0; i < crates.Length; i++)
            {
                var res = crates[i].resource;
                _pickers[i] = () => Choose(res);
                if (crates[i].target) crates[i].target.OnSelect.AddListener(_pickers[i]);
            }
            buySeal.OnConfirmed.AddListener(Buy);
            sellSeal.OnConfirmed.AddListener(Sell);
            KingdomManager.Instance.OnDashboard += Render;
            if (KingdomManager.Instance.Dashboard != null) Render(KingdomManager.Instance.Dashboard);
            else Render(null);
        }

        void OnDisable()
        {
            for (int i = 0; i < crates.Length; i++)
                if (crates[i].target && _pickers[i] != null) crates[i].target.OnSelect.RemoveListener(_pickers[i]);
            buySeal.OnConfirmed.RemoveListener(Buy);
            sellSeal.OnConfirmed.RemoveListener(Sell);
            if (KingdomManager.Instance) KingdomManager.Instance.OnDashboard -= Render;
        }

        public void Choose(string resource)
        {
            _chosen = resource;
            Render(KingdomManager.Instance.Dashboard);
        }

        /// <summary>Units the next palm-hold will trade: a full lot, or whatever capacity is left this turn.</summary>
        int LotSize(MarketView m) => Mathf.Max(0, Mathf.Min(lot, m?.UnitsLeft ?? 0));

        void Render(Dashboard d)
        {
            var m = d?.Market;
            foreach (var c in crates)
            {
                if (c.selectedMarker) c.selectedMarker.SetActive(c.resource == _chosen);
                if (c.priceTag)
                    c.priceTag.text = m?.Prices != null && m.Prices.TryGetValue(c.resource, out var p) ? $"{p.Buy} / {p.Sell}" : "";
            }
            if (m == null || !m.Open)
            {
                board.text = "<b>Royal Market</b>\n<size=80%>Build a <b>Market</b> to trade goods for gold with the crown's merchants.</size>";
                buySeal.Armed = sellSeal.Armed = false;
                if (buyLabel) buyLabel.text = "";
                if (sellLabel) sellLabel.text = "";
                return;
            }
            var price = m.Prices[_chosen];
            var have = d.Kingdom.Resources;
            var n = LotSize(m);
            var canBuy = n > 0 && have.Gold >= price.Buy * n;
            var canSell = n > 0 && have.Get(_chosen) >= n;
            board.text = $"<b>Royal Market</b>  <size=75%>gold per unit: buy / sell</size>\n" +
                         string.Join("   ", m.Prices.Select(kv => $"{(kv.Key == _chosen ? "<color=#8c2a33>" : "")}{kv.Key} {kv.Value.Buy}/{kv.Value.Sell}{(kv.Key == _chosen ? "</color>" : "")}")) +
                         $"\n<size=80%>{m.UnitsLeft} of {m.UnitsPerTurn} units left this turn · you hold {have.Get(_chosen):N0} {_chosen}, {have.Gold:N0} gold</size>" +
                         (n == 0 ? "\n<size=80%><i>The merchants are sold out until next turn.</i></size>" : "");
            buySeal.Armed = canBuy && !_busy;
            sellSeal.Armed = canSell && !_busy;
            if (buyLabel) buyLabel.text = n > 0 ? $"Buy {n} {_chosen}\n{price.Buy * n:N0} gold" : "";
            if (sellLabel) sellLabel.text = n > 0 ? $"Sell {n} {_chosen}\n+{price.Sell * n:N0} gold" : "";
        }

        void Buy() => _ = Trade("buy");
        void Sell() => _ = Trade("sell");

        /// <summary>Also used by the smoke test. Returns null when the trade did not happen.</summary>
        public async System.Threading.Tasks.Task<MarketResult> Trade(string side, string resource = null)
        {
            var km = KingdomManager.Instance;
            var n = LotSize(km.Dashboard?.Market);
            if (_busy || n == 0) return null;
            _busy = true;
            buySeal.Armed = sellSeal.Armed = false;
            MarketResult r = null;
            try
            {
                // idempotent: one key per palm-hold, so a repeated gesture or network retry cannot trade twice
                r = await ApiClient.Instance.Post<MarketResult>("/market",
                    new { kingdom_id = km.KingdomId, resource = resource ?? _chosen, amount = n, side }, idempotent: true);
                if (coins) coins.Play();
                Toasts.Show(side == "buy" ? $"Bought {r.Amount} {r.Resource} for {r.Gold:N0} gold."
                                          : $"Sold {r.Amount} {r.Resource} for {r.Gold:N0} gold.");
            }
            catch (GameApiException e) { Toasts.Show(e.Message); }
            finally { _busy = false; }
            await km.Refresh();
            return r;
        }
    }
}
