// FoV-aware feedback: short messages float ~1 m ahead, inside a 30° cone of the gaze, and fade.
// Nothing important is ever placed at the periphery (judging alignment §3.1).
using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace Storyverse
{
    [DefaultExecutionOrder(-900)]   // ready before anything can fail and want to show a message
    public class Toasts : MonoBehaviour
    {
        static Toasts _instance;
        [SerializeField] Transform head;
        [SerializeField] TMP_Text template;
        [SerializeField] float distance = 0.9f, seconds = 4f, lowerBy = 0.18f;
        readonly Queue<string> _queue = new();
        bool _showing;

        void Awake() { _instance = this; template.gameObject.SetActive(false); }

        public static void Show(string message)
        {
            if (_instance == null) { Debug.Log($"[Toast] {message}"); return; }
            _instance._queue.Enqueue(message);
            if (!_instance._showing) _instance.StartCoroutine(_instance.Run());
        }

        IEnumerator Run()
        {
            _showing = true;
            while (_queue.Count > 0)
            {
                var text = Instantiate(template, transform);
                text.text = _queue.Dequeue();
                text.gameObject.SetActive(true);
                var forward = Vector3.ProjectOnPlane(head.forward, Vector3.up).normalized;
                text.transform.position = head.position + forward * distance - Vector3.up * lowerBy;
                text.transform.rotation = Quaternion.LookRotation(forward);
                for (float t = 0; t < seconds; t += Time.deltaTime)
                {
                    text.alpha = Mathf.Clamp01(Mathf.Min(t * 4f, (seconds - t) * 2f));
                    yield return null;
                }
                Destroy(text.gameObject);
            }
            _showing = false;
        }
    }
}
