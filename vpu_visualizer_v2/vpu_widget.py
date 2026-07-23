"""
VPU Visualizer 2.0 VPU Widgets
The VPU card and its mixer/pipe matrix. The pipe-cell grid is the core
visualization and keeps its bordered-cell look; everything around it is flat.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from vpu_model import Device, VPU, Scaler, get_device_label
from theme import PALETTE, device_color, resource_path


# Color scheme: base surfaces from the shared theme, domain colors preserved
COLORS = {
    'bg_dark': PALETTE['surface_deep'],
    'bg_medium': PALETTE['surface'],

    'accent_secondary': PALETTE['accent_soft'],
    'accent_highlight': PALETTE['accent'],

    'status_active': '#8bb650',
    'status_warning': PALETTE['amber'],
    'status_error': PALETTE['red'],
    'status_inactive': '#343850',

    'text_primary': PALETTE['text'],
    'text_secondary': PALETTE['text_dim'],
    'text_muted': PALETTE['muted'],

    # Screen colors (from contact regions)
    'screen_1': '#009141',
    'screen_2': '#0d809b',
    'screen_3': '#989737',
    'screen_4': '#cc2e60',
    'screen_5': '#68469e',
    'screen_6': '#23a8b7',
    'screen_7': '#e23f30',
    'screen_8': '#de911f',

    # Capability colors
    'cap_off': '#343850',
    'cap_dual': '#4b579d',
    'cap_4k': '#8bb650',
    'cap_5k': '#e6b421',
    'cap_8k': '#cc2e60',
}

# Official layer colors (1-indexed, layer 1 is index 0)
LAYER_COLORS = [
    '#E31F1D', '#2F5295', '#56AB36', '#CC9999', '#3499CD', '#FAF19A',
    '#CB9902', '#A24B93', '#99CCCC', '#EA663B', '#F4E500', '#E6418D',
    '#DD6D6C', '#4C35C0', '#5ADE8B', '#8E0379', '#6362A6', '#C27A4E',
    '#837D30', '#AA69D8', '#0BB4BA', '#684B32', '#808079',
]

# Official layer text colors (white or black for contrast)
LAYER_TEXT_COLORS = [
    'white', 'white', 'black', 'black', 'black', 'black',
    'black', 'white', 'black', 'black', 'black', 'white',
    'black', 'white', 'black', 'white', 'white', 'black',
    'white', 'black', 'black', 'white', 'white',
]


def get_layer_color(layer_id: int) -> str:
    """Get official color for a layer ID, looping after layer 23."""
    if layer_id and layer_id > 0:
        return LAYER_COLORS[(layer_id - 1) % len(LAYER_COLORS)]
    return COLORS['status_inactive']


def get_layer_text_color(layer_id: int) -> str:
    """Get official text color (white or black) for a layer ID."""
    if layer_id and layer_id > 0:
        return LAYER_TEXT_COLORS[(layer_id - 1) % len(LAYER_TEXT_COLORS)]
    return COLORS['text_primary']


def get_screen_color(screen_id: int) -> str:
    """Get color for a screen ID."""
    colors = [
        COLORS['screen_1'], COLORS['screen_2'], COLORS['screen_3'],
        COLORS['screen_4'], COLORS['screen_5'], COLORS['screen_6'],
        COLORS['screen_7'], COLORS['screen_8'],
    ]
    return colors[(screen_id - 1) % len(colors)]


def get_capability_color(capability: str) -> str:
    """Get color for a capability value."""
    if not capability:
        return COLORS['cap_off']

    cap_upper = str(capability).upper()
    if cap_upper == 'OFF':
        return COLORS['cap_off']
    elif cap_upper == 'DUAL':
        return COLORS['cap_dual']
    elif cap_upper in ('4K', '3'):
        return COLORS['cap_4k']
    elif cap_upper in ('5K', '5', '6', '7'):
        return COLORS['cap_5k']
    elif cap_upper == '8K':
        return COLORS['cap_8k']
    else:
        return COLORS['cap_dual']


# Capacity icons: DUAL -> cap1, 4K -> cap2, 5K -> cap4 (rendered at 2.25:1 aspect)
ICONS_DIR = resource_path("icons")
CAPACITY_ICONS = {
    'DUAL': 'cap1.png',
    '4K': 'cap2.png',
    '5K': 'cap4.png',
}
CF_ICON_PATH = os.path.join(ICONS_DIR, "cf.png").replace("\\", "/")


def get_capacity_icon_path(capability: str):
    """Filesystem path of the capacity icon for a capability value, or None."""
    filename = CAPACITY_ICONS.get(str(capability).upper()) if capability else None
    if not filename:
        return None
    return os.path.join(ICONS_DIR, filename).replace("\\", "/")


def is_truthy_capa(value) -> bool:
    """Whether a capacity-like property value counts as set/true."""
    return bool(value) and str(value).upper() not in ("NONE", "OFF")


def get_capacity_html(capability: str) -> str:
    """Get an HTML snippet (icon only, 2.25:1 aspect) for a mixer capacity value."""
    if not capability:
        return "-"
    icon_path = get_capacity_icon_path(capability)
    if not icon_path:
        return str(capability)
    return f'<img src="{icon_path}" width="36" height="16">'


def get_cutnfill_html() -> str:
    """Get an HTML snippet (icon only, square) for the cut-and-fill indicator."""
    return f'<img src="{CF_ICON_PATH}" width="16" height="16">'


class PipeCellWidget(QFrame):
    """Widget representing one or more contiguous output pipe columns for a mixer.

    Carries the full mixer content (color, screen/layer text, tooltip) when
    the mixer actually uses these pipes. Pipes that share the same data
    (same mixer, same used/unused state, adjacent columns) are merged into
    a single wider cell instead of duplicating the content across cells.
    """

    CELL_SIZE = 32

    cell_hovered = pyqtSignal(object)
    cell_left = pyqtSignal()

    def __init__(self, scaler: Scaler, pipe_ids, parent=None):
        super().__init__(parent)
        self.scaler = scaler
        self.pipe_ids = list(pipe_ids)
        self.is_highlighted = False
        self.highlight_slice_match = False
        self.text_color = COLORS['text_primary']

        self.setFixedHeight(self.CELL_SIZE)
        self.setMinimumWidth(self.CELL_SIZE * len(self.pipe_ids))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self.update_display()

    def is_used(self) -> bool:
        """Whether this mixer actually uses these pipes."""
        value = self.scaler.pipes.get(self.pipe_ids[0])
        return bool(value) and value != "NONE"

    def update_display(self):
        """Update the display based on mixer data and this pipe's usage."""
        used = self.is_used()

        if used and self.scaler.is_enabled:
            if self.scaler.layer:
                bg_color = get_layer_color(self.scaler.layer)
                self.text_color = get_layer_text_color(self.scaler.layer)
            elif self.scaler.screen:
                bg_color = get_screen_color(self.scaler.screen)
                self.text_color = COLORS['text_primary']
            else:
                bg_color = COLORS['status_active']
                self.text_color = COLORS['text_primary']
            border_color = get_capability_color(self.scaler.capability)
        else:
            bg_color = COLORS['bg_dark']
            self.text_color = COLORS['text_primary']
            border_color = COLORS['status_inactive']

        highlight_color = "#ffffff" if self.highlight_slice_match else "#ffff00"
        hover_border = COLORS['accent_highlight'] if not self.is_highlighted else highlight_color
        highlight_border = f"3px solid {highlight_color}" if self.is_highlighted else f"2px solid {border_color}"

        self.setStyleSheet(f"""
            PipeCellWidget {{
                background-color: {bg_color};
                border: {highlight_border};
                border-radius: 5px;
            }}
            PipeCellWidget:hover {{
                border: 2px solid {hover_border};
            }}
        """)

        self.setToolTip(self._get_tooltip())
        self.update()

    def set_highlighted(self, highlighted: bool, slice_match: bool = False):
        """Set highlight state (border only). slice_match marks the tighter
        match (same screen/layer AND same slice number) with a different border color."""
        self.is_highlighted = highlighted
        self.highlight_slice_match = slice_match
        self.update_display()
        self.repaint()

    def enterEvent(self, event):
        """Handle mouse enter event."""
        if self.is_used() and self.scaler.screen is not None and self.scaler.layer is not None:
            self.cell_hovered.emit(self.scaler)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave event."""
        self.cell_left.emit()
        super().leaveEvent(event)

    def _get_tooltip(self) -> str:
        """Generate tooltip HTML. Empty (no tooltip) when this pipe is not used."""
        if not self.is_used():
            return ""

        s = self.scaler
        lines = []

        if s.screen:
            lines.append(f"Screen: S{s.screen}")

        if s.layer:
            lines.append(f"Layer: {s.layer}")

        capacity_line = get_capacity_html(s.capability)
        if is_truthy_capa(s.cutnfill_capa):
            capacity_line += " " + get_cutnfill_html()
        lines.append(capacity_line)

        lines.append("Mixer" if is_truthy_capa(s.seamless_capa) else "Split")

        if s.channel is not None:
            lines.append(f"Channel: {s.channel}")

        if s.slice is not None:
            lines.append(f"Slice: {s.slice}")

        return "<html>" + "<br>".join(lines) + "</html>"

    def paintEvent(self, event):
        """Custom paint for mixer content, only when this pipe is used."""
        super().paintEvent(event)

        if not self.is_used():
            if len(self.pipe_ids) > 1:
                self._paint_empty_dividers()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw text with proper color (small cell, but keep text prominent)
        painter.setPen(QColor(self.text_color))
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)

        rect = self.rect()

        if self.scaler.is_enabled and self.scaler.screen:
            text = f"S{self.scaler.screen}"
            if self.scaler.layer:
                text += f"\nL{self.scaler.layer}"
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        else:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(self.scaler.id))

        painter.end()

    def _paint_empty_dividers(self):
        """Draw thin vertical lines at each pipe boundary inside a merged empty
        cell, so the number of joined (unused) pipes stays visible."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(COLORS['status_inactive']))
        pen.setWidth(1)
        painter.setPen(pen)

        segment_width = self.width() / len(self.pipe_ids)
        for i in range(1, len(self.pipe_ids)):
            x = round(segment_width * i)
            painter.drawLine(x, 3, x, self.height() - 3)

        painter.end()


class VPUWidget(QFrame):
    """Card for one VPU: 16 mixers (rows) x 8 output pipes (columns),
    with mixers grouped in pairs. Flat card; the device accent color is used
    on hover so all VPUs of the same device light up together."""

    # Forwarded from whichever PipeCellWidget is currently hovered - the grid can be
    # rebuilt (merged spans changing), so callers should connect to these instead of
    # to individual pipe widgets, which may be replaced.
    cell_hovered = pyqtSignal(object)
    cell_left = pyqtSignal()

    # Emitted so the main window can highlight every card of the same device
    device_hovered = pyqtSignal(int)
    device_left = pyqtSignal(int)

    def __init__(self, device: Device, vpu: VPU, parent=None):
        super().__init__(parent)
        self.device = device
        self.vpu = vpu
        self.pipe_widgets = []
        self.dev_color = device_color(device.id)
        self._device_highlight = False

        self.setMinimumWidth(300)
        self._apply_card_style()
        self.setup_ui()

    def _apply_card_style(self):
        border = (f"1px solid {self.dev_color}" if self._device_highlight
                  else f"1px solid {PALETTE['border_soft']}")
        self.setStyleSheet(f"""
            VPUWidget {{
                background-color: {PALETTE['surface']};
                border: {border};
                border-radius: 10px;
            }}
            VPUWidget:hover {{
                border: 1px solid {self.dev_color};
                background-color: {PALETTE['surface_alt']};
            }}
        """)

    def set_device_highlight(self, highlighted: bool):
        """Subtle highlight applied to sibling cards of the hovered device."""
        if self._device_highlight != highlighted:
            self._device_highlight = highlighted
            self._apply_card_style()

    def enterEvent(self, event):
        self.device_hovered.emit(self.device.id)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.device_left.emit(self.device.id)
        super().leaveEvent(event)

    def setup_ui(self):
        """Setup the VPU widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header: device color dot + VPU title + device chip
        header = QHBoxLayout()
        header.setSpacing(8)

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {self.dev_color}; font-size: 11px; background: transparent;")
        header.addWidget(dot)

        title = QLabel(f"VPU {self.vpu.vpu_id}")
        title.setStyleSheet("font-weight: 600; font-size: 13px; background: transparent;")
        header.addWidget(title)

        header.addStretch()

        chip = QLabel(f"D{self.device.id} · {get_device_label(self.device.device_type)}")
        chip.setStyleSheet(
            f"color: {self.dev_color}; background-color: rgba(255,255,255,0.05);"
            "border-radius: 4px; padding: 1px 7px; font-size: 11px; font-weight: 600;"
        )
        header.addWidget(chip)

        layout.addLayout(header)

        # Mixer/pipe matrix: 16 mixers (rows) x 8 output pipes (columns),
        # mixers grouped in pairs (1&2, 3&4, ...)
        matrix_widget = QWidget()
        matrix_widget.setStyleSheet("background: transparent;")
        matrix_layout = QVBoxLayout(matrix_widget)
        matrix_layout.setContentsMargins(0, 0, 0, 0)
        matrix_layout.setSpacing(4)

        # Column headers (stretch evenly so they always fill the VPU's width,
        # matching the proportional stretch used by the mixer rows below)
        header_row = QHBoxLayout()
        header_row.setSpacing(0)
        for pipe_id in range(1, 9):
            pipe_header = QLabel(f"P{pipe_id}")
            pipe_header.setMinimumWidth(PipeCellWidget.CELL_SIZE)
            pipe_header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            pipe_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pipe_header.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 9px; background: transparent;")
            header_row.addWidget(pipe_header, 1)
        matrix_layout.addLayout(header_row)

        # Container for the mixer rows, rebuilt whenever pipe usage changes
        # (merged cell spans can only change by rebuilding the row layout).
        self.rows_container = QWidget()
        self.rows_container.setStyleSheet("background: transparent;")
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        matrix_layout.addWidget(self.rows_container)

        layout.addWidget(matrix_widget)

        # Usage info
        self.usage_label = QLabel()
        self.usage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.usage_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px; background: transparent;")
        layout.addWidget(self.usage_label)

        self.rebuild_matrix()

    @staticmethod
    def _compute_pipe_runs(scaler: Scaler):
        """Group pipes 1-8 into contiguous runs sharing the same used/unused state,
        so pipes sharing the same data can be rendered as a single merged cell."""
        def pipe_used(pipe_id: int) -> bool:
            value = scaler.pipes.get(pipe_id)
            return bool(value) and value != "NONE"

        runs = []
        current_run = [1]
        current_used = pipe_used(1)
        for pipe_id in range(2, 9):
            used = pipe_used(pipe_id)
            if used == current_used:
                current_run.append(pipe_id)
            else:
                runs.append(current_run)
                current_run = [pipe_id]
                current_used = used
        runs.append(current_run)
        return runs

    def rebuild_matrix(self):
        """(Re)build the mixer/pipe grid, merging contiguous pipes that share the same data."""
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.pipe_widgets = []

        for pair_start in range(0, len(self.vpu.scalers), 2):
            pair_scalers = self.vpu.scalers[pair_start:pair_start + 2]

            # Mixer pairs are grouped by a soft background tint instead of a border
            pair_frame = QFrame()
            pair_frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(255, 255, 255, 0.03);
                    border: none;
                    border-radius: 6px;
                }
            """)
            pair_layout = QVBoxLayout(pair_frame)
            pair_layout.setContentsMargins(4, 4, 4, 4)
            pair_layout.setSpacing(3)

            for scaler in pair_scalers:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(0)

                for pipe_run in self._compute_pipe_runs(scaler):
                    pipe_widget = PipeCellWidget(scaler, pipe_run)
                    pipe_widget.cell_hovered.connect(self.cell_hovered)
                    pipe_widget.cell_left.connect(self.cell_left)
                    self.pipe_widgets.append(pipe_widget)
                    # Stretch proportional to how many pipe columns this cell spans,
                    # so the row always stretches to fill the VPU's width.
                    row_layout.addWidget(pipe_widget, len(pipe_run))

                pair_layout.addLayout(row_layout)

            self.rows_layout.addWidget(pair_frame)

    def update_display(self):
        """Update the display, rebuilding the grid if merged pipe spans need to change."""
        old_shape = [tuple(w.pipe_ids) for w in self.pipe_widgets]
        new_shape = []
        for scaler in self.vpu.scalers:
            new_shape.extend(tuple(run) for run in self._compute_pipe_runs(scaler))

        if old_shape != new_shape:
            self.rebuild_matrix()
        else:
            for widget in self.pipe_widgets:
                widget.update_display()

        active = self.vpu.get_active_scalers_count()
        percentage = self.vpu.get_usage_percentage()

        # Color based on usage
        if percentage >= 80:
            color = COLORS['status_error']
        elif percentage >= 50:
            color = COLORS['status_warning']
        else:
            color = COLORS['status_active']

        self.usage_label.setText(f"{active}/16 mixers · {percentage:.0f}%")
        self.usage_label.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")

    def get_matching_cells(self, scaler: Scaler):
        """Get all used pipe cells whose mixer matches the given screen and layer."""
        matching = []
        for widget in self.pipe_widgets:
            s = widget.scaler
            if widget.is_used() and s.screen == scaler.screen and s.layer == scaler.layer:
                matching.append(widget)
        return matching

    def highlight_matching(self, scaler: Scaler, highlighted: bool):
        """Highlight (border) all cells matching the given scaler's screen and layer.
        Cells that also share the same slice number get a slightly different border color."""
        matching = self.get_matching_cells(scaler)
        for widget in matching:
            slice_match = (highlighted and scaler.slice is not None
                           and widget.scaler.slice == scaler.slice)
            widget.set_highlighted(highlighted, slice_match)
