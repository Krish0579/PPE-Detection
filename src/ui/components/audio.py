"""Browser audio alerts: a generated two-tone chime and the playback bridge
needed to satisfy autoplay policies."""

from __future__ import annotations

import base64
import functools
import io
import math
import struct

import streamlit.components.v1 as st_components


@functools.lru_cache(maxsize=1)
def _get_chime_wav_b64() -> str:
    """Generate a crisp, two-tone safety notification in PCM WAV format."""
    sample_rate = 22050
    duration = 0.38  # 380ms total
    num_samples = int(sample_rate * duration)
    buf = io.BytesIO()
    # RIFF header
    buf.write(b"RIFF")
    buf.write(struct.pack("<I", 36 + num_samples * 2))
    buf.write(b"WAVEfmt ")
    buf.write(struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16))
    buf.write(b"data")
    buf.write(struct.pack("<I", num_samples * 2))

    for i in range(num_samples):
        t = i / sample_rate
        # Tone 1: 880Hz (A5) for 140ms, Tone 2: 587.33Hz (D5) harmonic resolution
        if t < 0.14:
            phase = 2 * math.pi * 880.0 * t
        else:
            phase = 2 * math.pi * 880.0 * 0.14 + 2 * math.pi * 587.33 * (t - 0.14)
        decay = math.exp(-5.2 * t)
        sample = int(0.75 * math.sin(phase) * decay * 32767)
        buf.write(struct.pack("<h", max(-32768, min(32767, sample))))

    return base64.b64encode(buf.getvalue()).decode("ascii")


def play_violation_chime() -> None:
    """Play an immediate safety notification in the user's browser."""
    wav_b64 = _get_chime_wav_b64()
    chime_html = f"""
    <audio autoplay="autoplay" style="display:none;" preload="auto">
        <source src="data:audio/wav;base64,{wav_b64}" type="audio/wav">
    </audio>
    <script>
    (function() {{
        var wav = "{wav_b64}";
        // 1. Try local Audio element
        try {{
            var snd = new Audio("data:audio/wav;base64," + wav);
            snd.volume = 0.85;
            var p = snd.play();
            if (p && p.catch) p.catch(function(e) {{}});
        }} catch(e) {{}}

        // 2. Dispatch cross-window message to top-level window context
        try {{
            if (window.parent && window.parent !== window) {{
                window.parent.postMessage({{type: 'safesight_play_chime', audio: wav}}, '*');
                if (window.parent.Audio) {{
                    var pSnd = new window.parent.Audio("data:audio/wav;base64," + wav);
                    pSnd.volume = 0.85;
                    var p2 = pSnd.play();
                    if (p2 && p2.catch) p2.catch(function(e) {{}});
                }}
            }}
        }} catch(e) {{}}
    }})();
    </script>
    """
    st_components.html(chime_html, height=0, width=0)


def render_audio_alert_script(active: bool = False) -> None:
    """Prepare audio playback infrastructure and unlock Web Audio API on first user gesture."""
    if not active:
        return
    # Pre-warm the cache so audio generation is instantaneous
    _get_chime_wav_b64()
    # Install listener in host page to bypass iframe autoplay sandboxes
    st_components.html(
        """
        <script>
        (function() {
            if (window._safesight_audio_bridge_ready) return;
            window._safesight_audio_bridge_ready = true;

            function unlock() {
                try {
                    var ctx = new (window.AudioContext || window.webkitAudioContext)();
                    if (ctx && ctx.state === 'suspended') ctx.resume();
                } catch(e) {}
                window.removeEventListener('click', unlock);
                window.removeEventListener('keydown', unlock);
            }
            window.addEventListener('click', unlock);
            window.addEventListener('keydown', unlock);

            window.addEventListener('message', function(ev) {
                if (ev.data && ev.data.type === 'safesight_play_chime' && ev.data.audio) {
                    try {
                        var a = new Audio('data:audio/wav;base64,' + ev.data.audio);
                        a.volume = 0.85;
                        var p = a.play();
                        if (p && p.catch) p.catch(function() {});
                    } catch(e) {}
                }
            });
        })();
        </script>
        """,
        height=0,
        width=0,
    )
