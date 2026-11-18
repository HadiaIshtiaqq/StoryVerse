// Only for the PC preview: on the headset the real room (passthrough) is the council chamber.
using UnityEngine;

namespace Storyverse.World
{
    public class DesktopOnly : MonoBehaviour
    {
        void Start() => gameObject.SetActive(!UnityEngine.XR.XRSettings.isDeviceActive);
    }
}
