# camera-recorder
A lightweight Python screen recorder that captures webcam footage with synchronized audio, includes a 10-second pre-roll buffer, and saves timestamped .mp4 files to a local records/ folder.

# Camera Recorder

![Python](https://img.shields.io/badge/Python-3.8+-green) ![OpenCV](https://img.shields.io/badge/OpenCV-blue) ![FFmpeg](https://img.shields.io/badge/FFmpeg-orange)

A lightweight Python webcam recorder with synchronized audio, a 10-second pre-roll buffer, and timestamped `.mp4` output saved to a local `records/` folder.

## Features

- **10s pre-roll buffer** — video & audio captured before you press record are included automatically
- **Synced audio** — microphone input is captured in parallel and muxed into the final video via FFmpeg
- **Auto-organized output** — recordings saved to `records/` with timestamped filenames
- **Keyboard controlled** — no GUI overhead, start/stop/quit with single keystrokes

## Requirements

```bash
pip install opencv-python pyaudio
```

FFmpeg must be installed and on your system `PATH`.
- macOS: `brew install ffmpeg`
- Ubuntu: `sudo apt install ffmpeg`

> **Windows users:** `pyaudio` may need a pre-built wheel — `pip install pipwin && pipwin install pyaudio`

## Usage

```bash
python recorder.py
```

## Controls

| Key | Action |
|-----|--------|
| `R` | Start recording (includes pre-roll buffer) |
| `S` | Stop recording and save file |
| `Q` | Quit |

## Output

Recordings are saved inside `records/` (created automatically):

```
records/
├── recording_2025-04-21_14-03-22.mp4
└── recording_2025-04-21_14-11-05.mp4
```

## Configuration

Edit the constants at the top of `recorder.py`:

```python
CAMERA_INDEX   = 0      # webcam device index
PRE_BUFFER_SEC = 10     # seconds of pre-roll to keep
AUDIO_RATE     = 44100  # audio sample rate (Hz)
AUDIO_CHANNELS = 1      # 1 = mono, 2 = stereo
```

## How it works

The script runs two concurrent loops — a main thread reading webcam frames into a rolling buffer, and a background thread reading audio chunks. On `R`, both pre-roll buffers flush into the recording. On `S`, the video is written to a temp file, audio to a `.wav`, then FFmpeg muxes them into a final `.mp4`.
