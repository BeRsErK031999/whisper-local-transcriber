from __future__ import annotations

import os
import sys
import importlib
from pathlib import Path
from subprocess import CalledProcessError, run
from typing import Callable

import imageio_ffmpeg
import numpy as np
import whisper
import whisper.audio
from whisper.model import Whisper

whisper_transcribe = importlib.import_module("whisper.transcribe")

AVAILABLE_MODELS = ("small", "medium")
SUPPORTED_AUDIO_SUFFIXES = (".mp3", ".wav", ".m4a", ".flac", ".ogg")
ProgressCallback = Callable[[int, int], None]
StatusCallback = Callable[[str], None]

_MODEL_CACHE: dict[str, Whisper] = {}


def _get_project_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent

    return Path(__file__).resolve().parent


PROJECT_DIR = _get_project_dir()
AUDIO_INPUT_DIR = PROJECT_DIR / "audio_in"
TEXT_OUTPUT_DIR = PROJECT_DIR / "text_out"
MODELS_DIR = PROJECT_DIR / "models"


def ensure_project_directories() -> tuple[Path, Path]:
    AUDIO_INPUT_DIR.mkdir(exist_ok=True)
    TEXT_OUTPUT_DIR.mkdir(exist_ok=True)
    return AUDIO_INPUT_DIR, TEXT_OUTPUT_DIR


def ensure_model_directory() -> Path:
    MODELS_DIR.mkdir(exist_ok=True)
    return MODELS_DIR


def list_audio_files(directory: Path = AUDIO_INPUT_DIR) -> list[Path]:
    ensure_project_directories()
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES
    )


def build_output_path(
    audio_path: Path,
    output_directory: Path = TEXT_OUTPUT_DIR,
) -> Path:
    output_directory.mkdir(parents=True, exist_ok=True)
    return output_directory / f"{audio_path.stem}.txt"


def _ensure_ffmpeg_on_path() -> None:
    ffmpeg_executable = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    candidate_directories = [
        str(Path(sys.executable).resolve().parent),
        str(PROJECT_DIR),
        str(ffmpeg_executable.parent),
    ]
    current_entries = (
        os.environ.get("PATH", "").split(os.pathsep) if os.environ.get("PATH") else []
    )

    normalized_entries = {entry.lower() for entry in current_entries}
    new_entries = [
        entry for entry in candidate_directories if entry.lower() not in normalized_entries
    ]

    if new_entries:
        os.environ["PATH"] = os.pathsep.join([*new_entries, *current_entries])

    _patch_whisper_audio_loader(ffmpeg_executable)


def _patch_whisper_audio_loader(ffmpeg_executable: Path) -> None:
    def load_audio_with_bundled_ffmpeg(
        file: str,
        sr: int = whisper.audio.SAMPLE_RATE,
    ) -> np.ndarray:
        cmd = [
            str(ffmpeg_executable),
            "-nostdin",
            "-threads",
            "0",
            "-i",
            file,
            "-f",
            "s16le",
            "-ac",
            "1",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(sr),
            "-",
        ]

        try:
            out = run(cmd, capture_output=True, check=True).stdout
        except CalledProcessError as error:
            message = error.stderr.decode(errors="replace")
            raise RuntimeError(f"Не удалось прочитать аудио через ffmpeg: {message}") from error

        return np.frombuffer(out, np.int16).flatten().astype(np.float32) / 32768.0

    whisper.audio.load_audio = load_audio_with_bundled_ffmpeg


class _WhisperProgressBar:
    def __init__(
        self,
        *args: object,
        callback: ProgressCallback | None = None,
        **kwargs: object,
    ) -> None:
        total = kwargs.get("total")
        if total is None and args:
            total = args[0]

        self.total = int(total or 0)
        self.current = 0
        self.callback = callback

    def __enter__(self) -> "_WhisperProgressBar":
        self._emit()
        return self

    def __exit__(self, *args: object) -> None:
        if self.total:
            self.current = self.total
            self._emit()

    def update(self, amount: int | float = 1) -> None:
        self.current += int(amount)
        if self.total:
            self.current = min(self.current, self.total)
        self._emit()

    def close(self) -> None:
        self._emit()

    def _emit(self) -> None:
        if self.callback and self.total:
            self.callback(self.current, self.total)


class _ProgressPatch:
    def __init__(self, callback: ProgressCallback | None) -> None:
        self.callback = callback
        self.original_download_tqdm = None
        self.original_transcribe_tqdm = None

    def __enter__(self) -> None:
        if not self.callback:
            return

        self.original_download_tqdm = whisper.tqdm
        self.original_transcribe_tqdm = whisper_transcribe.tqdm.tqdm

        def progress_factory(*args: object, **kwargs: object) -> _WhisperProgressBar:
            return _WhisperProgressBar(*args, callback=self.callback, **kwargs)

        whisper.tqdm = progress_factory
        whisper_transcribe.tqdm.tqdm = progress_factory

    def __exit__(self, *args: object) -> None:
        if self.original_download_tqdm is not None:
            whisper.tqdm = self.original_download_tqdm
        if self.original_transcribe_tqdm is not None:
            whisper_transcribe.tqdm.tqdm = self.original_transcribe_tqdm


def _load_model(
    model_name: str,
    progress_callback: ProgressCallback | None = None,
) -> Whisper:
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    _ensure_ffmpeg_on_path()
    download_root = str(ensure_model_directory()) if getattr(sys, "frozen", False) else None

    with _ProgressPatch(progress_callback):
        model = whisper.load_model(model_name, download_root=download_root)

    _MODEL_CACHE[model_name] = model
    return model


def transcribe_audio(
    file_path: str,
    model_name: str = "medium",
    progress_callback: ProgressCallback | None = None,
    status_callback: StatusCallback | None = None,
) -> str:
    if model_name not in AVAILABLE_MODELS:
        available_models = ", ".join(AVAILABLE_MODELS)
        raise ValueError(
            f"Unsupported model '{model_name}'. Available models: {available_models}"
        )

    audio_path = Path(file_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Файл не найден: {audio_path}")

    if status_callback:
        status_callback("Подготовка ffmpeg")
    _ensure_ffmpeg_on_path()

    if status_callback:
        status_callback(f"Загрузка модели {model_name}")
    model = _load_model(model_name, progress_callback=progress_callback)

    if status_callback:
        status_callback("Распознавание речи")
    with _ProgressPatch(progress_callback):
        result = model.transcribe(
            str(audio_path),
            language="ru",
            fp16=False,
            verbose=False,
        )
    return result["text"].strip()
