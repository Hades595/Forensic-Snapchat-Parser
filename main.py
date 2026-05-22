import sys
import os
import re
import webbrowser
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLineEdit,
    QCheckBox, QFileDialog, QLabel, QGridLayout, QTextEdit, QHBoxLayout, QVBoxLayout
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QObject, QThread, Signal
from qt_material import apply_stylesheet

from parsers.ios.keychain import process_keychain
from parsers.android.android import process_android
from parsers.ios.ios import process_ios


# ─────────────────────────────────────────────
# Background worker — runs processing off the
# main thread so the GUI stays responsive.
# ─────────────────────────────────────────────
class ProcessWorker(QObject):
    log_signal = Signal(str, str)   # (message, level)
    finished   = Signal(str)        # report_path (empty string on failure)
    error      = Signal(str)        # error message

    def __init__(self, platform, case_name, examiner, extract_path,
                 output_path, keychain_path, download_snaps):
        super().__init__()
        self.platform      = platform
        self.case_name     = case_name
        self.examiner      = examiner
        self.extract_path  = extract_path
        self.output_path   = output_path
        self.keychain_path = keychain_path
        self.download_snaps = download_snaps

    def run(self):
        def log(msg, lvl="INFO"):
            self.log_signal.emit(str(msg), lvl)

        try:
            if self.platform == "IOS":
                result = process_keychain(self.keychain_path)
                log(result, "OK")
                report_path = process_ios(
                    case_name=self.case_name,
                    examiner=self.examiner,
                    input_path=self.extract_path,
                    cipherkey=result,
                    output_path=self.output_path,
                    download_files=self.download_snaps,
                    log_callback=log,
                )
            elif self.platform == "ANDROID":
                report_path = process_android(
                    case_name=self.case_name,
                    examiner=self.examiner,
                    input_path=self.extract_path,
                    output_path=self.output_path,
                    download_files=self.download_snaps,
                    log_callback=log,
                )
            else:
                report_path = ""

            self.finished.emit(report_path or "")

        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────
# Main GUI
# ─────────────────────────────────────────────
class SnapchatParserGUI(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Snapchat Forensic Parser")
        self.setFixedSize(1000, 600)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)

        # ── Header: logo + title ──
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)

        self.logo_label = QLabel()
        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        pixmap = QPixmap(logo_path)
        pixmap = pixmap.scaledToHeight(80)
        self.logo_label.setPixmap(pixmap)

        title_layout = QVBoxLayout()
        title_label = QLabel("Snapchat Forensic Parser")
        title_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        subtitle_label = QLabel("Parse Snapchat iOS/Android data, keychains, and logs")
        subtitle_label.setStyleSheet("font-size: 16px; color: gray;")
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)

        header_layout.addWidget(self.logo_label)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # ── Grid layout ──
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)

        # Labels
        case_label     = QLabel("Case Name")
        examiner_label = QLabel("Examiner Name")
        extraction_label = QLabel("Snapchat Folder")
        keychain_label = QLabel("Keychain File (iOS)")
        output_label   = QLabel("Output Folder")

        # Inputs
        self.case_name = QLineEdit()
        self.case_name.setPlaceholderText("Enter case name (e.g. Case_001)")

        self.examiner_name = QLineEdit()
        self.examiner_name.setPlaceholderText("Enter examiner name")

        self.extract_path = QLineEdit()
        self.extract_path.setPlaceholderText(
            "Select Snapchat Folder (com.snapchat.android or XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)"
        )

        self.keychain_path = QLineEdit()
        self.keychain_path.setPlaceholderText("Keychain file (iOS)")

        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output directory")

        # Browse buttons
        self.extract_btn  = QPushButton("Browse")
        self.keychain_btn = QPushButton("Browse")
        self.output_btn   = QPushButton("Browse")

        self.extract_btn.clicked.connect(self.select_extraction)
        self.keychain_btn.clicked.connect(self.select_keychain)
        self.output_btn.clicked.connect(self.select_output)

        # Checkbox + Process button
        self.download_snaps = QCheckBox("Download Snaps")

        self.process_btn = QPushButton("Process")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.clicked.connect(self.run_processing)

        # Log box
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        # ── Grid placement ──
        # Row 0: Case Name
        grid_layout.addWidget(case_label,       0, 0)
        grid_layout.addWidget(self.case_name,   0, 1)

        # Row 1: Examiner Name
        grid_layout.addWidget(examiner_label,      1, 0)
        grid_layout.addWidget(self.examiner_name,  1, 1)

        # Row 2: Snapchat Folder
        grid_layout.addWidget(extraction_label,  2, 0)
        grid_layout.addWidget(self.extract_path, 2, 1)
        grid_layout.addWidget(self.extract_btn,  2, 2)

        # Row 3: Keychain File
        grid_layout.addWidget(keychain_label,     3, 0)
        grid_layout.addWidget(self.keychain_path, 3, 1)
        grid_layout.addWidget(self.keychain_btn,  3, 2)

        # Row 4: Output Folder
        grid_layout.addWidget(output_label,     4, 0)
        grid_layout.addWidget(self.output_path, 4, 1)
        grid_layout.addWidget(self.output_btn,  4, 2)

        # Row 5: Download Snaps checkbox
        grid_layout.addWidget(self.download_snaps, 5, 1)

        # Row 6: Process button
        grid_layout.addWidget(self.process_btn, 6, 1)

        # Row 7: Log box
        grid_layout.addWidget(self.log_box, 7, 0, 1, 3)

        main_layout.addLayout(grid_layout)
        self.setLayout(main_layout)
        self.apply_style()

    # ── Styling ──
    def apply_style(self):
        self.setStyleSheet("""
        QWidget {
            background-color: #f5f6f8;
            font-size: 14px;
        }
        QLabel {
            font-weight: 500;
        }
        QLineEdit {
            border: 1px solid #c5c7cc;
            border-radius: 6px;
            padding: 6px;
            background: white;
        }
        QPushButton {
            background-color: #3b82f6;
            border: none;
            color: white;
            border-radius: 6px;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #2563eb;
        }
        QPushButton:disabled {
            background-color: #93c5fd;
        }
        QCheckBox {
            padding-top: 6px;
        }
        QTextEdit {
            background-color: #111;
            color: #e5e5e5;
            border-radius: 6px;
            padding: 6px;
            font-family: Consolas, monospace;
        }
        """)

    # ── Logging ──
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "#7dd3fc", "OK": "#86efac", "ERROR": "#fca5a5"}
        color = colors.get(level, "#ffffff")

        log_entry = (
            f'<span style="color:gray;">[{timestamp}]</span> '
            f'<span style="color:{color};"><b>{level}</b></span> {message}'
        )
        self.log_box.append(log_entry)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

    # ── File selectors ──
    def select_extraction(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Snapchat Folder")
        if folder:
            self.extract_path.setText(folder)
            self.log(f"Selected Snapchat folder: {folder}")

            global platform
            platform = self.detect_platform(folder)

            if platform == "ANDROID":
                self.log("Detected Android Snapchat extraction", "INFO")
                self.keychain_path.clear()
                self.keychain_path.setEnabled(False)
                self.keychain_btn.setEnabled(False)
            elif platform == "IOS":
                self.log("Detected iOS Snapchat extraction", "INFO")
                self.keychain_path.setEnabled(True)
                self.keychain_btn.setEnabled(True)
            else:
                self.log("Unknown Snapchat folder type", "ERROR")

    def select_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_path.setText(folder)
            self.log(f"Selected output folder: {folder}")

    def select_keychain(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Keychain File")
        if file:
            self.keychain_path.setText(file)
            self.log(f"Selected keychain file: {file}")

    # ── Platform detection ──
    def detect_platform(self, folder_path):
        folder_name = os.path.basename(folder_path)
        if folder_name == "com.snapchat.android":
            return "ANDROID"
        if re.match(r"^[0-9a-fA-F\-]{36}$", folder_name):
            return "IOS"
        return "UNKNOWN"

    # ── Processing (non-blocking) ──
    def run_processing(self):
        case_name = self.case_name.text().strip()
        if not case_name:
            self.log("No case name entered", "ERROR")
            return

        examiner = self.examiner_name.text().strip()
        if not examiner:
            self.log("No examiner name entered", "ERROR")
            return

        base_output = self.output_path.text()
        if not base_output:
            self.log("No output folder selected", "ERROR")
            return

        if platform == "IOS":
            keychain_file = self.keychain_path.text()
            if not keychain_file:
                self.log("No keychain file selected", "ERROR")
                return
        else:
            keychain_file = ""

        self.log(f"Processing case: {case_name}")
        self.log(f"Examiner: {examiner}")
        self.log(f"Case output folder: {base_output}")
        self.process_btn.setEnabled(False)

        self.worker = ProcessWorker(
            platform=platform,
            case_name=case_name,
            examiner=examiner,
            extract_path=self.extract_path.text(),
            output_path=base_output,
            keychain_path=keychain_file,
            download_snaps=self.download_snaps.isChecked(),
        )
        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.log_signal.connect(self.log)
        self.worker.finished.connect(self.on_processing_done)
        self.worker.error.connect(self.on_processing_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_processing_done(self, report_path):
        self.process_btn.setEnabled(True)
        self.log("Processing complete", "OK")
        if report_path:
            self.log(f"Report saved: {report_path}", "OK")
            webbrowser.open(f"file:///{report_path.replace(os.sep, '/')}")
        else:
            self.log("No report generated — check errors above", "ERROR")

    def on_processing_error(self, message):
        self.process_btn.setEnabled(True)
        self.log(f"Processing failed: {message}", "ERROR")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='light_blue.xml')
    window = SnapchatParserGUI()
    window.show()
    sys.exit(app.exec())
