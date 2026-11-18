// DiplomacyManager / TradeManager / LoanManager (spec §5.2) as one physical desk:
// select a kingdom (gaze + pinch its seat) -> Standing Gauge updates -> four Treaty Seals and a Gift Tray act on it.
// Every NPC answer is shown as itemised reasons on a parchment (judging alignment §2.1).
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json.Linq;
using Storyverse.Data;
using Storyverse.Kingdom;
using Storyverse.Networking;
using Storyverse.World;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Diplomacy
{
    public class DiplomaticDesk : MonoBehaviour
    {
        [System.Serializable]
        public class Seal
        {
            public string action;                  // alliance | declare_war | peace | trade | loan
            public PalmHoldConfirm confirm;
            public GameObject crackedVisual;       // shown when locked
            public TMP_Text engraving;             // lock reason / warning
        }

        [SerializeField] StandingGauge gauge;
        [SerializeField] Seal[] seals;
        [SerializeField] TMP_Text targetTitle;
        [SerializeField] TMP_Text decisionParchment;
        [SerializeField] GameObject decisionRoot;
        [SerializeField] Renderer targetPortrait;            // medallion of the ruler across the desk (optional)

        [Header("Default proposals (tweak with the desk dials)")]
        public string tradeGive = "food", tradeWant = "iron";
        public int tradeGiveAmount = 100, tradeWantAmount = 80;
        public int loanPrincipal = 2000, loanDuration = 5; public float loanRate = 10f; public bool loanAsBorrower = true;
        public int battleSoldiersPercent = 50;

        public RelationData Target { get; private set; }

        void Awake()
        {
            foreach (var s in seals) { var seal = s; s.confirm.OnConfirmed.AddListener(() => _ = Act(seal.action)); }
        }

        void OnEnable()
        {
            KingdomSeat.OnSelected += Select;
            KingdomManager.Instance.OnDashboard += OnDashboard;
        }

        void OnDisable()
        {
            KingdomSeat.OnSelected -= Select;
            if (KingdomManager.Instance) KingdomManager.Instance.OnDashboard -= OnDashboard;
        }

        void OnDashboard(Dashboard _) => RefreshTarget();

        /// <summary>Raised after the desk's target kingdom changes (GiftTray reloads its tiers).</summary>
        public event System.Action<RelationData> OnTargetChanged;

        void Select(KingdomSeat seat)
        {
            var km = KingdomManager.Instance;
            if (seat.KingdomId == km.KingdomId || km.Dashboard?.Relations == null) return;
            var relation = km.Dashboard.Relations.FirstOrDefault(r => r.KingdomId == seat.KingdomId);
            if (relation == null) return;                  // seat from a map refresh the dashboard hasn't caught up with
            Target = relation;
            RefreshTarget();
            OnTargetChanged?.Invoke(Target);
        }

        void RefreshTarget()
        {
            if (Target == null) return;
            Target = KingdomManager.Instance.Dashboard.Relations.FirstOrDefault(r => r.KingdomId == Target.KingdomId) ?? Target;
            targetTitle.text = $"{Target.Name}\n<size=60%>{Target.RulerName}{(Target.IsNpc ? " · NPC" : "")}</size>";
            ArtLibrary.Show(targetPortrait, ArtLibrary.Medallion(Target.Name));
            gauge.Show(Target);
            foreach (var s in seals)
            {
                var gateKey = s.action == "loan" ? "loan" : s.action;
                var gate = Target.Actions.TryGetValue(gateKey, out var g) ? g : new ActionGate { Allowed = true };
                var allowed = gate.Allowed || (s.action == "declare_war" && Target.WarId != null)
                              || (s.action == "passage" && Target.PassageGranted != null);
                s.confirm.Armed = allowed;
                s.crackedVisual.SetActive(!allowed);
                s.engraving.text = !allowed ? gate.Reason : gate.Warning ?? (s.action == "declare_war" && Target.WarId != null ? "Attack"
                                 : s.action == "passage" && Target.PassageGranted != null ? "Close roads" : "");
            }
        }

        async Task Act(string action)
        {
            if (Target == null) return;
            var me = KingdomManager.Instance.KingdomId;
            var api = ApiClient.Instance;
            try
            {
                switch (action)
                {
                    case "alliance":
                        Show((await api.Post<AllianceData>("/alliances", new { kingdom_id = me, target_id = Target.KingdomId })).Decision, "Alliance proposed");
                        break;
                    case "trade":
                        var t = await api.Post<TradeData>("/trades", new { kingdom_id = me, receiver_id = Target.KingdomId, offered_resource = tradeGive,
                            offered_amount = tradeGiveAmount, requested_resource = tradeWant, requested_amount = tradeWantAmount }, idempotent: true);
                        Show(t.Decision, $"Trade {t.Status.ToLower()}");
                        break;
                    case "loan":
                        var l = await api.Post<LoanData>("/loans", new { kingdom_id = me, counterparty_id = Target.KingdomId,
                            role = loanAsBorrower ? "borrower" : "lender", principal = loanPrincipal, interest_rate = loanRate,
                            duration_turns = loanDuration }, idempotent: true);
                        Show(l.Decision, $"Loan {l.Code}: {l.Status.ToLower()} (repay {l.TotalRepayment:N0})");
                        break;
                    case "declare_war":
                        var soldiers = Mathf.Max(1, KingdomManager.Instance.Dashboard.Kingdom.Soldiers * battleSoldiersPercent / 100);
                        var b = await api.Post<BattleData>("/battles", new { kingdom_id = me, target_id = Target.KingdomId, soldiers }, idempotent: true);
                        Toasts.Show($"Battle of {b.PlaceName}: {(b.Outcome == "ATTACKER_VICTORY" ? "victory" : "defeat")}");
                        break;
                    case "passage":
                        if (Target.PassageGranted != null)
                        {
                            await api.Post<JObject>($"/passages/{Target.PassageGranted.Id}/close", new { kingdom_id = me });
                            Toasts.Show($"Your roads to {Target.Name} are closed.");
                        }
                        else
                        {
                            await api.Post<JObject>("/passages", new { kingdom_id = me, target_id = Target.KingdomId });
                            Toasts.Show($"Your roads are open to {Target.Name}. Both realms earn tolls each turn.");
                        }
                        break;
                    case "peace":
                        var p = await api.Post<JObject>($"/wars/{Target.WarId}/peace", new { kingdom_id = me });
                        Show(p["decision"]?.Type == JTokenType.Null ? null : p["decision"]?.ToObject<Decision>(ApiClient.Serializer), "Peace offered");
                        break;
                }
            }
            catch (GameApiException e) { Toasts.Show(e.Message); }
            await KingdomManager.Instance.Refresh();
        }

        /// <summary>Gift Tray calls this after a chest was pushed across the desk and confirmed.</summary>
        public async Task<GiftResult> SendGift(int gold, int iron, string gestureKey)
        {
            var r = await ApiClient.Instance.SendWithKey<GiftResult>("POST", "/gifts",
                new { kingdom_id = KingdomManager.Instance.KingdomId, target_id = Target.KingdomId, gold, iron }, gestureKey);
            await KingdomManager.Instance.Refresh();
            return r;
        }

        void Show(Decision d, string headline)
        {
            if (d == null) { Toasts.Show(headline); return; }
            var sb = new System.Text.StringBuilder($"<b>{d.Summary}</b>\n");
            foreach (var r in d.Reasons ?? new System.Collections.Generic.List<Reason>()) sb.AppendLine($"<color={(r.Value >= 0 ? "#2f7a5a" : "#8b2f36")}>{r.Value:+#;-#;0}</color>  {r.Label}");
            decisionParchment.text = sb.ToString();
            decisionRoot.SetActive(true);
        }
    }
}
