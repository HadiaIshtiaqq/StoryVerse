// Hold your palm on a seal for N seconds to confirm actions that are hard to undo (war, gifts, loans, betrayal).
// Spec §4.4 safeguard: "Use dwell or confirmation interactions for destructive actions."
using UnityEngine;
using UnityEngine.Events;
using UnityEngine.UI;

namespace Storyverse.XR
{
    [RequireComponent(typeof(Collider))]
    public class PalmHoldConfirm : MonoBehaviour
    {
        [SerializeField] float holdSeconds = 1f;
        [SerializeField] Image progressRing;            // world-space radial fill
        [SerializeField] AudioSource waxSound;
        [Tooltip("Tag on the palm trigger colliders attached to each hand.")]
        [SerializeField] string palmTag = "Palm";
        public UnityEvent OnConfirmed = new();
        public bool Armed { get; set; } = true;

        float _held; int _palms; bool _fired;

        void OnTriggerEnter(Collider other) { if (other.CompareTag(palmTag)) _palms++; }
        void OnTriggerExit(Collider other) { if (other.CompareTag(palmTag)) _palms = Mathf.Max(0, _palms - 1); }

        void Update()
        {
            if (!Armed || _palms == 0) { _held = 0; _fired = false; }
            else if (!_fired && (_held += Time.deltaTime) >= holdSeconds)
            {
                _fired = true;
                if (waxSound) waxSound.Play();
                OnConfirmed.Invoke();
            }
            if (progressRing) progressRing.fillAmount = _fired ? 1 : _held / holdSeconds;
        }
    }
}
