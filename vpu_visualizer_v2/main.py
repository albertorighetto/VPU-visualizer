#!/usr/bin/env python3
"""
VPU Visualizer 2.0
Main entry point for the application.
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

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

    # Set a real point size on the default font. The stylesheet's font-size
    # is in pt too (see theme.py) - if either one were px instead, QFont
    # would carry a pixel size with no point size, and any Qt-internal
    # drawing code that derives a font from it (e.g. QLineEdit's built-in
    # clear button) would call setPointSize(-1) and print a Qt warning.
    app.setFont(QFont("Segoe UI", 10))

    app.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
