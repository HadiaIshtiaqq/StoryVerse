using Storyverse.Data;
using TMPro;
using UnityEngine;

namespace Storyverse.Story
{
    public class ChroniclePanel : MonoBehaviour
    {
        [SerializeField] TMP_Text title, body, footer;
        [SerializeField] Renderer frame;
        [SerializeField] Color normal = new(0.78f, 0.63f, 0.36f), dramatic = new(0.51f, 0.24f, 0.26f);

        public void Bind(StoryEventData e)
        {
            title.text = e.Title; body.text = e.Description; footer.text = $"Turn {e.Turn}";
            frame.material.color = e.Importance >= 3 ? dramatic : normal;
        }
    }
}
