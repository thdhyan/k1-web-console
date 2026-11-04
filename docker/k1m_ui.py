"""Streamlit front end for the K1 video -> motion retarget service.

SHARE THIS FILE. It is deliberately one file with two dependencies
(streamlit, requests) and no pipeline code, no model files and no credentials:
it is a client for the containerised service, so anyone can run

    pip install streamlit requests
    K1M_SERVICE_URL=http://<host>:7861 streamlit run k1m_ui.py

or just paste the sidebar URL in. Point it at your own instance and it works
against that.

WHY A SEPARATE UI
-----------------
The pipeline itself is heavy and lives in a container (GVHMR on one GPU host, GMR
on another, reached over ssh). Re-implementing any of that here would make this
file un-shareable. So this only does HTTP.

ONE THING TO KNOW BEFORE YOU TRUST THE OUTPUT
---------------------------------------------
`ok: false` does NOT mean the request failed. The service returns the retargeted
CSV even when the feasibility gate rejects the motion, because the CSV is what you
asked for and the gate is a separate opinion about whether a robot could track it.
The gate is a kinematic IK solve with no foot locking, no dynamics and no actuator
model, so a clean-looking motion can still be untrackable -- an early Macarena
render looked fine while asking AAHead_yaw for 9.58x its effort limit.

So: read the gate, not the render.
"""
from __future__ import annotations

import os

import requests
import streamlit as st

DEFAULT_SERVICE = os.environ.get("K1M_SERVICE_URL", "http://127.0.0.1:7861")
TIMEOUT_S = int(os.environ.get("K1M_TIMEOUT_S", "1800"))


@st.cache_data(ttl=30, show_spinner=False)
def _get(url: str, timeout: int = 20):
    try:
        r = requests.get(url, timeout=timeout)
        return r.status_code, (r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text)
    except Exception as exc:  # noqa: BLE001 - surface it in the UI, never crash
        return None, f"{type(exc).__name__}: {exc}"


@st.cache_data(ttl=30, show_spinner=False)
def _fetch(url: str, timeout: int = 60) -> bytes | None:
    try:
        r = requests.get(url, timeout=timeout)
        return r.content if r.ok else None
    except Exception:  # noqa: BLE001
        return None


def _rel(download: dict, key: str) -> str | None:
    """Turn the service's /artifact/... path into an absolute URL."""
    p = (download or {}).get(key)
    return f"{service.rstrip('/')}{p}" if p else None


st.set_page_config(page_title="K1 motion retarget", page_icon="🤖", layout="centered")

st.title("Human video → K1 joint motion")
st.caption(
    "Upload a clip of a person. GVHMR recovers the motion, GMR retargets it to the "
    "Booster K1's 22 joints, and the feasibility gate tells you whether a real robot "
    "could actually track the result."
)

# ---- sidebar: service + health ------------------------------------------------
service = st.sidebar.text_input("Service URL", DEFAULT_SERVICE, help="Where the k1m service is running.")
if st.sidebar.button("Check service", use_container_width=True):
    st.cache_data.clear()

code, health = _get(f"{service.rstrip('/')}/health")
if code == 200 and isinstance(health, dict) and health.get("ok"):
    st.sidebar.success("service up")
else:
    st.sidebar.error(f"service unreachable ({code})")
    st.sidebar.caption(str(health)[:200])
    st.info(f"No service at `{service}`. Start it with:\n\n"
            "`docker run -d -p 7861:7860 -v /root/k1m_ssh:/root/.ssh:ro "
            "-v ~/k1m_out:/data k1m-service:latest`")
    st.stop()

with st.expander("stage health"):
    code, doc = _get(f"{service.rstrip('/')}/doctor", timeout=90)
    if code == 200 and isinstance(doc, dict):
        for s in doc.get("stages", []):
            mark = "✅" if s.get("reachable") else "❌"
            st.write(f"{mark} **{s['stage']}** — `{s['host']}` {s.get('gpu', '')} {s.get('error', '')}")
    else:
        st.caption(str(doc)[:300])

# ---- inputs -------------------------------------------------------------------
video = st.file_uploader("Video of a person", type=["mp4", "mov", "avi", "mkv", "webm", "m4v"])

c1, c2 = st.columns(2)
fps = c1.number_input("Frames per second", min_value=1, max_value=120, value=30,
                      help="Must match the source clip, or every velocity the gate reports is wrong by a constant factor.")
seconds = c2.number_input("Seconds to use (0 = whole clip)", min_value=0.0, max_value=600.0, value=6.0, step=1.0,
                          help="Retargeting takes minutes per video. Start with a few seconds.")

c3, c4 = st.columns(2)
do_gate = c3.checkbox("Run the feasibility gate", value=True,
                      help="Strongly recommended. Off means the motion is unvalidated for hardware.")
do_render = c4.checkbox("Also render a replay video", value=False,
                        help="Needs a GL backend in the service container; usually off on CPU-only hosts.")

run = st.button("Retarget", type="primary", disabled=video is None)

# ---- run ----------------------------------------------------------------------
if run and video is not None:
    with st.spinner("Retargeting — GVHMR then GMR, this takes a minute or more per few seconds of clip…"):
        try:
            files = {"video": (video.name, video.getvalue(), "video/mp4")}
            data = {
                "fps": str(float(fps)), "seconds": str(float(seconds)),
                "do_gate": str(bool(do_gate)).lower(), "do_render": str(bool(do_render)).lower(),
            }
            r = requests.post(f"{service.rstrip('/')}/retarget", files=files, data=data, timeout=TIMEOUT_S)
            payload = r.json()
        except Exception as exc:  # noqa: BLE001
            st.error(f"{type(exc).__name__}: {exc}")
            st.stop()

    if not payload.get("ok") and "error" in payload:
        st.error(payload["error"][:800])
        st.stop()

    st.success(f"Retargeted in {payload.get('seconds')}s — "
               f"{payload.get('n_frames')} frames, stem `{payload.get('stem')}`")

    for w in payload.get("warnings") or []:
        st.caption(w)

    # ---- the gate: the part that decides hardware-readiness ------------------
    gate = payload.get("gate")
    if gate is None:
        st.warning("Gate was not run. This motion is **not** validated for hardware.")
    elif gate.get("pass"):
        st.success("Gate passed — the motion is within the K1's joint, velocity, "
                   "acceleration and torque limits.")
    else:
        st.error("Gate FAILED — the motion moves, but a real K1 could not track it.")
        st.caption(gate.get("summary", ""))
        failing = gate.get("failing_checks") or []
        if failing:
            st.dataframe(
                [{"check": c.get("check", "?"), "detail": c.get("detail", "")} for c in failing],
                use_container_width=True, hide_index=True,
            )
        st.info("Common causes: GVHMR has no foot locking (expect skating), and the "
                "solve has no dynamics, so fast limbs come out physically impossible. "
                "Slow the clip down, use a single full-body subject, or run SOMA "
                "foot-plant post-processing.")

    # ---- downloads -------------------------------------------------------------
    dl = payload.get("download") or {}
    csv_url, gate_url = _rel(dl, "csv"), _rel(dl, "gate_report")
    replay_url = _rel(dl, "replay_mp4")

    cols = st.columns(3)
    if csv_url and _fetch(csv_url):
        cols[0].download_button("⬇ Joint CSV", _fetch(csv_url),
                                file_name=f"{payload.get('stem')}_k1.csv", mime="text/csv",
                                use_container_width=True)
    if gate_url and _fetch(gate_url):
        cols[1].download_button("⬇ Gate report", _fetch(gate_url),
                                file_name=f"{payload.get('stem')}_gate.json", mime="application/json",
                                use_container_width=True)
    if replay_url and _fetch(replay_url):
        cols[2].download_button("⬇ Replay video", _fetch(replay_url),
                                file_name=f"{payload.get('stem')}_replay.mp4", mime="video/mp4",
                                use_container_width=True)

    st.divider()
    st.caption(
        "The CSV carries no fps, so a `.fps.txt` sidecar is written next to it — keep them "
        "together or every velocity you compute from the file is wrong by a constant factor. "
        "Columns are the K1's 22 joints plus a 7-component root pose, in "
        "`booster_assets.motions.K1_JOINT_NAMES` order."
    )
