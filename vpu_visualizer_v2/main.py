#!/usr/bin/env python3
"""
VPU Visualizer 2.0
Main entry point for the application.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from main_window import MainWindow


def main():
    """Main application entry point."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("VPU Visualizer")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("VPU Visualizer")
    
    # Apply dark theme stylesheet
    app.setStyleSheet(get_dark_stylesheet())
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


def get_dark_stylesheet():
    """Return dark theme stylesheet inspired by the official software."""
    return """
        QMainWindow {
            background-color: #1a1a2e;
        }
        QWidget {
            background-color: #1a1a2e;
            color: #e0e0e0;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 12px;
        }
        QLabel {
            color: #e0e0e0;
        }
        QGroupBox {
            border: 1px solid #3d3d5c;
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
            color: #8dadff;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #2e3192;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: #4b579d;
        }
        QPushButton:pressed {
            background-color: #1b1464;
        }
        QPushButton:disabled {
            background-color: #3d3d5c;
            color: #888888;
        }
        QLineEdit {
            background-color: #16213e;
            border: 1px solid #3d3d5c;
            border-radius: 4px;
            padding: 6px;
            color: #e0e0e0;
        }
        QLineEdit:focus {
            border: 1px solid #826bff;
        }
        QSpinBox {
            background-color: #16213e;
            border: 1px solid #3d3d5c;
            border-radius: 4px;
            padding: 6px;
            color: #e0e0e0;
        }
        QTextEdit {
            background-color: #16213e;
            border: 1px solid #3d3d5c;
            border-radius: 4px;
            color: #e0e0e0;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        QScrollArea {
            border: none;
            background-color: #1a1a2e;
        }
        QScrollBar:vertical {
            background-color: #16213e;
            width: 12px;
            border-radius: 6px;
        }
        QScrollBar::handle:vertical {
            background-color: #3d3d5c;
            border-radius: 6px;
            min-height: 20px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #4b579d;
        }
        QStatusBar {
            background-color: #16213e;
            color: #8dadff;
        }
        QMenuBar {
            background-color: #16213e;
            color: #e0e0e0;
        }
        QMenuBar::item:selected {
            background-color: #2e3192;
        }
        QMenu {
            background-color: #16213e;
            color: #e0e0e0;
            border: 1px solid #3d3d5c;
        }
        QMenu::item:selected {
            background-color: #2e3192;
        }
    """


if __name__ == "__main__":
    main()
