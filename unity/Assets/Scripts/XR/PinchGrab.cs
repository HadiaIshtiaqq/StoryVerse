// Minimal direct grab: pinch near the object to pick it up, release the pinch to drop it.
// Used for the gift chests (drag one onto the envoy plate). If you adopt ISDK grabbables, remove this.
using UnityEngine;

namespace Storyverse.XR
{
    [RequireComponent(typeof(Rigidbody))]
    public class PinchGrab : MonoBehaviour
    {
        [SerializeField] PinchDetector[] pinchers;
        [SerializeField] float grabRadius = 0.06f;

        /// <summary>True while any grabbable is in a hand (GazeSelector ignores that pinch).</summary>
        public static bool AnyHeld => _held > 0;
        static int _held;

        Rigidbody _body;
        PinchDetector _holder;
        Vector3 _offset;
        bool _wasKinematic;

        void Awake() => _body = GetComponent<Rigidbody>();

        void OnEnable()
        {
            if (pinchers == null) return;
            foreach (var p in pinchers) { p.PinchStarted += TryGrab; p.PinchEnded += Release; p.TrackingLost += Release; }
        }

        void OnDisable()
        {
            if (_holder != null) Release(_holder);
            if (pinchers == null) return;
            foreach (var p in pinchers) { p.PinchStarted -= TryGrab; p.PinchEnded -= Release; p.TrackingLost -= Release; }
        }

        void TryGrab(PinchDetector hand)
        {
            if (_holder != null) return;
            var closest = _body.ClosestPointOnBounds(hand.PinchPoint);
            if (Vector3.Distance(closest, hand.PinchPoint) > grabRadius) return;
            _holder = hand; _held++;
            _offset = transform.position - hand.PinchPoint;
            _wasKinematic = _body.isKinematic;
            _body.isKinematic = true;
        }

        void Release(PinchDetector hand)
        {
            if (hand != _holder) return;
            _holder = null; _held = Mathf.Max(0, _held - 1);
            _body.isKinematic = _wasKinematic;
        }

        void LateUpdate()
        {
            if (_holder != null) transform.position = _holder.PinchPoint + _offset;
        }
    }
}
