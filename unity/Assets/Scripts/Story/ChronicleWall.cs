// StoryEventManager (spec §5.2): the Living History Engine made visible.
// Chronicle panels hang on the nearest real wall (MRUK) or a free-standing banner; the Herald reads
// important entries aloud; "while you were away" replays what happened since your last visit.
using System.Collections.Generic;
using System.Threading.Tasks;
using Meta.XR.MRUtilityKit;
using Storyverse.Data;
using Storyverse.Kingdom;
using Storyverse.Networking;
using TMPro;
using UnityEngine;

namespace Storyverse.Story
{
    public class ChronicleWall : MonoBehaviour
    {
        [SerializeField] Transform head;
        [SerializeField] Transform panelRoot;
        [SerializeField] ChroniclePanel panelPrefab;
        [SerializeField] GameObject freeStandingBanner;     // used when no wall is in view
        [SerializeField] Herald herald;
        [SerializeField] int maxPanels = 12;

        readonly Queue<ChroniclePanel> _panels = new();

        void OnEnable()
        {
            KingdomManager.Instance.OnChronicle += Add;
            KingdomManager.Instance.OnDashboard += LoadRecentOnce;
            if (MRUK.Instance != null) MRUK.Instance.RegisterSceneLoadedCallback(HangOnWall);
            else UseBanner();
        }
        void OnDisable()
        {
            if (!KingdomManager.Instance) return;
            KingdomManager.Instance.OnChronicle -= Add;
            KingdomManager.Instance.OnDashboard -= LoadRecentOnce;
        }

        bool _loaded;

        /// <summary>A new arrival should see the realm's recent history, not a blank wall. Loaded quietly (no Herald).</summary>
        async void LoadRecentOnce(Dashboard d)
        {
            if (_loaded || _panels.Count > 0) return;
            _loaded = true;
            try
            {
                var recent = await ApiClient.Instance.Get<List<StoryEventData>>($"/worlds/{d.World.Id}/chronicle?limit=8");
                for (int i = recent.Count - 1; i >= 0; i--) Add(recent[i], announce: false);   // newest last = top-left
            }
            catch (GameApiException e) { Debug.LogWarning($"[ChronicleWall] {e.Message}"); }
        }

        void HangOnWall()
        {
            var room = MRUK.Instance.GetCurrentRoom();
            MRUKAnchor best = null; float bestScore = float.MinValue;
            if (room != null)
                foreach (var wall in room.WallAnchors)
                {
                    // Prefer a wall the seated player faces, at a readable distance.
                    var to = wall.transform.position - head.position;
                    var score = Vector3.Dot(to.normalized, head.forward) * 2f - Mathf.Abs(to.magnitude - 2f);
                    if (score > bestScore) { bestScore = score; best = wall; }
                }
            if (best == null) { UseBanner(); return; }
            // Wall plane normal is the anchor's Z axis, pointing into the room.
            panelRoot.SetPositionAndRotation(best.transform.position + best.transform.forward * 0.02f + Vector3.up * (head.position.y - best.transform.position.y),
                                             Quaternion.LookRotation(-best.transform.forward, Vector3.up));
        }

        void UseBanner()
        {
            freeStandingBanner.SetActive(true);
            panelRoot.SetPositionAndRotation(freeStandingBanner.transform.position, freeStandingBanner.transform.rotation);
        }

        public void Add(StoryEventData e) => Add(e, announce: true);

        public void Add(StoryEventData e, bool announce)
        {
            var panel = Instantiate(panelPrefab, panelRoot);
            panel.Bind(e);
            _panels.Enqueue(panel);
            if (_panels.Count > maxPanels) Destroy(_panels.Dequeue().gameObject);
            Layout();
            if (announce && e.Importance >= 2) herald.Announce(e);
        }

        void Layout()
        {
            int i = 0;
            foreach (var p in _panels)
            {
                p.transform.localPosition = new Vector3((i % 4 - 1.5f) * 0.42f, (1 - i / 4) * 0.32f, 0);
                p.transform.localRotation = Quaternion.identity;
                i++;
            }
        }

        /// <summary>Judging alignment §1.2: on re-entry, ravens and the Herald replay what you missed.</summary>
        public async Task ReplaySince(int lastSeenTurn)
        {
            var km = KingdomManager.Instance;
            var report = await ApiClient.Instance.Since(km.KingdomId, lastSeenTurn);
            foreach (var e in report.Chronicle) Add(e);
            if (report.Chronicle.Count == 0) herald.Say("All was quiet while you were away, Your Majesty.");
        }
    }
}
