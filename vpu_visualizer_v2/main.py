#!/usr/bin/env python3
"""
VPU Visualizer 2.0
Main entry point for the application.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from theme import build_stylesheet
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

    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
