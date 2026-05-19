# Whisper Local Transcriber

Desktop application for local speech-to-text transcription with OpenAI Whisper.

The app runs Whisper on the user's machine, reads audio files from `audio_in`,
and writes UTF-8 `.txt` transcripts to `text_out`.

## Features

- Local transcription without sending audio to an external API.
- Russian transcription by default.
- Batch processing for all supported files in `audio_in`.
- Single-file selection through the desktop UI.
- Progress bar, percentage, current stage, elapsed time, and queue counter.
- `small` and `medium` model selection.
- Inno Setup installer that can be installed without administrator rights.

## Folders

- `audio_in` - input audio files.
- `text_out` - generated text transcripts.
- `models` - Whisper model files used by the packaged app.

When running the packaged executable from `dist`, these folders are created
next to `dist/whisper-local-app.exe`.

## Supported Audio Formats

- `.mp3`
- `.wav`
- `.m4a`
- `.flac`
- `.ogg`

## Development

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Build Executable

```powershell
.\venv\Scripts\activate
pyinstaller --noconfirm whisper-local-app.spec
```

The executable is created at:

```text
dist/whisper-local-app.exe
```

## Build Installer

Install Inno Setup 6, then run:

```powershell
.\build-installer.ps1
```

The installer is created at:

```text
installer-output/whisper-local-app-setup.exe
```

The installer uses:

```text
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\Whisper Local App
```

This allows per-user installation without administrator rights.

## Offline Model

The installer includes:

```text
dist/models/small.pt
```

Users can transcribe with the `small` model without internet access after
installation. If the `medium` model is selected and it is not present locally,
Whisper may try to download it.
