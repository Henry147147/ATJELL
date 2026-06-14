from __future__ import annotations

import threading
from pathlib import Path

from .models import ProcessingOptions
from .orchestrator import Pipeline
from .workers.ipc import WorkerClient


def main() -> None:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QFileDialog,
            QFormLayout,
            QHBoxLayout,
            QLineEdit,
            QMainWindow,
            QPushButton,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise SystemExit("PySide6 is not installed. Run: python -m pip install -e .[gui]") from exc

    class Window(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("asub")
            self.input_edit = QLineEdit()
            self.output_edit = QLineEdit(str(Path("asub-output").resolve(strict=False)))
            self.asr_model_edit = QLineEdit("Qwen/Qwen3-ASR-1.7B")
            self.targets_edit = QLineEdit("en,es,fr")
            self.source_edit = QLineEdit("auto")
            self.align_check = QCheckBox("Forced alignment")
            self.mux_check = QCheckBox("Mux subtitles")
            self.mux_check.setChecked(True)
            self.burn_check = QCheckBox("Burn subtitles")
            self.log = QTextEdit()
            self.log.setReadOnly(True)
            browse_input = QPushButton("Files or folder")
            browse_output = QPushButton("Output")
            start = QPushButton("Start")
            browse_input.clicked.connect(self.pick_input)
            browse_output.clicked.connect(self.pick_output)
            start.clicked.connect(self.start)
            form = QFormLayout()
            input_row = QHBoxLayout()
            input_row.addWidget(self.input_edit)
            input_row.addWidget(browse_input)
            output_row = QHBoxLayout()
            output_row.addWidget(self.output_edit)
            output_row.addWidget(browse_output)
            form.addRow("Input", input_row)
            form.addRow("Output", output_row)
            form.addRow("ASR model", self.asr_model_edit)
            form.addRow("Targets", self.targets_edit)
            form.addRow("Source", self.source_edit)
            form.addRow(self.align_check)
            form.addRow(self.mux_check)
            form.addRow(self.burn_check)
            layout = QVBoxLayout()
            layout.addLayout(form)
            layout.addWidget(start)
            layout.addWidget(self.log)
            widget = QWidget()
            widget.setLayout(layout)
            self.setCentralWidget(widget)
            self.resize(760, 520)

        def pick_input(self) -> None:
            files, _ = QFileDialog.getOpenFileNames(self, "Select videos")
            if files:
                self.input_edit.setText(";".join(files))
                return
            folder = QFileDialog.getExistingDirectory(self, "Select video folder")
            if folder:
                self.input_edit.setText(folder)

        def pick_output(self) -> None:
            folder = QFileDialog.getExistingDirectory(self, "Select output folder")
            if folder:
                self.output_edit.setText(folder)

        def start(self) -> None:
            inputs = [part for part in self.input_edit.text().split(";") if part.strip()]
            options = ProcessingOptions(
                output_dir=Path(self.output_edit.text()),
                asr_model=self.asr_model_edit.text().strip() or "Qwen/Qwen3-ASR-1.7B",
                target_languages=[part.strip() for part in self.targets_edit.text().split(",") if part.strip()],
                source_language=self.source_edit.text() or "auto",
                align=self.align_check.isChecked(),
                mux=self.mux_check.isChecked(),
                burn=self.burn_check.isChecked(),
            )
            self.log.append("Starting...")
            self.log.append(f"Qwen ASR worker: {WorkerClient('qwen_asr', 'asub.workers.qwen_asr_worker').command()[0]}")
            self.log.append(f"MT worker: {WorkerClient('mt', 'asub.workers.mt_worker').command()[0]}")
            self.log.append(f"Align worker: {WorkerClient('align', 'asub.workers.align_worker').command()[0]}")
            thread = threading.Thread(target=self._run, args=(inputs, options), daemon=True)
            thread.start()

        def _run(self, inputs: list[str], options: ProcessingOptions) -> None:
            try:
                jobs = Pipeline(options).process_inputs(inputs)
                self.log.append(f"Completed {len(jobs)} job(s).")
            except Exception as exc:
                self.log.append(f"Error: {exc}")

    app = QApplication([])
    window = Window()
    window.show()
    raise SystemExit(app.exec())
