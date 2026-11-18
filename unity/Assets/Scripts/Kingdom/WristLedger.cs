// ResourceDisplay (spec §5.2): palm-up opens a small ledger on the wrist with balances and per-turn deltas.
using Storyverse.Data;
using TMPro;
using UnityEngine;

namespace Storyverse.Kingdom
{
    public class WristLedger : MonoBehaviour
    {
        [SerializeField] OVRHand hand;
        [SerializeField] Transform palm;                   // wrist/palm bone or anchor
        [SerializeField] Transform head;
        [SerializeField] GameObject panel;
        [SerializeField] TMP_Text body;
        [Tooltip("Dot product between palm normal and up needed to count as 'palm up'.")]
        [SerializeField] float palmUpThreshold = 0.7f;
        [SerializeField] OnboardingDirector onboarding;     // optional: completes the "palm up" tutorial step

        static readonly string[] Res = { "gold", "food", "wood", "stone", "iron" };

        void OnEnable() => KingdomManager.Instance.OnDashboard += Render;
        void OnDisable() { if (KingdomManager.Instance) KingdomManager.Instance.OnDashboard -= Render; }

        void Update()
        {
            // Palm normal points out of the palm: -palm.up on Meta's hand skeleton (verify for your rig).
            var palmUp = hand.IsTracked && Vector3.Dot(-palm.up, Vector3.up) > palmUpThreshold
                         && Vector3.Dot((palm.position - head.position).normalized, head.forward) > 0.5f;
            if (palmUp && !panel.activeSelf && onboarding) onboarding.ReportPalmLedgerShown();
            panel.SetActive(palmUp);
            if (palmUp) panel.transform.SetPositionAndRotation(palm.position + Vector3.up * 0.08f,
                Quaternion.LookRotation(panel.transform.position - head.position));
        }

        void Render(Dashboard d)
        {
            var k = d.Kingdom;
            var sb = new System.Text.StringBuilder($"<b>{k.Name}</b>  ·  Turn {d.World.Turn}\n");
            foreach (var r in Res)
            {
                var delta = k.YieldPerTurn != null && k.YieldPerTurn.TryGetValue(r, out var v) ? v : 0;
                var color = delta >= 0 ? "#4fb38a" : "#b54a52";
                sb.Append($"{char.ToUpper(r[0]) + r[1..],-6} {k.Resources.Get(r),7:N0}  <color={color}>{delta:+#;-#;0}</color>\n");
            }
            sb.Append($"People {k.Population:N0}   Soldiers {k.Soldiers:N0}   Prestige {k.Prestige}");
            body.text = sb.ToString();
        }
    }
}
