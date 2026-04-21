# =============================================================
#  Author      : MAMADY CHEICK SOUARE
# =============================================================

import cv2
import sys
import wave
import threading
import subprocess
import os
from collections import deque
from datetime import datetime

try:
    import pyaudio
except ImportError:
    print("Missing dependency: pip install pyaudio")
    sys.exit(1)

# ── Config ────────────────────────────────────────────────────
CAMERA_INDEX   = 0
PRE_BUFFER_SEC = 10          # max seconds kept before R is pressed
FOURCC         = cv2.VideoWriter_fourcc(*"mp4v")

AUDIO_RATE     = 44100
AUDIO_CHANNELS = 1
AUDIO_CHUNK    = 1024
AUDIO_FORMAT   = pyaudio.paInt16

TMP_VIDEO      = "_tmp_video.mp4"
TMP_AUDIO      = "_tmp_audio.wav"
RECORDS_DIR    = "records"
os.makedirs(RECORDS_DIR, exist_ok=True)

# ── Camera setup ──────────────────────────────────────────────
cap = cv2.VideoCapture(CAMERA_INDEX)
if not cap.isOpened():
    print("Error: Could not open camera.")
    sys.exit(1)

# Warm up so FPS is readable
for _ in range(5):
    cap.read()

fps = cap.get(cv2.CAP_PROP_FPS)
if fps <= 0 or fps > 120:
    fps = 30.0
    print(f"Could not read FPS from camera, defaulting to {fps:.0f}")
else:
    print(f"Camera FPS: {fps:.1f}")

width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# ── Audio setup ───────────────────────────────────────────────
pa     = pyaudio.PyAudio()
stream = pa.open(format=AUDIO_FORMAT, channels=AUDIO_CHANNELS,
                 rate=AUDIO_RATE, input=True, frames_per_buffer=AUDIO_CHUNK)

# Rolling pre-roll buffers (filled while NOT recording)
audio_pre_maxlen = int(PRE_BUFFER_SEC * AUDIO_RATE / AUDIO_CHUNK) + 1
video_pre_maxlen = int(PRE_BUFFER_SEC * fps) + 1
audio_buffer     = deque(maxlen=audio_pre_maxlen)
video_buffer     = deque(maxlen=video_pre_maxlen)

print(f"Pre-roll buffer capacity: {PRE_BUFFER_SEC}s  "
      f"({video_pre_maxlen} frames / {audio_pre_maxlen} audio chunks)")

# ── Shared state ──────────────────────────────────────────────
recording      = False
stop_audio     = False
audio_lock     = threading.Lock()
recorded_audio = []          # fresh list assigned at each R press

# ── Audio thread ──────────────────────────────────────────────
def audio_worker():
    """
    Always running in the background.
    - recording=False  →  chunk goes into rolling pre-roll deque (capped at 10s)
    - recording=True   →  chunk appended to recorded_audio (unbounded, until S)
    """
    global stop_audio
    while not stop_audio:
        chunk = stream.read(AUDIO_CHUNK, exception_on_overflow=False)
        with audio_lock:
            if recording:
                recorded_audio.append(chunk)
            else:
                audio_buffer.append(chunk)

audio_thread = threading.Thread(target=audio_worker, daemon=True)
audio_thread.start()

# ── Main loop ─────────────────────────────────────────────────
writer = None

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Failed to capture frame.")
        break

    if recording and writer is not None:
        # ── Active recording: every frame goes straight to file ──
        writer.write(frame)
    else:
        # ── Standby: rolling window of up to PRE_BUFFER_SEC seconds ──
        video_buffer.append(frame)

    # HUD
    label = "● REC  (S = stop)" if recording else "● BUFFERING  (R = record)"
    color = (0, 0, 220)          if recording else (0, 180, 0)
    cv2.putText(frame, label, (14, 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2, cv2.LINE_AA)

    cv2.imshow("Recorder", frame)
    key = cv2.waitKey(1) & 0xFF

    # ── R : start ─────────────────────────────────────────────
    if key == ord('r') and not recording:
        writer = cv2.VideoWriter(TMP_VIDEO, FOURCC, fps, (width, height))

        # 1. Write all buffered video frames (= whatever was in the
        #    deque: up to 10s, or less if you waited fewer seconds)
        pre_video = list(video_buffer)
        for f in pre_video:
            writer.write(f)
        video_buffer.clear()

        # 2. Inside the lock: snapshot audio pre-roll, assign a FRESH
        #    list for this session, then flip the flag so audio_worker
        #    starts appending to it immediately
        with audio_lock:
            pre_audio      = list(audio_buffer)
            audio_buffer.clear()
            recorded_audio = pre_audio      # fresh list = pre-roll + future chunks
            recording      = True

        print(f"● Recording started  —  "
              f"{len(pre_video)/fps:.1f}s video pre-roll  /  "
              f"{len(pre_audio)*AUDIO_CHUNK/AUDIO_RATE:.1f}s audio pre-roll included.")
        print("  Press S to stop.")

    # ── S : stop ──────────────────────────────────────────────
    elif key == ord('s') and recording:

        # 1. Flip flag so audio_worker stops appending, grab everything
        with audio_lock:
            recording      = False
            final_audio    = recorded_audio     # reference to the full session list
            recorded_audio = []                 # ready for next session already

        # 2. Finalise video
        if writer:
            writer.release()
            writer = None

        # 3. Write WAV
        wf = wave.open(TMP_AUDIO, 'wb')
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(pa.get_sample_size(AUDIO_FORMAT))
        wf.setframerate(AUDIO_RATE)
        wf.writeframes(b''.join(final_audio))
        wf.close()

        # 4. Mux with FFmpeg → records/recording_TIMESTAMP.mp4
        timestamp   = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_file = os.path.join(RECORDS_DIR, f"recording_{timestamp}.mp4")

        print("  Muxing video and audio…")
        result = subprocess.run([
            "ffmpeg", "-y",
            "-i", TMP_VIDEO,
            "-i", TMP_AUDIO,
            "-c:v", "copy",
            "-c:a", "aac",
            output_file
        ], capture_output=True, text=True)

        if result.returncode == 0:
            os.remove(TMP_VIDEO)
            os.remove(TMP_AUDIO)
            print(f"  Saved → {output_file}")
        else:
            print("  ffmpeg error:")
            print(result.stderr)

        # 5. Pre-roll buffers are already empty and recorded_audio is
        #    already reset — ready to press R again immediately
        print("  Ready. Press R to record again.")

    # ── Q : quit ──────────────────────────────────────────────
    elif key == ord('q'):
        if recording:
            with audio_lock:
                recording = False
        if writer:
            writer.release()
        break

# ── Cleanup ───────────────────────────────────────────────────
stop_audio = True
audio_thread.join(timeout=2)
stream.stop_stream()
stream.close()
pa.terminate()
cap.release()
cv2.destroyAllWindows()