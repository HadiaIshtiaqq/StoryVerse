// Puts the Realm Map on the player's REAL table (passthrough), keeps it there between sessions with a
// persistent spatial anchor, and degrades gracefully in rooms we never tested (judging alignment §1, §3.3).
//
// Requires: Meta XR Core SDK (OVRSpatialAnchor) + Meta MR Utility Kit (MRUK).
// API names target Meta XR SDK v71+ / MRUK v71+. Verify against the versions you install in Phase 1.
using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Meta.XR.MRUtilityKit;
using UnityEngine;

namespace Storyverse.XR
{
    public class TableAnchorPlacer : MonoBehaviour
    {
        [Tooltip("Root of the Realm Map. Its local XZ plane is the map; 1 unit = full map width before scaling.")]
        [SerializeField] Transform mapRoot;
        [Tooltip("Virtual pedestal table used when the room has no usable table.")]
        [SerializeField] GameObject fallbackPedestal;
        [SerializeField] Transform head;
        [SerializeField] float hoverAboveSurface = 0.05f;
        [SerializeField] float minTableSize = 0.6f, maxMapSize = 1.2f, fallbackMapSize = 0.9f;
        [SerializeField] float seatedTableHeight = 0.72f;
        [Tooltip("Head-to-map-centre distance for the virtual pedestal (m).")]
        [SerializeField] float pedestalDistance = 0.85f;

        const string AnchorKey = "sv_map_anchor";
        public event Action<string> OnPlaced; // "anchor" | "table" | "pedestal"

        /// <summary>Set once the map is on a surface. Listeners that subscribe late (onboarding starts after
        /// login) read this instead of waiting for an event that already fired.</summary>
        public string PlacedMode { get; private set; }
        public bool IsPlaced => PlacedMode != null;

        void Placed(string mode)
        {
            PlacedMode = mode;
            OnPlaced?.Invoke(mode);
        }

        [Tooltip("If room data hasn't arrived by then (permission denied, Space Setup never run), use the pedestal.")]
        [SerializeField] float sceneTimeoutSeconds = 8f;

        static bool HeadsetRunning => UnityEngine.XR.XRSettings.isDeviceActive;

        async void Start()
        {
            // No headset (PC preview): MRUK would load its sample room and put the map on a virtual table metres
            // away, and spatial anchors can't be created. Use the seated pedestal right in front of the camera.
            if (!HeadsetRunning) { PlaceOnPedestal("desktop preview (no headset)"); return; }

            try { if (await TryRestoreAnchor()) { Placed("anchor"); return; } }
            catch (Exception e) { Debug.LogWarning($"[TableAnchorPlacer] Could not restore anchor: {e.Message}"); }

            if (MRUK.Instance == null) { PlaceOnPedestal("MRUK missing"); return; }
            MRUK.Instance.RegisterSceneLoadedCallback(() => { if (!IsPlaced) PlaceFromScene(); });
            await Task.Delay(TimeSpan.FromSeconds(sceneTimeoutSeconds));
            if (this && !IsPlaced) PlaceOnPedestal("no room data in time");
        }

        // ---- 1. returning player: restore the saved anchor -------------------------------------------------
        async Task<bool> TryRestoreAnchor()
        {
            var saved = PlayerPrefs.GetString(AnchorKey, "");
            if (!Guid.TryParse(saved, out var uuid)) return false;
            var unbound = new List<OVRSpatialAnchor.UnboundAnchor>();
            var result = await OVRSpatialAnchor.LoadUnboundAnchorsAsync(new[] { uuid }, unbound);
            if (!result.Success || unbound.Count == 0) return false;
            var anchor = unbound[0];
            if (!await anchor.LocalizeAsync()) return false;
            var go = new GameObject("RealmMapAnchor");
            var spatial = go.AddComponent<OVRSpatialAnchor>();
            anchor.BindTo(spatial);
            AttachMap(go.transform, PlayerPrefs.GetFloat(AnchorKey + "_size", fallbackMapSize));
            return true;
        }

        // ---- 2. first run: find the largest table via scene understanding ---------------------------------
        void PlaceFromScene()
        {
            var room = MRUK.Instance.GetCurrentRoom();
            if (room == null) { PlaceOnPedestal("no room data (Space Setup skipped)"); return; }

            MRUKAnchor best = null; float bestArea = 0;
            foreach (var a in room.Anchors)
            {
                if (!a.HasAnyLabel(MRUKAnchor.SceneLabels.TABLE) || !a.PlaneRect.HasValue) continue;
                var area = a.PlaneRect.Value.width * a.PlaneRect.Value.height;
                if (area > bestArea) { bestArea = area; best = a; }
            }
            if (best == null) { PlaceOnPedestal("no table detected"); return; }

            var rect = best.PlaneRect.Value;
            var shortSide = Mathf.Min(rect.width, rect.height);
            if (shortSide < minTableSize * 0.5f) { PlaceOnPedestal("table too small"); return; }
            // A plane anchor's normal is its local Z. Keep the map level and yaw it to the table's long edge.
            var position = best.transform.position + Vector3.up * hoverAboveSurface;
            var edge = rect.width >= rect.height ? best.transform.right : best.transform.up;
            var rotation = Quaternion.LookRotation(Vector3.ProjectOnPlane(edge, Vector3.up).normalized, Vector3.up);
            var size = Mathf.Clamp(shortSide * 0.9f, 0.35f, maxMapSize);
            _ = CreateAnchorAndAttach(position, rotation, size, "table");
        }

        // ---- 3. fallback: virtual pedestal in front of a seated player ---------------------------------------
        void PlaceOnPedestal(string reason)
        {
            Debug.Log($"[TableAnchorPlacer] Using virtual pedestal: {reason}");
            var forward = Vector3.ProjectOnPlane(head.forward, Vector3.up).normalized;
            // The map centre sits far enough out that the Diplomatic Desk (on the map's near edge) lands in the
            // player's lap instead of behind their eyes.
            var position = new Vector3(head.position.x, seatedTableHeight, head.position.z) + forward * pedestalDistance;
            if (fallbackPedestal != null)
            {
                fallbackPedestal.SetActive(true);
                fallbackPedestal.transform.SetPositionAndRotation(position - Vector3.up * hoverAboveSurface, Quaternion.LookRotation(forward));
            }
            _ = CreateAnchorAndAttach(position, Quaternion.LookRotation(forward), fallbackMapSize, "pedestal");
        }

        async Task CreateAnchorAndAttach(Vector3 position, Quaternion rotation, float size, string mode)
        {
            var go = new GameObject("RealmMapAnchor");
            go.transform.SetPositionAndRotation(position, rotation);
            if (!HeadsetRunning) { AttachMap(go.transform, size); Placed(mode); return; }
            var anchor = go.AddComponent<OVRSpatialAnchor>();
            AttachMap(go.transform, size);
            Placed(mode);                                   // the map is visible now; persisting is a bonus
            try
            {
                if (await anchor.WhenLocalizedAsync())
                {
                    var save = await anchor.SaveAnchorAsync();
                    if (save.Success)
                    {
                        PlayerPrefs.SetString(AnchorKey, anchor.Uuid.ToString());
                        PlayerPrefs.SetFloat(AnchorKey + "_size", size);
                        PlayerPrefs.Save();
                    }
                }
            }
            catch (Exception e) { Debug.LogWarning($"[TableAnchorPlacer] Anchor not saved ({e.Message}); the map stays put this session"); }
        }

        void AttachMap(Transform anchor, float size)
        {
            mapRoot.SetParent(anchor, false);
            mapRoot.localPosition = Vector3.zero;
            mapRoot.localRotation = Quaternion.identity;
            mapRoot.localScale = Vector3.one * size;
        }

        /// <summary>"Re-place your realm": called from the settings menu or when tracking of the table is lost.</summary>
        public void ForgetAndReplace()
        {
            PlayerPrefs.DeleteKey(AnchorKey);
            mapRoot.SetParent(null, true);
            if (MRUK.Instance != null) PlaceFromScene(); else PlaceOnPedestal("manual re-place");
        }
    }
}
