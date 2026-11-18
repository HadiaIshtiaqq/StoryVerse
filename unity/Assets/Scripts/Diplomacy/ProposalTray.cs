// The envoy's scroll: proposals other rulers (human or NPC) sent YOU (trades, loans, alliances, peace) appear
// one at a time on a parchment with an Accept seal and a Refuse seal (palm-hold either). Without this, the inbox the
// server keeps for you was unreachable in VR.
using System.Collections.Generic;
using System.Threading.Tasks;
using Storyverse.Data;
using Storyverse.Kingdom;
using Storyverse.Networking;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Diplomacy
{
    public class ProposalTray : MonoBehaviour
    {
        [SerializeField] TMP_Text parchment;
        [SerializeField] PalmHoldConfirm acceptSeal, refuseSeal;
        [SerializeField] GameObject refuseRoot;              // hidden for peace offers (there is nothing to refuse server-side)
        [SerializeField] GameObject waitingGlow;             // lights up while something waits for you
        [SerializeField] Renderer senderPortrait;            // medallion of the ruler who sent the proposal (optional)

        enum Kind { Trade, Loan, Alliance, Peace }
        struct Proposal { public Kind Kind; public string Id, Text, From; }

        readonly List<Proposal> _queue = new();
        bool _busy;

        public int PendingCount => _queue.Count;

        void OnEnable()
        {
            acceptSeal.OnConfirmed.AddListener(Accept);
            refuseSeal.OnConfirmed.AddListener(Refuse);
            KingdomManager.Instance.OnDashboard += Render;
            if (KingdomManager.Instance.Dashboard != null) Render(KingdomManager.Instance.Dashboard);
            else Show();
        }

        void OnDisable()
        {
            acceptSeal.OnConfirmed.RemoveListener(Accept);
            refuseSeal.OnConfirmed.RemoveListener(Refuse);
            if (KingdomManager.Instance) KingdomManager.Instance.OnDashboard -= Render;
        }

        static string NameOf(string kingdomId)
        {
            var k = KingdomManager.Instance.Map?.Kingdoms?.Find(x => x.Id == kingdomId);
            return k?.Name ?? "A distant court";
        }

        void Render(Dashboard d)
        {
            _queue.Clear();
            var inbox = d.Inbox;
            if (inbox != null)
            {
                foreach (var t in inbox.Trades ?? new List<TradeData>())
                    _queue.Add(new Proposal { Kind = Kind.Trade, Id = t.Id, From = NameOf(t.SenderId), Text =
                        $"<b>Trade from {NameOf(t.SenderId)}</b>\nThey give {t.OfferedAmount:N0} {t.OfferedResource}\nfor your {t.RequestedAmount:N0} {t.RequestedResource}" });
                foreach (var l in inbox.Loans ?? new List<LoanData>())
                {
                    var iLend = l.LenderId == KingdomManager.Instance.KingdomId;
                    _queue.Add(new Proposal { Kind = Kind.Loan, Id = l.Id, From = NameOf(iLend ? l.BorrowerId : l.LenderId), Text =
                        $"<b>Loan {l.Code}</b>\n{(iLend ? $"{NameOf(l.BorrowerId)} asks to borrow" : $"{NameOf(l.LenderId)} offers to lend")} {l.Principal:N0} gold\n" +
                        $"{l.InterestRate:0.#}% over {l.DurationTurns} turns · repay {l.TotalRepayment:N0}" });
                }
                foreach (var a in inbox.Alliances ?? new List<AllianceData>())
                    _queue.Add(new Proposal { Kind = Kind.Alliance, Id = a.Id, From = NameOf(a.ProposerId), Text =
                        $"<b>Alliance from {NameOf(a.ProposerId)}</b>\n{a.DurationTurns} turns{(a.MutualDefense ? " · mutual defence" : "")}" });
                foreach (var w in inbox.Peace ?? new List<WarData>())
                    _queue.Add(new Proposal { Kind = Kind.Peace, Id = w.Id, From = NameOf(w.PeaceProposedBy), Text = $"<b>Peace offered by {NameOf(w.PeaceProposedBy)}</b>\nEnd the war?" });
            }
            Show();
        }

        void Show()
        {
            var has = _queue.Count > 0;
            if (waitingGlow) waitingGlow.SetActive(has);
            ArtLibrary.Show(senderPortrait, has ? ArtLibrary.Medallion(_queue[0].From) : null);
            acceptSeal.Armed = has && !_busy;
            refuseSeal.Armed = has && !_busy && _queue[0].Kind != Kind.Peace;
            if (refuseRoot) refuseRoot.SetActive(!has || _queue[0].Kind != Kind.Peace);
            parchment.text = has
                ? $"{_queue[0].Text}\n<size=70%>{(_queue.Count > 1 ? $"1 of {_queue.Count} · " : "")}palm-hold a seal to answer</size>"
                : "<i>No envoys are waiting.</i>";
        }

        void Accept() => _ = Answer(true);
        void Refuse() => _ = Answer(false);

        /// <summary>Same path as the seals; used by the headless smoke test.</summary>
        public Task AnswerFirst(bool accept) => Answer(accept);

        async Task Answer(bool accept)
        {
            if (_busy || _queue.Count == 0) return;
            var p = _queue[0];
            if (!accept && p.Kind == Kind.Peace) return;
            _busy = true; Show();
            var api = ApiClient.Instance;
            var me = KingdomManager.Instance.KingdomId;
            // Deterministic key per answer: a repeated palm-hold replays instead of moving resources twice.
            var key = $"{(accept ? "accept" : "reject")}-{p.Id}";
            try
            {
                switch (p.Kind)
                {
                    case Kind.Trade:
                        await api.SendWithKey<TradeData>("POST", $"/trades/{p.Id}/{(accept ? "accept" : "reject")}", null, key);
                        Toasts.Show(accept ? "Trade sealed. The caravans are moving." : "Trade refused.");
                        break;
                    case Kind.Loan:
                        await api.SendWithKey<LoanData>("POST", $"/loans/{p.Id}/{(accept ? "accept" : "reject")}", null, key);
                        Toasts.Show(accept ? "Loan agreed. The ledger remembers." : "Loan refused.");
                        break;
                    case Kind.Alliance:
                        await api.SendWithKey<AllianceData>("POST", $"/alliances/{p.Id}/respond", new { accept }, key);
                        Toasts.Show(accept ? "The pact is sealed." : "Alliance refused.");
                        break;
                    case Kind.Peace:
                        await api.SendWithKey<Newtonsoft.Json.Linq.JObject>("POST", $"/wars/{p.Id}/peace", new { kingdom_id = me }, key);
                        Toasts.Show("Peace is made.");
                        break;
                }
            }
            catch (GameApiException e) { Toasts.Show(e.Message); }
            finally { _busy = false; }
            await KingdomManager.Instance.Refresh();
        }
    }
}
