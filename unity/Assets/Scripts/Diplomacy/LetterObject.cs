// A sealed letter is a 3D object, not a flat panel (spec §4.7). A raven drops it on the table;
// gaze + pinch breaks the seal and unrolls it; reading marks it read on the server.
using Storyverse.Data;
using Storyverse.Kingdom;
using Storyverse.Networking;
using Storyverse.XR;
using TMPro;
using UnityEngine;

namespace Storyverse.Diplomacy
{
    [RequireComponent(typeof(GazeTarget))]
    public class LetterObject : MonoBehaviour
    {
        [SerializeField] GameObject sealedVisual, unrolledVisual;
        [SerializeField] TMP_Text subjectText, bodyText, fromText;
        [SerializeField] Renderer waxSeal;
        [SerializeField] AudioSource unrollSound;

        MessageData _message;

        public void Bind(MessageData m, string senderName, Color senderColor)
        {
            _message = m;
            subjectText.text = m.Subject;
            bodyText.text = m.Body;
            fromText.text = $"From {senderName} · turn {m.Turn}";
            waxSeal.material.color = senderColor;
            sealedVisual.SetActive(true); unrolledVisual.SetActive(false);
            GetComponent<GazeTarget>().OnSelect.AddListener(Open);
        }

        async void Open()
        {
            if (unrolledVisual.activeSelf) { Destroy(gameObject, 0.1f); return; }   // second pinch puts it away
            sealedVisual.SetActive(false); unrolledVisual.SetActive(true);
            if (unrollSound) unrollSound.Play();
            if (_message.Read) return;
            try { await ApiClient.Instance.Post<MessageData>($"/messages/{_message.Id}/read"); _message.Read = true; }
            catch (GameApiException e) { Debug.LogWarning(e.Message); }
        }
    }
}
