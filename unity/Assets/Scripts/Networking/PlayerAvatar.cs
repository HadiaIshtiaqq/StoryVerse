#if STORYVERSE_FUSION // Requires Photon Fusion 2; see MultiplayerManager.cs
// Remote rulers sit around YOUR real table: poses are synced in Realm-Map-local space, so each player's
// avatar appears at the right place relative to every other player's map, wherever their table is.
using Fusion;
using Storyverse.World;
using TMPro;
using UnityEngine;

namespace Storyverse.Networking
{
    public class PlayerAvatar : NetworkBehaviour
    {
        [Networked] public Vector3 HeadPos { get; set; }
        [Networked] public Quaternion HeadRot { get; set; }
        [Networked] public Vector3 LeftHandPos { get; set; }
        [Networked] public Vector3 RightHandPos { get; set; }
        [Networked] public Vector3 PointTarget { get; set; }       // where this ruler is pointing on the map
        [Networked] public NetworkBool Pointing { get; set; }
        [Networked] public NetworkString<_32> KingdomName { get; set; }
        [Networked] public NetworkString<_16> KingdomColor { get; set; }

        [SerializeField] Transform headVisual, leftVisual, rightVisual, pointMarker;
        [SerializeField] TMP_Text nameplate;
        [SerializeField] Renderer[] tinted;

        Transform _localHead, _localLeft, _localRight;
        RealmMap _map;

        public void Init(string kingdomName, string color)
        {
            KingdomName = kingdomName;
            KingdomColor = color;
        }

        public override void Spawned()
        {
            _map = FindFirstObjectByType<RealmMap>();
            if (HasStateAuthority)
            {
                var rig = FindFirstObjectByType<OVRCameraRig>();
                _localHead = rig.centerEyeAnchor; _localLeft = rig.leftHandAnchor; _localRight = rig.rightHandAnchor;
                foreach (var r in GetComponentsInChildren<Renderer>()) r.enabled = false;   // don't render yourself
            }
        }

        public override void FixedUpdateNetwork()
        {
            if (!HasStateAuthority || _map == null) return;
            var root = _map.Root;
            HeadPos = root.InverseTransformPoint(_localHead.position);
            HeadRot = Quaternion.Inverse(root.rotation) * _localHead.rotation;
            LeftHandPos = root.InverseTransformPoint(_localLeft.position);
            RightHandPos = root.InverseTransformPoint(_localRight.position);
        }

        /// <summary>Called by the local pointing gesture (point + hold) to ping a spot on the map for others.</summary>
        public void SetPointing(bool on, Vector3 worldTarget)
        {
            if (!HasStateAuthority || _map == null) return;
            Pointing = on;
            PointTarget = _map.Root.InverseTransformPoint(worldTarget);
        }

        public override void Render()
        {
            if (HasStateAuthority || _map == null) return;
            var root = _map.Root;
            headVisual.SetPositionAndRotation(root.TransformPoint(HeadPos), root.rotation * HeadRot);
            leftVisual.position = root.TransformPoint(LeftHandPos);
            rightVisual.position = root.TransformPoint(RightHandPos);
            pointMarker.gameObject.SetActive(Pointing);
            if (Pointing) pointMarker.position = root.TransformPoint(PointTarget);
            nameplate.text = KingdomName.ToString();
            if (ColorUtility.TryParseHtmlString(KingdomColor.ToString(), out var c))
                foreach (var r in tinted) r.material.color = c;
        }
    }
}

#endif
