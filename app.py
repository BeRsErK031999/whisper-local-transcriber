from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from transcribe import (
    AUDIO_INPUT_DIR,
    AVAILABLE_MODELS,
    TEXT_OUTPUT_DIR,
    build_output_path,
    ensure_project_directories,
    list_audio_files,
    transcribe_audio,
)


class WhisperTranscriberApp:
    def __init__(self, root: tk.Tk) -> None:
        ensure_project_directories()

        self.root = root
        self.root.title("Whisper Transcriber")
        self.root.geometry("880x600")
        self.root.minsize(800, 560)

        self.audio_input_dir = AUDIO_INPUT_DIR
        self.text_output_dir = TEXT_OUTPUT_DIR

        self.selected_file = tk.StringVar(value="Файл не выбран")
        self.status_text = tk.StringVar(value="Готово к распознаванию")
        self.stage_text = tk.StringVar(value="Ожидание")
        self.progress_text = tk.StringVar(value="0%")
        self.folder_text = tk.StringVar()
        self.model_name = tk.StringVar(value="small")
        self.progress_value = tk.DoubleVar(value=0)
        self.file_counter_text = tk.StringVar(value="Файлов в очереди: 0")
        self.elapsed_text = tk.StringVar(value="Время: 00:00")

        self.is_processing = False
        self.started_at = 0.0
        self.timer_job: str | None = None

        self._configure_style()
        self._build_ui()
        self._sync_folder_text()
        self._refresh_queue_count()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f6f7f9")
        style.configure("TLabelframe", background="#f6f7f9")
        style.configure("TLabelframe.Label", background="#f6f7f9", foreground="#1f2937")
        style.configure("TLabel", background="#f6f7f9", foreground="#1f2937")
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Muted.TLabel", foreground="#5f6b7a")
        style.configure("Status.TLabel", foreground="#155e75", font=("Segoe UI", 10, "bold"))
        style.configure("TButton", padding=(12, 7))
        style.configure("Horizontal.TProgressbar", thickness=18)

    def _build_ui(self) -> None:
        container = ttk.Frame(self.root, padding=24)
        container.pack(fill="both", expand=True)

        header = ttk.Frame(container)
        header.pack(fill="x")

        title = ttk.Label(
            header,
            text="Локальное распознавание аудио",
            style="Title.TLabel",
        )
        title.pack(anchor="w")

        description = ttk.Label(
            header,
            text=(
                "Выберите папку с аудио и папку для текста. "
                "Можно обработать всю папку или выбрать один отдельный файл."
            ),
            style="Muted.TLabel",
            wraplength=820,
            justify="left",
        )
        description.pack(anchor="w", pady=(6, 0))

        folders_frame = ttk.LabelFrame(container, text="Рабочие папки", padding=14)
        folders_frame.pack(fill="x", pady=(18, 0))

        folders_label = ttk.Label(
            folders_frame,
            textvariable=self.folder_text,
            wraplength=800,
            justify="left",
        )
        folders_label.pack(anchor="w")

        folder_buttons = ttk.Frame(folders_frame)
        folder_buttons.pack(anchor="w", pady=(12, 0))

        self.choose_input_button = ttk.Button(
            folder_buttons,
            text="Выбрать папку аудио",
            command=self.choose_audio_input_dir,
        )
        self.choose_input_button.pack(side="left")

        self.choose_output_button = ttk.Button(
            folder_buttons,
            text="Выбрать папку текста",
            command=self.choose_text_output_dir,
        )
        self.choose_output_button.pack(side="left", padx=(10, 0))

        self.open_input_button = ttk.Button(
            folder_buttons,
            text="Открыть аудио",
            command=lambda: self.open_directory(self.audio_input_dir),
        )
        self.open_input_button.pack(side="left", padx=(10, 0))

        self.open_output_button = ttk.Button(
            folder_buttons,
            text="Открыть текст",
            command=lambda: self.open_directory(self.text_output_dir),
        )
        self.open_output_button.pack(side="left", padx=(10, 0))

        self.refresh_button = ttk.Button(
            folder_buttons,
            text="Обновить очередь",
            command=self._refresh_queue_count,
        )
        self.refresh_button.pack(side="left", padx=(10, 0))

        controls = ttk.Frame(container)
        controls.pack(fill="x", pady=(18, 0))

        model_label = ttk.Label(controls, text="Модель:")
        model_label.pack(side="left")

        self.model_select = ttk.Combobox(
            controls,
            textvariable=self.model_name,
            values=AVAILABLE_MODELS,
            state="readonly",
            width=12,
        )
        self.model_select.pack(side="left", padx=(8, 20))

        queue_label = ttk.Label(controls, textvariable=self.file_counter_text, style="Muted.TLabel")
        queue_label.pack(side="left")

        actions = ttk.Frame(container)
        actions.pack(fill="x", pady=(16, 0))

        self.process_folder_button = ttk.Button(
            actions,
            text="Обработать выбранную папку",
            command=self.process_input_folder,
        )
        self.process_folder_button.pack(side="left")

        self.select_button = ttk.Button(
            actions,
            text="Выбрать отдельный файл",
            command=self.select_file,
        )
        self.select_button.pack(side="left", padx=(10, 0))

        progress_frame = ttk.LabelFrame(container, text="Ход обработки", padding=14)
        progress_frame.pack(fill="x", pady=(18, 0))

        progress_header = ttk.Frame(progress_frame)
        progress_header.pack(fill="x")

        self.stage_label = ttk.Label(progress_header, textvariable=self.stage_text, style="Status.TLabel")
        self.stage_label.pack(side="left")

        self.progress_label = ttk.Label(progress_header, textvariable=self.progress_text, style="Status.TLabel")
        self.progress_label.pack(side="right")

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_value,
            maximum=100,
            mode="determinate",
        )
        self.progress_bar.pack(fill="x", pady=(10, 0))

        details = ttk.Frame(progress_frame)
        details.pack(fill="x", pady=(10, 0))

        self.elapsed_label = ttk.Label(details, textvariable=self.elapsed_text, style="Muted.TLabel")
        self.elapsed_label.pack(side="left")

        self.status_label = ttk.Label(
            details,
            textvariable=self.status_text,
            style="Muted.TLabel",
            wraplength=600,
            justify="right",
        )
        self.status_label.pack(side="right")

        file_frame = ttk.LabelFrame(container, text="Текущий выбор", padding=14)
        file_frame.pack(fill="both", expand=True, pady=(18, 0))

        self.file_label = ttk.Label(
            file_frame,
            textvariable=self.selected_file,
            wraplength=800,
            justify="left",
        )
        self.file_label.pack(anchor="nw")

    def choose_audio_input_dir(self) -> None:
        if self.is_processing:
            return

        directory = filedialog.askdirectory(
            title="Выберите папку с аудио",
            initialdir=str(self.audio_input_dir),
        )
        if not directory:
            return

        self.audio_input_dir = Path(directory)
        self._sync_folder_text()
        self._refresh_queue_count()

    def choose_text_output_dir(self) -> None:
        if self.is_processing:
            return

        directory = filedialog.askdirectory(
            title="Выберите папку для текста",
            initialdir=str(self.text_output_dir),
        )
        if not directory:
            return

        self.text_output_dir = Path(directory)
        self.text_output_dir.mkdir(parents=True, exist_ok=True)
        self._sync_folder_text()

    def open_directory(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        os.startfile(directory)
        self._refresh_queue_count()

    def select_file(self) -> None:
        if self.is_processing:
            return

        file_path = filedialog.askopenfilename(
            title="Выберите аудиофайл",
            initialdir=str(self.audio_input_dir),
            filetypes=[
                ("Audio Files", "*.mp3 *.wav *.m4a *.flac *.ogg"),
                ("All Files", "*.*"),
            ],
        )

        if not file_path:
            return

        self.selected_file.set(file_path)
        self._start_processing()

        worker = threading.Thread(
            target=self._transcribe_single_in_background,
            args=(Path(file_path), self.model_name.get()),
            daemon=True,
        )
        worker.start()

    def process_input_folder(self) -> None:
        if self.is_processing:
            return

        audio_files = list_audio_files(self.audio_input_dir)
        if not audio_files:
            messagebox.showwarning(
                "Нет файлов",
                f"В выбранной папке нет аудиофайлов:\n{self.audio_input_dir}",
            )
            self._refresh_queue_count()
            return

        names_preview = "\n".join(audio_path.name for audio_path in audio_files[:8])
        if len(audio_files) > 8:
            names_preview += f"\n... и еще {len(audio_files) - 8} файл(ов)"

        self.selected_file.set(names_preview)
        self._start_processing()

        worker = threading.Thread(
            target=self._transcribe_folder_in_background,
            args=(audio_files, self.model_name.get()),
            daemon=True,
        )
        worker.start()

    def _start_processing(self) -> None:
        self.started_at = time.monotonic()
        self._set_progress(0, "Подготовка")
        self._set_processing_state(True)
        self._tick_timer()

    def _set_processing_state(self, is_processing: bool) -> None:
        self.is_processing = is_processing
        button_state = "disabled" if is_processing else "normal"
        combobox_state = "disabled" if is_processing else "readonly"

        self.process_folder_button.config(state=button_state)
        self.select_button.config(state=button_state)
        self.choose_input_button.config(state=button_state)
        self.choose_output_button.config(state=button_state)
        self.open_input_button.config(state=button_state)
        self.open_output_button.config(state=button_state)
        self.refresh_button.config(state=button_state)
        self.model_select.config(state=combobox_state)

        if not is_processing:
            self._cancel_timer()
            self._refresh_queue_count()

    def _transcribe_single_in_background(self, file_path: Path, model_name: str) -> None:
        try:
            self._set_status_async(f"Файл: {file_path.name}")
            output_path = self._transcribe_to_output(file_path, model_name, 0, 1)
            self.root.after(0, self._handle_success, [str(output_path)])
        except Exception as error:
            self.root.after(0, self._handle_error, str(error))

    def _transcribe_folder_in_background(
        self,
        audio_files: list[Path],
        model_name: str,
    ) -> None:
        output_paths: list[str] = []

        try:
            total_files = len(audio_files)
            for index, audio_path in enumerate(audio_files, start=1):
                self._set_status_async(f"Файл {index} из {total_files}: {audio_path.name}")
                output_path = self._transcribe_to_output(
                    audio_path,
                    model_name,
                    index - 1,
                    total_files,
                )
                output_paths.append(str(output_path))

            self.root.after(0, self._handle_success, output_paths)
        except Exception as error:
            self.root.after(0, self._handle_error, str(error))

    def _transcribe_to_output(
        self,
        file_path: Path,
        model_name: str,
        completed_files: int,
        total_files: int,
    ) -> Path:
        def progress_callback(current: int, total: int) -> None:
            if total <= 0:
                return

            file_progress = current / total
            overall_progress = ((completed_files + file_progress) / total_files) * 100
            self.root.after(
                0,
                self._set_progress,
                overall_progress,
                f"{round(overall_progress)}%",
            )

        def status_callback(message: str) -> None:
            self.root.after(0, self.stage_text.set, message)

        text = transcribe_audio(
            file_path=str(file_path),
            model_name=model_name,
            progress_callback=progress_callback,
            status_callback=status_callback,
        )
        output_path = build_output_path(file_path, self.text_output_dir)
        output_path.write_text(text, encoding="utf-8")
        return output_path

    def _set_progress(self, value: float, label: str) -> None:
        safe_value = max(0, min(100, value))
        self.progress_value.set(safe_value)
        self.progress_text.set(label)

    def _set_status_async(self, message: str) -> None:
        self.root.after(0, self.status_text.set, message)

    def _handle_success(self, output_paths: list[str]) -> None:
        self._set_progress(100, "100%")
        self.stage_text.set("Готово")
        self.status_text.set("Распознавание завершено")
        self._set_processing_state(False)

        if len(output_paths) == 1:
            output_path = output_paths[0]
            messagebox.showinfo("Готово", f"Текст сохранен:\n{output_path}")
            return

        messagebox.showinfo(
            "Готово",
            (
                f"Обработано файлов: {len(output_paths)}\n"
                f"Результаты сохранены в:\n{self.text_output_dir}"
            ),
        )

    def _handle_error(self, error_message: str) -> None:
        self.stage_text.set("Ошибка")
        self.status_text.set("Обработка остановлена")
        self._set_processing_state(False)
        messagebox.showerror("Ошибка", error_message)

    def _refresh_queue_count(self) -> None:
        try:
            count = len(list_audio_files(self.audio_input_dir))
        except FileNotFoundError:
            count = 0
        self.file_counter_text.set(f"Файлов в очереди: {count}")

    def _sync_folder_text(self) -> None:
        self.folder_text.set(
            f"Папка аудио: {self.audio_input_dir}\n"
            f"Папка текста: {self.text_output_dir}"
        )

    def _tick_timer(self) -> None:
        if not self.is_processing:
            return

        elapsed = int(time.monotonic() - self.started_at)
        minutes, seconds = divmod(elapsed, 60)
        self.elapsed_text.set(f"Время: {minutes:02d}:{seconds:02d}")
        self.timer_job = self.root.after(1000, self._tick_timer)

    def _cancel_timer(self) -> None:
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None


def main() -> None:
    root = tk.Tk()
    WhisperTranscriberApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
