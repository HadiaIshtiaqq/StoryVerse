// Pinch with hysteresis so a wobbly pinch never fires twice (test XR-09), plus safe pause on tracking loss (XR-06/07).
// Requires: Meta XR Core SDK (OVRHand, OVRSkeleton).
using System;
using UnityEngine;

namespace Storyverse.XR
{
    public class PinchDetector : MonoBehaviour
    {
        [SerializeField] OVRHand hand;
        [SerializeField] OVRSkeleton skeleton;
        [Range(0.5f, 1f)] [SerializeField] float pinchOn = 0.85f;
        [Range(0f, 0.8f)] [SerializeField] float pinchOff = 0.55f;
        [Tooltip("Configurable sensitivity (spec §4.4 safeguards). Multiplies the thresholds.")]
        [Range(0.7f, 1.2f)] public float sensitivity = 1f;

        public bool IsPinching { get; private set; }
        public bool IsTracked => hand != null && hand.IsTracked && hand.HandConfidence == OVRHand.TrackingConfidence.High;
        public Vector3 PinchPoint { get; private set; }

        /// <summary>One id per pinch gesture: use it as the Idempotency-Key for whatever the pinch commits.</summary>
        public string GestureId { get; private set; }

        public event Action<PinchDetector> PinchStarted, PinchEnded, TrackingLost;

        bool _wasTracked = true;

        void Update()
        {
            if (!IsTracked)
            {
                if (_wasTracked) { _wasTracked = false; if (IsPinching) { IsPinching = false; TrackingLost?.Invoke(this); } }
                return;
            }
            _wasTracked = true;
            PinchPoint = MidpointOfThumbAndIndex();
            var strength = hand.GetFingerPinchStrength(OVRHand.HandFinger.Index);
            if (!IsPinching && strength >= pinchOn * sensitivity)
            {
                IsPinching = true; GestureId = Guid.NewGuid().ToString();
                PinchStarted?.Invoke(this);
            }
            else if (IsPinching && strength <= pinchOff * sensitivity)
            {
                IsPinching = false;
                PinchEnded?.Invoke(this);
            }
        }

        Vector3 MidpointOfThumbAndIndex()
        {
            if (skeleton == null || !skeleton.IsDataValid) return hand.PointerPose.position;
            // New Meta XR projects (v68+) default to the OpenXR hand skeleton (XRHand_* ids); older ones use Hand_*.
            Vector3? thumb = null, index = null;
            foreach (var bone in skeleton.Bones)
            {
                if (bone.Id == OVRSkeleton.BoneId.XRHand_ThumbTip || bone.Id == OVRSkeleton.BoneId.Hand_ThumbTip) thumb = bone.Transform.position;
                else if (bone.Id == OVRSkeleton.BoneId.XRHand_IndexTip || bone.Id == OVRSkeleton.BoneId.Hand_IndexTip) index = bone.Transform.position;
            }
            if (thumb == null || index == null) return hand.PointerPose.position;
            return (thumb.Value + index.Value) * 0.5f;
        }
    }
}
