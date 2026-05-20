import sys
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLineEdit,
    QCheckBox, QFileDialog, QLabel, QGridLayout, QTextEdit, QHBoxLayout, QVBoxLayout
)
from PySide6.QtGui import QPixmap
from qt_material import apply_stylesheet
from parsers.ios.keychain import process_keychain
from parsers.android.android import process_android
from parsers.ios.ios import process_ios
import os
import re

class SnapchatParserGUI(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Snapchat Forensic Parser")
        self.setFixedSize(1000, 550)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)

        # -------------------------
        # Top header: logo + title
        # -------------------------
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

        # -------------------------
        # Grid layout for inputs
        # -------------------------
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)

        # Labels
        case_label = QLabel("Case Name")
        extraction_label = QLabel("Snapchat Folder")
        output_label = QLabel("Output Folder")
        keychain_label = QLabel("Keychain File (iOS)")

        # Inputs
        self.case_name = QLineEdit()
        self.case_name.setPlaceholderText("Enter case name (e.g. Case_001)")

        self.extract_path = QLineEdit()
        self.extract_path.setPlaceholderText(
            "Select Snapchat Folder (com.snapchat.android or XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX)"
        )

        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Select output directory")

        self.keychain_path = QLineEdit()
        self.keychain_path.setPlaceholderText("Keychain file (iOS)")

        # Buttons
        self.extract_btn = QPushButton("Browse")
        self.output_btn = QPushButton("Browse")
        self.keychain_btn = QPushButton("Browse")

        self.extract_btn.clicked.connect(self.select_extraction)
        self.output_btn.clicked.connect(self.select_output)
        self.keychain_btn.clicked.connect(self.select_keychain)

        # Checkbox
        self.download_snaps = QCheckBox("Download Snaps")

        # Process button
        self.process_btn = QPushButton("Process")
        self.process_btn.setMinimumHeight(40)
        self.process_btn.clicked.connect(self.run_processing)

        # Log box
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        # -------------------------
        # Add widgets to grid
        # -------------------------

        grid_layout.addWidget(case_label, 0, 0)
        grid_layout.addWidget(self.case_name, 0, 1)

        grid_layout.addWidget(extraction_label, 1, 0)
        grid_layout.addWidget(self.extract_path, 1, 1)
        grid_layout.addWidget(self.extract_btn, 1, 2)

        grid_layout.addWidget(keychain_label, 2, 0)
        grid_layout.addWidget(self.keychain_path, 2, 1)
        grid_layout.addWidget(self.keychain_btn, 2, 2)

        grid_layout.addWidget(output_label, 3, 0)
        grid_layout.addWidget(self.output_path, 3, 1)
        grid_layout.addWidget(self.output_btn, 3, 2)

        grid_layout.addWidget(self.download_snaps, 4, 1)
        grid_layout.addWidget(self.process_btn, 5, 1)

        grid_layout.addWidget(self.log_box, 6, 0, 1, 3)

        main_layout.addLayout(grid_layout)
        self.setLayout(main_layout)

        self.apply_style()

    # -------------------------
    # Styling
    # -------------------------
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

    # -------------------------
    # Logging
    # -------------------------
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"INFO": "#7dd3fc", "OK": "#86efac", "ERROR": "#fca5a5"}
        color = colors.get(level, "#ffffff")

        log_entry = f'<span style="color:gray;">[{timestamp}]</span> ' \
                    f'<span style="color:{color};"><b>{level}</b></span> {message}'

        self.log_box.append(log_entry)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

    # -------------------------
    # File selectors
    # -------------------------
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

    # -------------------------
    # Detect platform
    # -------------------------
    def detect_platform(self, folder_path):

        folder_name = os.path.basename(folder_path)

        if folder_name == "com.snapchat.android":
            return "ANDROID"

        uuid_pattern = r"^[0-9a-fA-F\-]{36}$"

        if re.match(uuid_pattern, folder_name):
            return "IOS"

        return "UNKNOWN"

    # -------------------------
    # Processing
    # -------------------------
    def run_processing(self):

        case_name = self.case_name.text()

        if not case_name:
            self.log("No case name entered", "ERROR")
            return

        base_output = self.output_path.text()

        if not base_output:
            self.log("No output folder selected", "ERROR")
            return

        self.log(f"Processing case: {case_name}")
        self.log(f"Case output folder: {base_output}")

        if platform == "IOS":

            keychain_file = self.keychain_path.text()

            if not keychain_file:
                self.log("No keychain file selected", "ERROR")
                return

            self.log("Starting keychain processing")

            result = process_keychain(keychain_file)

            self.log(result, "OK")

            process_ios(
                case_name=case_name,
                input_path=self.extract_path.text(),
                cipherkey=result,
                output_path=base_output,
                download_files=self.download_snaps.isChecked()
            )

        elif platform == "ANDROID":

            process_android(
                case_name=case_name,
                input_path=self.extract_path.text(),
                output_path=base_output
            )

        self.log("Processing complete\n", "OK")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    apply_stylesheet(app, theme='light_blue.xml')

    window = SnapchatParserGUI()
    window.show()

    sys.exit(app.exec())