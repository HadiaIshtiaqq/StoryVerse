// A kingdom's capital on the map. It is also a gaze target: look at it to see its name and standing;
// gaze + pinch selects it as the target of the Diplomatic Desk.
using Storyverse.Data;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.World
{
    [RequireComponent(typeof(GazeTarget))]
    public class KingdomSeat : MonoBehaviour
    {
        [SerializeField] TMP_Text nameLabel;
        [SerializeField] Renderer bannerRenderer;
        [SerializeField] GameObject myRealmHalo;
        [Tooltip("Radius of the buildable border in map units (backend MAX_BUILD_RADIUS).")]
        [SerializeField] float borderRadius = 0.22f;
        [SerializeField] Transform borderRing;

        public string KingdomId { get; private set; }
        public string KingdomName { get; private set; }
        public static event System.Action<KingdomSeat> OnSelected;

        void Awake() => GetComponent<GazeTarget>().OnSelect.AddListener(() => OnSelected?.Invoke(this));

        public void Bind(MapKingdom k, bool mine)
        {
            KingdomId = k.Id; KingdomName = k.Name;
            nameLabel.text = k.IsNpc ? $"{k.Name}\n<size=60%>NPC ruler</size>" : k.Name;
            var crest = ArtLibrary.Crest(k.Name);                  // the kingdom's heraldic banner
            if (crest != null) ArtLibrary.Show(bannerRenderer, crest);
            else if (ColorUtility.TryParseHtmlString(k.Color, out var c)) bannerRenderer.material.color = c;
            myRealmHalo.SetActive(mine);
            if (borderRing)
            {
                borderRing.gameObject.SetActive(mine);
                // Widen the ring to the build radius, but keep its thickness: scaling Y too turned the flat ring
                // into a column taller than the castle.
                var d = borderRadius * 2f;
                borderRing.localScale = new Vector3(d, borderRing.localScale.y, d);
            }
        }
    }
}
