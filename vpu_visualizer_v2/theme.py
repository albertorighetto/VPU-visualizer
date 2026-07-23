"""
Theme, palette and shared style helpers for VPU Visualizer 2.0.

Flat, minimal dark theme. Panels are borderless "cards" distinguished by
surface color instead of frames; the only strong borders left in the app are
the pipe cells of the VPU matrix, which are a core feature.
"""

import os
import sys

from PyQt6.QtWidgets import QLabel


def resource_path(relative: str) -> str:
    """Absolute path to a bundled resource (works from source and PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


PALETTE = {
    "bg":           "#101116",
    "surface":      "#171820",
    "surface_alt":  "#1e2029",
    "surface_deep": "#0b0c10",
    "border":       "#272a37",
    "border_soft":  "#20222d",
    "accent":       "#7c6cff",
    "accent_hover": "#8f81ff",
    "accent_soft":  "#4b579d",
    "text":         "#e8e9ee",
    "text_dim":     "#9a9eb3",
    "muted":        "#686c80",
    "green":        "#3fd08b",
    "amber":        "#e8b33e",
    "red":          "#e5484d",
}

# One accent per device slot (1..4) so chained chassis are easy to tell apart.
DEVICE_COLORS = {
    1: "#7c6cff",   # violet
    2: "#35b8c8",   # teal
    3: "#e09a4a",   # orange
    4: "#d05fa2",   # pink
}


def device_color(device_id: int) -> str:
    return DEVICE_COLORS.get(device_id, PALETTE["accent"])


def make_chip(text: str, bg: str, fg: str = "#ffffff", tooltip: str = None) -> QLabel:
    """Small rounded pill label used for statuses, layers, mappings."""
    label = QLabel(text)
    label.setStyleSheet(
        f"background-color: {bg}; color: {fg};"
        "border-radius: 4px; padding: 2px 7px;"
        "font-size: 11px; font-weight: 600;"
    )
    if tooltip:
        label.setToolTip(tooltip)
    return label


def build_stylesheet() -> str:
    p = PALETTE
    return f"""
        QMainWindow, QDialog {{
            background-color: {p['bg']};
        }}
        QWidget {{
            color: {p['text']};
            font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            font-size: 13px;
        }}
        QLabel {{
            background: transparent;
        }}

        /* ---- Tabs: flat, underline indicator ---- */
        QTabWidget::pane {{
            border: none;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {p['text_dim']};
            padding: 8px 18px;
            margin-right: 2px;
            border: none;
            border-bottom: 2px solid transparent;
            font-weight: 600;
        }}
        QTabBar::tab:selected {{
            color: {p['text']};
            border-bottom: 2px solid {p['accent']};
        }}
        QTabBar::tab:hover:!selected {{
            color: {p['text']};
        }}

        /* ---- Buttons ---- */
        QPushButton {{
            background-color: {p['surface_alt']};
            color: {p['text']};
            border: none;
            border-radius: 6px;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            background-color: #262937;
        }}
        QPushButton:pressed {{
            background-color: {p['surface']};
        }}
        QPushButton:disabled {{
            color: {p['muted']};
            background-color: {p['surface']};
        }}
        QPushButton#accent {{
            background-color: {p['accent']};
            color: white;
            font-weight: 600;
        }}
        QPushButton#accent:hover {{
            background-color: {p['accent_hover']};
        }}
        QPushButton#accent:disabled {{
            background-color: {p['accent_soft']};
            color: {p['text_dim']};
        }}
        QPushButton#danger {{
            background-color: transparent;
            border: 1px solid {p['red']};
            color: {p['red']};
        }}
        QPushButton#danger:hover {{
            background-color: rgba(229, 72, 77, 0.15);
        }}
        QPushButton#ghost {{
            background-color: transparent;
            color: {p['text_dim']};
            padding: 6px 10px;
        }}
        QPushButton#ghost:hover {{
            background-color: {p['surface_alt']};
            color: {p['text']};
        }}
        QPushButton#segment {{
            background-color: transparent;
            color: {p['text_dim']};
            border-radius: 6px;
            padding: 4px 14px;
            font-weight: 600;
        }}
        QPushButton#segment:checked {{
            background-color: {p['accent']};
            color: white;
        }}
        QPushButton#segment:disabled {{
            color: {p['muted']};
        }}
        QFrame#segmentBox {{
            background-color: {p['surface']};
            border: 1px solid {p['border_soft']};
            border-radius: 8px;
        }}

        /* ---- Inputs ---- */
        QLineEdit, QSpinBox, QComboBox {{
            background-color: {p['surface']};
            border: 1px solid {p['border']};
            border-radius: 6px;
            padding: 5px 10px;
            color: {p['text']};
            selection-background-color: {p['accent']};
        }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
            border: 1px solid {p['accent']};
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            width: 0px;
            border: none;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {p['surface_alt']};
            border: 1px solid {p['border']};
            selection-background-color: {p['accent']};
            outline: none;
        }}
        QCheckBox {{
            color: {p['text_dim']};
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 15px;
            height: 15px;
            border: 1px solid {p['border']};
            border-radius: 4px;
            background: {p['surface']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {p['accent']};
            border-color: {p['accent']};
        }}

        /* ---- Tables (log) ---- */
        QTableView {{
            background-color: {p['surface']};
            alternate-background-color: rgba(255, 255, 255, 0.02);
            border: none;
            border-radius: 8px;
            gridline-color: transparent;
        }}
        QTableView::item {{
            padding: 1px 8px;
            border: none;
        }}
        QTableView::item:selected {{
            background-color: rgba(124, 108, 255, 0.25);
            color: {p['text']};
        }}
        QHeaderView::section {{
            background-color: {p['surface']};
            color: {p['muted']};
            border: none;
            padding: 6px 8px;
            font-weight: 600;
        }}
        QTableCornerButton::section {{
            background-color: {p['surface']};
            border: none;
        }}

        /* ---- Scrollbars: thin, unobtrusive ---- */
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: rgba(255, 255, 255, 0.12);
            border-radius: 5px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: rgba(255, 255, 255, 0.22);
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 10px;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: rgba(255, 255, 255, 0.12);
            border-radius: 5px;
            min-width: 30px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: rgba(255, 255, 255, 0.22);
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0;
            height: 0;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: transparent;
        }}

        /* ---- Misc ---- */
        QProgressBar {{
            background-color: {p['surface_deep']};
            border: none;
            border-radius: 3px;
            max-height: 6px;
        }}
        QProgressBar::chunk {{
            background-color: {p['accent']};
            border-radius: 3px;
        }}
        QStatusBar {{
            background-color: {p['surface']};
            color: {p['text_dim']};
            border-top: 1px solid {p['border_soft']};
        }}
        QStatusBar::item {{
            border: none;
        }}
        QToolTip {{
            background-color: {p['surface_alt']};
            color: {p['text']};
            border: 1px solid {p['border']};
            padding: 6px;
        }}

        /* ---- Cards: borderless panels distinguished by surface color ---- */
        QFrame[card="true"] {{
            background-color: {p['surface']};
            border: none;
            border-radius: 10px;
        }}
    """
