using System.Collections.Generic;
using System.Threading.Tasks;
using Storyverse.Data;
using TMPro;
using UnityEngine;

namespace Storyverse.Story
{
    /// <summary>Old Penn, the Herald. Text-to-speech or recorded VO can hook into OnSpeak.</summary>
    public class Herald : MonoBehaviour
    {
        [SerializeField] TMP_Text speechBubble;
        [SerializeField] AudioSource fanfare;
        [SerializeField] float secondsPerLine = 5f;
        public UnityEngine.Events.UnityEvent<string> OnSpeak = new();
        readonly Queue<string> _lines = new();
        bool _busy;

        public void Announce(StoryEventData e) => Say($"Hear ye! {e.Title}. {e.Description}");

        public async void Say(string line)
        {
            _lines.Enqueue(line);
            if (_busy) return;
            _busy = true;
            while (_lines.Count > 0)
            {
                var next = _lines.Dequeue();
                if (fanfare) fanfare.Play();
                speechBubble.text = next; speechBubble.gameObject.SetActive(true);
                OnSpeak.Invoke(next);
                await Task.Delay((int)(secondsPerLine * 1000));
            }
            speechBubble.gameObject.SetActive(false);
            _busy = false;
        }
    }
}
