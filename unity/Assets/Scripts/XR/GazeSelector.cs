// Gaze + pinch: look at a target to highlight it, pinch (either hand, anywhere) to select it.
// Uses OVREyeGaze when eye tracking is available and permitted, otherwise head gaze.
// If you use ISDK's gaze interactors instead, disable this component and wire their events to GazeTarget.
using Storyverse.Buildings;
using UnityEngine;

namespace Storyverse.XR
{
    public class GazeSelector : MonoBehaviour
    {
        [SerializeField] OVREyeGaze eyeGaze;            // optional
        [SerializeField] Transform head;
        [SerializeField] PinchDetector[] pinchers;
        [SerializeField] float maxDistance = 4f;
        [Tooltip("Ignore pinches while the hand is near a grabbable/building tray (direct manipulation wins).")]
        [SerializeField] BuildingPlacementManager placement;
        [SerializeField] LayerMask gazeLayers = ~0;
        [SerializeField] float dwellToSelectSeconds = 0f;  // >0 enables dwell selection (accessibility)

        GazeTarget _current;
        float _dwell;

        void OnEnable() { foreach (var p in pinchers) p.PinchStarted += OnPinch; }
        void OnDisable() { foreach (var p in pinchers) p.PinchStarted -= OnPinch; }

        void Update()
        {
            var useEyes = eyeGaze != null && eyeGaze.EyeTrackingEnabled && eyeGaze.Confidence > 0.5f;
            var origin = useEyes ? eyeGaze.transform.position : head.position;
            var dir = useEyes ? eyeGaze.transform.forward : head.forward;
            GazeTarget hit = null;
            if (Physics.SphereCast(origin, 0.01f, dir, out var info, maxDistance, gazeLayers, QueryTriggerInteraction.Collide))
                hit = info.collider.GetComponentInParent<GazeTarget>();

            if (hit != _current)
            {
                if (_current) _current.Unhover();
                _current = hit; _dwell = 0;
                if (_current) _current.Hover();
            }
            if (_current && dwellToSelectSeconds > 0 && (_dwell += Time.deltaTime) >= dwellToSelectSeconds)
            {
                _dwell = float.NegativeInfinity;
                _current.Select();
            }
        }

        bool _pendingSelect;

        // The same pinch also reaches BuildingCard (grab from the tray) and PinchGrab (gift chests), in no fixed
        // order. Decide at the end of the frame: if that pinch picked something up, it was not a gaze selection.
        void OnPinch(PinchDetector _) => _pendingSelect = true;

        void LateUpdate()
        {
            if (!_pendingSelect) return;
            _pendingSelect = false;
            if (placement != null && placement.IsPlacing) return;
            if (PinchGrab.AnyHeld) return;
            if (_current) _current.Select();
        }
    }
}
