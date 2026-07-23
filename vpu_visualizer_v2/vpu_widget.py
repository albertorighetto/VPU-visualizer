"""
VPU Visualizer 2.0 VPU Widgets
Custom widgets for displaying VPU and scaler information.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QSizePolicy, QToolTip,
    QTableWidget, QTableWidgetItem
)
from PyQt6.QtGui import QBrush as QtBrush
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QEvent
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QFont, QPainterPath

from vpu_model import Device, VPU, Scaler, Screen, Layer, get_device_label


# Color scheme from official app analysis
COLORS = {
    # Background colors
    'bg_dark': '#1a1a2e',
    'bg_medium': '#16213e',
    'bg_light': '#1f4068',

    # Accent colors from BANK_COLOR_PALETTE and KEYER_COLOR_PALETTE
    'accent_primary': '#2e3192',
    'accent_secondary': '#4b579d',
    'accent_highlight': '#826bff',
    'accent_purple': '#68469e',
    'accent_magenta': '#8e3899',

    # Status colors
    'status_active': '#8bb650',
    'status_warning': '#e6b421',
    'status_error': '#cc2e60',
    'status_inactive': '#3d3d5c',

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
    'cap_off': '#3d3d5c',
    'cap_dual': '#4b579d',
    'cap_4k': '#8bb650',
    'cap_5k': '#e6b421',
    'cap_8k': '#cc2e60',

    # Text colors
    'text_primary': '#e0e0e0',
    'text_secondary': '#8dadff',
    'text_muted': '#888888',
}

# Official layer colors (1-indexed, layer 1 is index 0)
LAYER_COLORS = [
    '#E31F1D',  # Layer 1
    '#2F5295',  # Layer 2
    '#56AB36',  # Layer 3
    '#CC9999',  # Layer 4
    '#3499CD',  # Layer 5
    '#FAF19A',  # Layer 6
    '#CB9902',  # Layer 7
    '#A24B93',  # Layer 8
    '#99CCCC',  # Layer 9
    '#EA663B',  # Layer 10
    '#F4E500',  # Layer 11
    '#E6418D',  # Layer 12
    '#DD6D6C',  # Layer 13
    '#4C35C0',  # Layer 14
    '#5ADE8B',  # Layer 15
    '#8E0379',  # Layer 16
    '#6362A6',  # Layer 17
    '#C27A4E',  # Layer 18
    '#837D30',  # Layer 19
    '#AA69D8',  # Layer 20
    '#0BB4BA',  # Layer 21
    '#684B32',  # Layer 22
    '#808079',  # Layer 23
]

# Official layer text colors (white or black for contrast)
LAYER_TEXT_COLORS = [
    'white',   # Layer 1
    'white',   # Layer 2
    'black',   # Layer 3
    'black',   # Layer 4
    'black',   # Layer 5
    'black',   # Layer 6
    'black',   # Layer 7
    'white',   # Layer 8
    'black',   # Layer 9
    'black',   # Layer 10
    'black',   # Layer 11
    'white',   # Layer 12
    'black',   # Layer 13
    'white',   # Layer 14
    'black',   # Layer 15
    'white',   # Layer 16
    'white',   # Layer 17
    'black',   # Layer 18
    'white',   # Layer 19
    'black',   # Layer 20
    'black',   # Layer 21
    'white',   # Layer 22
    'white',   # Layer 23
]


def get_layer_color(layer_id: int) -> str:
    """Get official color for a layer ID, looping after layer 23."""
    if layer_id > 0:
        return LAYER_COLORS[(layer_id - 1) % len(LAYER_COLORS)]
    return COLORS['status_inactive']


def get_layer_text_color(layer_id: int) -> str:
    """Get official text color (white or black) for a layer ID, looping after layer 23."""
    if layer_id > 0:
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
ICONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
CAPACITY_ICONS = {
    'DUAL': 'cap1.png',
    '4K': 'cap2.png',
    '5K': 'cap4.png',
}
CF_ICON_PATH = os.path.join(ICONS_DIR, "cf.png").replace("\\", "/")


def is_truthy_capa(value) -> bool:
    """Whether a capacity-like property value counts as set/true."""
    return bool(value) and str(value).upper() not in ("NONE", "OFF")


def get_capacity_html(capability: str) -> str:
    """Get an HTML snippet (icon only, 2.25:1 aspect) for a mixer capacity value."""
    if not capability:
        return "-"

    filename = CAPACITY_ICONS.get(str(capability).upper())
    if not filename:
        return str(capability)

    icon_path = os.path.join(ICONS_DIR, filename).replace("\\", "/")
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
    """Widget representing a complete VPU: 16 mixers (rows) x 8 output pipes (columns),
    with mixers grouped in pairs (1&2, 3&4, ... 15&16)."""

    # Forwarded from whichever PipeCellWidget is currently hovered - the grid can be
    # rebuilt (merged spans changing), so callers should connect to these instead of
    # to individual pipe widgets, which may be replaced.
    cell_hovered = pyqtSignal(object)
    cell_left = pyqtSignal()

    def __init__(self, device: Device, vpu: VPU, parent=None):
        super().__init__(parent)
        self.device = device
        self.vpu = vpu
        self.pipe_widgets = []

        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setStyleSheet(f"""
            VPUWidget {{
                background-color: {COLORS['bg_medium']};
                border: 1px solid {COLORS['accent_secondary']};
                border-radius: 8px;
                padding: 5px;
            }}
        """)

        self.setup_ui()
    
    def setup_ui(self):
        """Setup the VPU widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Header
        header = QLabel(f"Device {self.device.id} - VPU {self.vpu.vpu_id}")
        header.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            font-weight: bold;
            font-size: 12px;
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Device type
        if self.device.device_type:
            type_label = QLabel(f"({get_device_label(self.device.device_type)})")
            type_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
            type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(type_label)
        
        # Mixer/pipe matrix: 16 mixers (rows) x 8 output pipes (columns),
        # mixers grouped in pairs (1&2, 3&4, ...)
        matrix_widget = QWidget()
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
            pipe_header.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 9px;")
            header_row.addWidget(pipe_header, 1)
        matrix_layout.addLayout(header_row)

        # Container for the mixer rows, rebuilt whenever pipe usage changes
        # (merged cell spans can only change by rebuilding the row layout).
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(3)
        matrix_layout.addWidget(self.rows_container)

        layout.addWidget(matrix_widget)

        # Usage info
        self.usage_label = QLabel()
        self.usage_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.usage_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
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

            pair_frame = QFrame()
            pair_frame.setStyleSheet(f"""
                QFrame {{
                    border: 1px solid {COLORS['accent_secondary']};
                    border-radius: 4px;
                }}
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

        self.usage_label.setText(f"Usage: {active}/16 ({percentage:.0f}%)")
        self.usage_label.setStyleSheet(f"color: {color}; font-size: 10px;")

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


class LayerWidget(QFrame):
    """Widget representing a layer in a screen."""

    def __init__(self, layer: Layer, parent=None):
        super().__init__(parent)
        self.layer = layer

        self.setFixedSize(25, 25)
        self.update_display()

    def update_display(self):
        """Update layer display."""
        bg_color = get_layer_color(self.layer.id)
        border = "2px solid #826bff" if self.layer.mask else "1px solid #3d3d5c"

        self.setStyleSheet(f"""
            LayerWidget {{
                background-color: {bg_color};
                border: {border};
                border-radius: 3px;
            }}
        """)

        tooltip = f"Layer {self.layer.id}"
        if self.layer.capability:
            tooltip += f"\nCapability: {self.layer.capability}"
        if self.layer.mask:
            tooltip += "\n(Mask enabled)"

        self.setToolTip(tooltip)

    def paintEvent(self, event):
        """Paint layer number."""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        text_color = get_layer_text_color(self.layer.id)
        painter.setPen(QColor(text_color))
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self.layer.id))
        painter.end()


class ScreenWidget(QFrame):
    """Widget representing a screen."""
    
    def __init__(self, screen: Screen, parent=None):
        super().__init__(parent)
        self.screen = screen
        
        self.setMinimumSize(150, 100)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup screen widget UI."""
        color = get_screen_color(self.screen.id)
        
        self.setStyleSheet(f"""
            ScreenWidget {{
                background-color: {COLORS['bg_medium']};
                border: 2px solid {color};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        
        # Header
        header = QHBoxLayout()
        
        title = QLabel(f"Screen {self.screen.id}")
        title.setStyleSheet(f"color: {color}; font-weight: bold;")
        header.addWidget(title)
        
        if self.screen.optimized:
            opt_label = QLabel("⚡")
            opt_label.setToolTip("Optimized")
            header.addWidget(opt_label)
        
        header.addStretch()
        layout.addLayout(header)
        
        # Layers
        self.layers_widget = QWidget()
        self.layers_layout = QHBoxLayout(self.layers_widget)
        self.layers_layout.setContentsMargins(0, 0, 0, 0)
        self.layers_layout.setSpacing(3)
        
        self.layer_widgets = []
        for layer in self.screen.layers:
            widget = LayerWidget(layer)
            self.layer_widgets.append(widget)
            self.layers_layout.addWidget(widget)
        
        self.layers_layout.addStretch()
        layout.addWidget(self.layers_widget)
        
        # Info
        self.info_label = QLabel(f"{len(self.screen.layers)} layers")
        self.info_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 10px;")
        layout.addWidget(self.info_label)
        
        layout.addStretch()
    
    def update_display(self):
        """Update display."""
        for widget in self.layer_widgets:
            widget.update_display()
        
        self.info_label.setText(f"{len(self.screen.layers)} layers")


class PipeWidget(QFrame):
    """Widget representing an output pipe."""
    
    def __init__(self, pipe_id: int, is_used: bool = False, parent=None):
        super().__init__(parent)
        self.pipe_id = pipe_id
        self.is_used = is_used
        
        self.setFixedSize(20, 20)
        self.update_display()
    
    def update_display(self):
        """Update pipe display."""
        if self.is_used:
            bg_color = COLORS['status_active']
        else:
            bg_color = COLORS['status_inactive']
        
        self.setStyleSheet(f"""
            PipeWidget {{
                background-color: {bg_color};
                border: 1px solid {COLORS['accent_secondary']};
                border-radius: 3px;
            }}
        """)
        
        self.setToolTip(f"Pipe {self.pipe_id}: {'Used' if self.is_used else 'Available'}")
    
    def paintEvent(self, event):
        """Paint pipe number."""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setPen(QColor(COLORS['text_primary']))
        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)
        
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self.pipe_id))
        painter.end()


class LayersTableWidget(QWidget):
    """Table widget displaying all layers with color coding and hover highlighting."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.table = QTableWidget()
        self.hovered_row = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Screen", "Layer", "Capability", "Regions", "Mask"])
        self.table.horizontalHeader().setStretchLastSection(False)

        self.setup_hover()

    def setup_hover(self):
        """Setup hover tracking for cells."""
        self.table.setMouseTracking(True)
        self.table.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle mouse hover events."""
        if obj == self.table.viewport():
            if event.type() == QEvent.Type.MouseMove:
                pos = event.position().toPoint()
                item = self.table.itemAt(pos)
                if item:
                    self.on_row_hover(item.row())
                else:
                    self.clear_highlight()
            elif event.type() == QEvent.Type.Leave:
                self.clear_highlight()
        return super().eventFilter(obj, event)

    def on_row_hover(self, row):
        """Highlight the hovered row as a whole (no property matching)."""
        if row == self.hovered_row:
            return

        self.clear_highlight()

        if row < 0 or row >= self.table.rowCount():
            return

        self.hovered_row = row
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(QtBrush(QColor("#3d5c7a")))

    def clear_highlight(self):
        """Clear the current row highlight."""
        if self.hovered_row is not None and 0 <= self.hovered_row < self.table.rowCount():
            for col in range(self.table.columnCount()):
                item = self.table.item(self.hovered_row, col)
                if item and col == 1:  # Layer number column
                    layer_id = int(item.text())
                    color = get_layer_color(layer_id)
                    item.setBackground(QtBrush(QColor(color)))
                elif item:
                    item.setBackground(QtBrush(QColor(COLORS['bg_medium'])))
        self.hovered_row = None

    def populate_from_model(self):
        """Populate table with layer data from model."""
        self.table.setRowCount(0)

        for screen in self.model.screens:
            if screen.active:
                for layer in screen.layers:
                    row = self.table.rowCount()
                    self.table.insertRow(row)

                    layer_id = layer.id
                    layer_color = get_layer_color(layer_id)
                    text_color = get_layer_text_color(layer_id)

                    # Screen
                    screen_item = QTableWidgetItem(f"S{screen.id}")
                    screen_item.setBackground(QtBrush(QColor(COLORS['bg_medium'])))
                    screen_item.setForeground(QtBrush(QColor(COLORS['text_primary'])))
                    self.table.setItem(row, 0, screen_item)

                    # Layer
                    layer_item = QTableWidgetItem(str(layer_id))
                    layer_item.setBackground(QtBrush(QColor(layer_color)))
                    layer_item.setForeground(QtBrush(QColor(text_color)))
                    layer_item.setFont(QFont(layer_item.font().family(), layer_item.font().pointSize(), QFont.Weight.Bold))
                    self.table.setItem(row, 1, layer_item)

                    # Capability
                    cap_item = QTableWidgetItem(layer.capability or "-")
                    cap_item.setBackground(QtBrush(QColor(COLORS['bg_medium'])))
                    cap_item.setForeground(QtBrush(QColor(COLORS['text_primary'])))
                    self.table.setItem(row, 2, cap_item)

                    # Regions
                    regions_text = ", ".join(map(str, layer.regions)) if layer.regions else "-"
                    regions_item = QTableWidgetItem(regions_text)
                    regions_item.setBackground(QtBrush(QColor(COLORS['bg_medium'])))
                    regions_item.setForeground(QtBrush(QColor(COLORS['text_primary'])))
                    self.table.setItem(row, 3, regions_item)

                    # Mask
                    mask_item = QTableWidgetItem("Yes" if layer.mask else "No")
                    mask_item.setBackground(QtBrush(QColor(COLORS['bg_medium'])))
                    mask_item.setForeground(QtBrush(QColor(COLORS['text_primary'])))
                    self.table.setItem(row, 4, mask_item)
