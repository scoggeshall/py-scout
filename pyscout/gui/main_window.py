from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pyscout.resources import app_icon_path, app_logo_path
from pyscout.storage.sqlite_store import open_default_store

from .tabs.discovery_tab import DiscoveryTab
from .tabs.mapper_tab import MapperTab


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Py-Scout")
        icon_path = app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        self._apply_style()
        status_bar = QStatusBar()
        status_bar.setSizeGripEnabled(False)
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("Ready")

        store = open_default_store()
        self.tabs = QTabWidget()
        self.discovery_tab = DiscoveryTab(store, status_callback=self.show_status)
        self.mapper_tab = MapperTab(store, status_callback=self.show_status)
        self.discovery_tab.mapper_record_saved.connect(self._show_saved_mapper_record)

        self.tabs.addTab(self.discovery_tab, "Discovery")
        self.tabs.addTab(self.mapper_tab, "Mapper")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self._build_header())
        content_layout.addWidget(self.tabs, stretch=1)
        self.setCentralWidget(content)

    def show_status(self, message: str) -> None:
        self.statusBar().showMessage(message or "Ready")

    def _show_saved_mapper_record(self, record_id: int) -> None:
        self.mapper_tab.refresh_records(select_record_id=record_id)
        self.tabs.setCurrentWidget(self.mapper_tab)
        self.show_status("Record saved")

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("BrandHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(14)

        logo_label = QLabel()
        logo_label.setObjectName("BrandLogo")
        logo_label.setFixedSize(96, 96)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = app_logo_path()
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo_label.setPixmap(
                    pixmap.scaled(
                        logo_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title = QLabel("Py-Scout")
        title.setObjectName("BrandTitle")
        subtitle = QLabel("Switchport Discovery + Physical Mapping Tool")
        subtitle.setObjectName("BrandSubtitle")

        text_layout.addStretch(1)
        text_layout.addWidget(title)
        text_layout.addWidget(subtitle)
        text_layout.addStretch(1)

        header_layout.addWidget(logo_label)
        header_layout.addLayout(text_layout)
        header_layout.addStretch(1)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return header

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #f5f7fa;
                font-family: "Segoe UI", Arial, sans-serif;
            }
            QFrame#BrandHeader {
                background: #ffffff;
                border-bottom: 1px solid #c9d2df;
            }
            QLabel#BrandTitle {
                color: #172033;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#BrandSubtitle {
                color: #4b5b72;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #c9d2df;
                background: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background: #e8edf4;
                border: 1px solid #c9d2df;
                padding: 8px 16px;
                min-width: 110px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom-color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #d3dae5;
                border-radius: 6px;
                font-weight: 600;
                margin-top: 10px;
                padding-top: 10px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QPushButton {
                min-height: 32px;
                min-width: 118px;
                padding: 4px 14px;
            }
            QLineEdit, QComboBox {
                min-height: 30px;
                padding-left: 6px;
            }
            QTableWidget {
                gridline-color: #d8dee8;
                selection-background-color: #2f6fed;
                selection-color: #ffffff;
                alternate-background-color: #f7f9fc;
                show-decoration-selected: 1;
            }
            QHeaderView::section {
                background: #eef2f7;
                border: 0;
                border-right: 1px solid #d8dee8;
                border-bottom: 1px solid #d8dee8;
                padding: 6px;
                font-weight: 600;
            }
            QStatusBar {
                background: #eef2f7;
                border-top: 1px solid #c9d2df;
                padding-left: 8px;
            }
            """
        )
