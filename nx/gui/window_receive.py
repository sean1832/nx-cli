import pathlib

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QWidget,
)

from nx.core import utilities as utils
from nx.gui.file_receiver_thread import FileReceiverThread
from nx.gui.widget_toggle_switch import ToggleSwitch
from nx.gui.window_add_entries import AddEntries


class ReceiveWindow(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app

        self.toggle_switch = ToggleSwitch()  # create a toggle switch
        self.toggle_switch.toggled.connect(self.on_toggle_switch_changed)

        self.initUI()
        self.setWindowIcon(
            QIcon(str(pathlib.Path(utils.get_project_root(), "assets/icon.png")))
        )

    def initUI(self):
        self.setWindowTitle("Receiver")

        # Create a grid layout
        main_layout = QGridLayout(self)

        # create a IP label
        self.ip_label = QLabel(f"IP: {utils.get_local_ip()}")
        self.ip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ip_label.setStyleSheet("font: Arial; font-size: 15px; black;")
        main_layout.addWidget(self.ip_label, 0, 0, 1, 2)

        # create a port combo box
        self.combo_box_port = QComboBox()
        self.combo_box_port.addItems(utils.read_local_entries("ports"))
        self.combo_box_port.addItem("Add Port...")
        self.combo_box_port.setEditable(True)
        self.combo_box_port.currentIndexChanged.connect(self.on_combobox_port_changed)
        main_layout.addWidget(self.combo_box_port, 1, 0, 1, 2)

        # create a save path line edit
        self.save_path_line_edit = QLineEdit()
        self.save_path_line_edit.setPlaceholderText("Save Path")
        main_layout.addWidget(self.save_path_line_edit, 2, 0)

        # create a browse button
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_save_path)
        main_layout.addWidget(self.browse_btn, 2, 1)

        # create a toggle switch
        self.toggle_switch.clicked.connect(self.receive_file)

        main_layout.addWidget(
            self.toggle_switch, 3, 0, 1, 2, Qt.AlignmentFlag.AlignCenter
        )

        # progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar, 4, 0, 1, 2)

        # Set the layout
        self.setLayout(main_layout)

    def receive_file(self):
        if self.toggle_switch.isChecked():
            file_dir = self.save_path_line_edit.text()
            port = self.combo_box_port.currentText()
            if file_dir == "":
                QMessageBox.critical(
                    self,
                    "Error",
                    "Please select a save path",
                    QMessageBox.StandardButton.Ok,
                )
                self.close_toggle_switch()
                return

            # Create and start the file receiver thread
            self.file_receiver_thread = FileReceiverThread(port, file_dir, 4)
            self.file_receiver_thread.update_progress.connect(self.update_progress_bar)
            self.file_receiver_thread.finished_receiving.connect(
                self.on_receiving_finished
            )
            self.file_receiver_thread.error_occured.connect(self.on_error_occured)
            self.file_receiver_thread.start()

        else:
            self.progress_bar.setValue(0)

    def on_toggle_switch_changed(self, checked):
        if not checked and hasattr(self, "file_receiver_thread"):
            self.file_receiver_thread.requestInterruption()

    def close_toggle_switch(self):
        self.progress_bar.setValue(0)
        self.toggle_switch.setChecked(False)

    def closeEvent(self, event):
        if (
            hasattr(self, "file_receiver_thread")
            and self.file_receiver_thread.isRunning()
        ):
            self.file_receiver_thread.requestInterruption()
            self.file_receiver_thread.terminate()
        super().closeEvent(event)

    @Slot(str)
    def on_error_occured(self, error):
        QMessageBox.critical(self, "Error", error)
        self.close_toggle_switch()

    @Slot(dict)
    def update_progress_bar(self, progress):
        current = progress["current"]
        total = progress["total"]
        percent = int((current / total) * 100)
        self.progress_bar.setValue(percent)

    @Slot()
    def on_receiving_finished(self):
        self.progress_bar.setValue(0)

    def browse_save_path(self):
        file_path = QFileDialog.getExistingDirectory(
            self, "Select Directory", self.save_path_line_edit.text()
        )
        self.save_path_line_edit.setText(file_path)

    def refresh_port_combo_boxes(self):
        self.combo_box_port.clear()
        self.combo_box_port.addItems(utils.read_local_entries("ports"))
        self.combo_box_port.addItem("Add Port...")
        # select the second last item
        self.combo_box_port.setCurrentIndex(self.combo_box_port.count() - 2)

    def on_combobox_port_changed(self):
        if self.combo_box_port.currentText() == "Add Port...":
            self.add_port()

    def add_port(self):
        self.combo_box_port.setCurrentIndex(0)
        self.app.add_entries = AddEntries("Port", "ports", self)
        self.app.add_entries.entries_updated.connect(self.refresh_port_combo_boxes)
        self.app.add_entries.show()
