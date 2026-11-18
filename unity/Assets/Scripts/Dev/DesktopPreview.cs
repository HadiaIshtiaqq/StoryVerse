// Play and inspect the VR scene on a PC with no headset.
// Active only when no XR device is running. Seats the camera at the table and maps the mouse onto the VR verbs:
//   left-click  = look + pinch (select a kingdom, open a letter, read the gauge) or palm-hold a seal (desk, envoy, turn)
//   right-drag  = look around      E = end turn      A / R = accept / refuse the first proposal on the Envoy's Scroll
// Command line: -screenshot <file.png> saves a picture after the realm loads, then quits (used for visual checks).
using System;
using System.Linq;
using System.Threading.Tasks;
using Storyverse.Diplomacy;
using Storyverse.Kingdom;
using Storyverse.XR;
using UnityEngine;

namespace Storyverse.Dev
{
    [DefaultExecutionOrder(-500)]   // seat the camera before TableAnchorPlacer reads the head position
    public class DesktopPreview : MonoBehaviour
    {
        [SerializeField] Transform rig;                 // OVRCameraRig root (the rig rewrites its anchors, so move the root)
        [SerializeField] Camera eye;
        [SerializeField] Vector3 seat = new(0f, 1.18f, -0.30f);
        [SerializeField] Vector2 startLook = new(38f, 0f);   // pitch down at the table, yaw straight ahead
        [SerializeField] float lookSpeed = 3f;

        Vector2 _look;
        bool _active;

        static bool HeadsetRunning => UnityEngine.XR.XRSettings.isDeviceActive;

        void Awake()
        {
            // Awake, not Start: TableAnchorPlacer.Start places the pedestal relative to the head, so the seat must
            // already be set. Pedestal faces head-forward on the floor plane, which is unaffected by our pitch.
            _active = !HeadsetRunning;
            if (!_active) return;
            _look = startLook;
            var look = Arg("-look");                                 // e.g. -look 60,0 for a screenshot of the desk
            if (look != null && look.Split(',') is { Length: 2 } p &&
                float.TryParse(p[0], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var pitch) &&
                float.TryParse(p[1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var yaw))
                _look = new Vector2(pitch, yaw);
            Apply();
        }

        void Start()
        {
            if (!_active) { enabled = false; return; }
            eye.fieldOfView = 60f;                                   // the rig assumes a 90° headset lens
            eye.clearFlags = CameraClearFlags.SolidColor;
            eye.backgroundColor = new Color(0.09f, 0.12f, 0.17f);   // no passthrough on a PC: a dark room instead
            Toasts.Show("Desktop preview: click = look+pinch · right-drag = look · E = end turn · A/R = answer envoy");
            var shot = Arg("-screenshot");
            if (shot != null) _ = Screenshot(shot);
        }

        void Apply()
        {
            rig.SetPositionAndRotation(seat, Quaternion.identity);
            // Rotate the rig so the (identity) eye anchor ends up looking where the mouse says.
            rig.rotation = Quaternion.Euler(_look.x, _look.y, 0f);
        }

        void Update()
        {
            if (!_active) return;
            if (Input.GetMouseButton(1))
            {
                _look += new Vector2(-Input.GetAxis("Mouse Y"), Input.GetAxis("Mouse X")) * lookSpeed;
                _look.x = Mathf.Clamp(_look.x, -60f, 85f);
                Apply();
            }
            if (Input.GetMouseButtonDown(0)) Click();
            if (Input.GetKeyDown(KeyCode.E)) _ = EndTurn();
            if (Input.GetKeyDown(KeyCode.A)) _ = Answer(true);
            if (Input.GetKeyDown(KeyCode.R)) _ = Answer(false);
        }

        void Click()
        {
            var ray = eye.ScreenPointToRay(Input.mousePosition);
            if (!Physics.Raycast(ray, out var hit, 10f, ~0, QueryTriggerInteraction.Collide)) return;
            var seal = hit.collider.GetComponentInParent<PalmHoldConfirm>();
            if (seal != null)
            {
                if (seal.Armed) seal.OnConfirmed.Invoke();
                else Toasts.Show("That seal is locked right now.");
                return;
            }
            var target = hit.collider.GetComponentInParent<GazeTarget>();
            if (target != null) { target.Hover(); target.Select(); }
        }

        static async Task EndTurn()
        {
            try
            {
                var r = await KingdomManager.Instance.AdvanceTurn();
                Toasts.Show(r.Advanced ? $"Turn {r.Turn} begins." : $"Waiting for: {string.Join(", ", r.WaitingFor)}");
            }
            catch (Networking.GameApiException e) { Toasts.Show(e.Message); }
        }

        static async Task Answer(bool accept)
        {
            var tray = FindFirstObjectByType<ProposalTray>();
            if (tray == null || tray.PendingCount == 0) { Toasts.Show("No envoys are waiting."); return; }
            await tray.AnswerFirst(accept);
        }

        async Task Screenshot(string path)
        {
            var km = KingdomManager.Instance;
            var end = Time.realtimeSinceStartup + 40f;
            while ((km.Dashboard == null || km.Map == null) && Time.realtimeSinceStartup < end) await Task.Delay(200);
            await Task.Delay(2500);                                  // let seats, buildings and labels appear
            var pick = Arg("-select");                               // e.g. -select Aurelia: open the desk on that court
            if (pick != null)
            {
                var seat = FindObjectsByType<World.KingdomSeat>(FindObjectsSortMode.None)
                    .FirstOrDefault(s => string.Equals(s.KingdomName, pick, StringComparison.OrdinalIgnoreCase));
                if (seat != null) { seat.GetComponent<GazeTarget>().Select(); await Task.Delay(800); }
            }
            var map = FindFirstObjectByType<World.RealmMap>();
            Debug.Log($"[DesktopPreview] eye {eye.transform.position} fwd {eye.transform.forward} fov {eye.fieldOfView} | rig {rig.position} | " +
                      $"map {(map ? map.Root.position.ToString() : "none")} scale {(map ? map.Root.lossyScale.x : 0f):0.00} parent {(map && map.Root.parent ? map.Root.parent.name : "none")}");
            ScreenCapture.CaptureScreenshot(path);
            await Task.Delay(1500);
            Debug.Log($"[DesktopPreview] Screenshot saved to {path}");
            Application.Quit(0);
        }

        static string Arg(string name)
        {
            var args = Environment.GetCommandLineArgs();
            var i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }
    }
}
