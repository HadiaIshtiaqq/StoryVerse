// WorldMapManager (spec §5.2): renders the shared continent on the table: kingdom seats, buildings,
// and the treaty web as ribbons (blue = alliance, dashed red = war). Map coords (0..1) <-> local XZ.
using System.Collections.Generic;
using Storyverse.Data;
using Storyverse.Kingdom;
using UnityEngine;

namespace Storyverse.World
{
    public class RealmMap : MonoBehaviour
    {
        [System.Serializable] public class BuildingPrefab { public string type; public GameObject prefab; }

        [SerializeField] Transform mapRoot;                 // same transform TableAnchorPlacer scales to the table
        [SerializeField] GameObject seatPrefab;             // castle + banner; needs a KingdomSeat component
        [SerializeField] List<BuildingPrefab> buildingPrefabs;
        [SerializeField] Material allianceRibbon, warRibbon, passageRibbon;
        [SerializeField] float buildingScalePerLevel = 0.15f;

        readonly Dictionary<string, KingdomSeat> _seats = new();
        readonly Dictionary<string, GameObject> _buildings = new();
        readonly List<LineRenderer> _ribbons = new();

        public Transform Root => mapRoot;

        void OnEnable() { if (KingdomManager.Instance) KingdomManager.Instance.OnMap += Render; }
        void OnDisable() { if (KingdomManager.Instance) KingdomManager.Instance.OnMap -= Render; }

        public Vector3 MapToLocal(float x, float z) => new(x - 0.5f, 0f, 0.5f - z);
        public Vector3 MapToWorld(float x, float z) => mapRoot.TransformPoint(MapToLocal(x, z));
        public Vector2 WorldToMap(Vector3 world)
        {
            var p = mapRoot.InverseTransformPoint(world);
            return new Vector2(p.x + 0.5f, 0.5f - p.z);
        }

        public KingdomSeat Seat(string kingdomId) => _seats.TryGetValue(kingdomId, out var s) ? s : null;

        void Render(WorldMap map)
        {
            foreach (var k in map.Kingdoms)
            {
                if (!_seats.TryGetValue(k.Id, out var seat))
                {
                    seat = Instantiate(seatPrefab, mapRoot).GetComponent<KingdomSeat>();
                    _seats[k.Id] = seat;
                }
                seat.transform.localPosition = MapToLocal(k.MapX, k.MapY);
                seat.Bind(k, k.Id == KingdomManager.Instance.KingdomId);
            }

            var alive = new HashSet<string>();
            foreach (var b in map.Buildings)
            {
                alive.Add(b.Id);
                if (!_buildings.TryGetValue(b.Id, out var go))
                {
                    var prefab = buildingPrefabs.Find(p => p.type == b.BuildingType)?.prefab;
                    if (prefab == null) continue;
                    go = Instantiate(prefab, mapRoot);
                    _buildings[b.Id] = go;
                }
                go.transform.localPosition = MapToLocal(b.X, b.Z);
                go.transform.localRotation = Quaternion.Euler(0, b.RotationY, 0);
                go.transform.localScale = Vector3.one * (1f + buildingScalePerLevel * (b.Level - 1));
            }
            foreach (var id in new List<string>(_buildings.Keys))
                if (!alive.Contains(id)) { Destroy(_buildings[id]); _buildings.Remove(id); }

            foreach (var r in _ribbons) Destroy(r.gameObject);
            _ribbons.Clear();
            foreach (var a in map.Treaties.Alliances) Ribbon(a.A, a.B, allianceRibbon);
            foreach (var w in map.Treaties.Wars) Ribbon(w.Attacker, w.Defender, warRibbon);
            if (map.Treaties.Passages != null && passageRibbon != null)
                foreach (var p in map.Treaties.Passages) Ribbon(p.Grantor, p.Grantee, passageRibbon, 0.004f);   // open roads
        }

        void Ribbon(string a, string b, Material mat, float width = 0.008f)
        {
            if (!_seats.ContainsKey(a) || !_seats.ContainsKey(b)) return;
            var lr = new GameObject("Ribbon").AddComponent<LineRenderer>();
            lr.transform.SetParent(mapRoot, false);
            lr.useWorldSpace = false;
            lr.material = mat;
            lr.widthMultiplier = width;
            lr.positionCount = 2;
            lr.SetPosition(0, _seats[a].transform.localPosition + Vector3.up * 0.02f);
            lr.SetPosition(1, _seats[b].transform.localPosition + Vector3.up * 0.02f);
            _ribbons.Add(lr);
        }
    }
}
