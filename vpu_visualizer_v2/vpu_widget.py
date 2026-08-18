"""
VPU Visualizer 2.0 VPU Widgets
The VPU card and its mixer/pipe matrix. The pipe-cell grid is the core
visualization and keeps its bordered-cell look; everything around it is flat.
"""

import os
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor

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
    'status_inactive': '#323f48',

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
    'cap_off': '#323f48',
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
# Capacity "weight" - same DUAL/4K/5K keys as CAPACITY_ICONS, expressed as the
# pipe-count number shown in the weight chip instead of an icon graphic.
CAPACITY_WEIGHTS = {
    'DUAL': 1,
    '4K': 2,
    '5K': 4,
}
CF_ICON_PATH = os.path.join(ICONS_DIR, "cf.png").replace("\\", "/")
# Sourced from the Web RCS app bundle's own icon sprite (aw-ui/icons/svg/stereo-3d-14.svg,
# <symbol id="stereo-3d-14">), recolored to the app accent and rasterized to PNG.
STEREO3D_ICON_PATH = os.path.join(ICONS_DIR, "stereo3d.png").replace("\\", "/")
REGION_ICON_PATH = os.path.join(ICONS_DIR, "region.png").replace("\\", "/")
SCREEN_ICON_PATH = os.path.join(ICONS_DIR, "screens.png").replace("\\", "/")
MASK_ICON_PATH = os.path.join(ICONS_DIR, "mask.png").replace("\\", "/")
MIXER_ICON_PATH = os.path.join(ICONS_DIR, "mixer.png").replace("\\", "/")
SPLIT_ICON_PATH = os.path.join(ICONS_DIR, "split.png").replace("\\", "/")
WEIGHT_ICON_PATH = os.path.join(ICONS_DIR, "weight.png").replace("\\", "/")
WEIGHT_CHIP_COLOR = "#602799"


def format_regions(regions) -> str:
    """Format a layer's region indices as 'R1, R2' - never 'R 1, 2'."""
    return ", ".join(f"R{r}" for r in regions)


def get_capacity_icon_path(capability: str):
    """Filesystem path of the capacity icon for a capability value, or None."""
    filename = CAPACITY_ICONS.get(str(capability).upper()) if capability else None
    if not filename:
        return None
    return os.path.join(ICONS_DIR, filename).replace("\\", "/")


def get_capacity_weight(capability: str):
    """Pipe-count weight (1/2/4) for a capability value, or None if unmapped."""
    return CAPACITY_WEIGHTS.get(str(capability).upper()) if capability else None


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


def get_region_html(regions) -> str:
    """Get an HTML snippet (icon + 'R1, R2' label) for a layer's regions."""
    return f'<img src="{REGION_ICON_PATH}" width="14" height="14"> {format_regions(regions)}'


# A mixer's "channel" property is only meaningful for screens that are
# stereoscopic 3D-enabled, where it picks the eye: 0 = left, 1 = right.
# On any other screen it's not a real signal (always reads 0) - see
# ARCHITECTURE.md's enum reference and the investigation that led here.
STEREO_CHANNEL_EYES = {0: "left eye", 1: "right eye"}


def format_stereo_channel(channel) -> str:
    """Format a mixer's channel value for a stereo-3D screen, e.g. 'Channel: 0 (left eye)'."""
    eye = STEREO_CHANNEL_EYES.get(channel)
    return f"Channel: {channel} ({eye})" if eye else f"Channel: {channel}"


def get_stereo_channel_html(channel) -> str:
    """Get an HTML snippet (stereo-3d icon + channel label) for a mixer's channel."""
    return f'<img src="{STEREO3D_ICON_PATH}" width="14" height="14"> {format_stereo_channel(channel)}'


# Shared grace period for both the floating tooltip and the dim/border hover
# state (see MainWindow's own hover-clear timer): adjacent cells are
# separated by thin layout gaps, so the cursor briefly leaves every widget
# while crossing between them. Clearing state immediately on that crossing
# would flash the tooltip and the dim/border highlight off and back on;
# deferring the clear lets the next cell's enter event cancel it first, so
# both read as continuous while still reacting effectively instantly
# (imperceptibly so) once the mouse genuinely leaves the grid.
HOVER_GRACE_MS = 75


class _CellTooltip(QLabel):
    """Floating tooltip for pipe cells: shows instantly, tracks the cursor while
    the mouse moves, and hides on leave - unlike QToolTip, which delays both
    showing and hiding and stays put once shown. See HOVER_GRACE_MS for why
    hiding is debounced rather than immediate."""

    OFFSET_X = 18
    OFFSET_Y = 18
    HIDE_DELAY_MS = HOVER_GRACE_MS

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {PALETTE['surface_alt']};
                color: {PALETTE['text']};
                border: 1px solid {PALETTE['border_soft']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
        """)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_at(self, html: str, global_pos: QPoint):
        self._hide_timer.stop()
        self.setText(html)
        self.adjustSize()
        self.move(self._clamped(global_pos))
        self.show()
        self.raise_()

    def move_to(self, global_pos: QPoint):
        if self.isVisible():
            self._hide_timer.stop()
            self.move(self._clamped(global_pos))

    def hide_soon(self):
        """Hide after a short grace period, cancelable by a fresh show_at()."""
        self._hide_timer.start(self.HIDE_DELAY_MS)

    def _clamped(self, global_pos: QPoint) -> QPoint:
        """Offset the tooltip from the cursor, flipping to the other side of
        the cursor if it would otherwise run off the screen."""
        pos = QPoint(global_pos.x() + self.OFFSET_X, global_pos.y() + self.OFFSET_Y)
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            if pos.x() + self.width() > geo.right():
                pos.setX(global_pos.x() - self.OFFSET_X - self.width())
            if pos.y() + self.height() > geo.bottom():
                pos.setY(global_pos.y() - self.OFFSET_Y - self.height())
        return pos


_cell_tooltip = None


def _get_cell_tooltip() -> "_CellTooltip":
    """Lazily-created singleton tooltip widget shared by every pipe cell."""
    global _cell_tooltip
    if _cell_tooltip is None:
        _cell_tooltip = _CellTooltip()
    return _cell_tooltip


class PipeCellWidget(QFrame):
    """Widget representing one or more contiguous output pipe columns for a mixer.

    Carries the full mixer content (color, screen/layer text, tooltip) when
    the mixer actually uses these pipes. Pipes that share the same data
    (same mixer, same used/unused state, adjacent columns) are merged into
    a single wider cell instead of duplicating the content across cells.
    """

    CELL_SIZE = 32
    # Opacity tiers applied while a layer is hovered elsewhere in the grid:
    # cells on the same screen (but a different layer) dim by 70%, cells on
    # any other screen dim by 90%, so the hovered layer reads clearly and its
    # screen-mates stay just visible enough to place it in context.
    FULL_OPACITY = 1.0
    SAME_SCREEN_DIM_OPACITY = 0.85
    OTHER_SCREEN_DIM_OPACITY = 0.3
    BORDER_COLOR = "#ffffff"

    cell_hovered = pyqtSignal(object)
    cell_left = pyqtSignal()

    def __init__(self, scaler: Scaler, pipe_ids, model=None, parent=None):
        super().__init__(parent)
        self.scaler = scaler
        self.model = model  # VPUModel, for the stereo-3D screen lookup in _get_tooltip
        self.pipe_ids = list(pipe_ids)
        self.opacity = self.FULL_OPACITY
        self.bordered = False

        self.setFixedHeight(self.CELL_SIZE)
        self.setMinimumWidth(self.CELL_SIZE * len(self.pipe_ids))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

        self.update_display()

    def is_used(self) -> bool:
        """Whether this mixer actually uses these pipes."""
        value = self.scaler.pipes.get(self.pipe_ids[0])
        return bool(value) and value != "NONE"

    def update_display(self):
        """Refresh appearance (repainted in paintEvent) and, if the cursor is
        currently over this cell, the live tooltip content."""
        self.update()
        if self.underMouse():
            self._sync_tooltip()

    def set_dim_and_border(self, opacity: float, bordered: bool):
        """opacity fades the cell to enhance readability of another hovered
        layer (see the tier constants above); bordered draws the white
        highlight border for the exact screen+layer+slice match."""
        if self.opacity != opacity or self.bordered != bordered:
            self.opacity = opacity
            self.bordered = bordered
            self.update()

    def enterEvent(self, event):
        """Handle mouse enter event."""
        if self.is_used() and self.scaler.screen is not None and self.scaler.layer is not None:
            self.cell_hovered.emit(self.scaler)
        self._sync_tooltip()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave event."""
        self.cell_left.emit()
        _get_cell_tooltip().hide_soon()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event):
        """Keep the tooltip tracking the cursor while hovering this cell - but
        only when it has content. move_to() only cancels a pending hide, it
        never schedules one, so calling it unconditionally here let a stray
        tooltip (still alive from a just-left used cell, within its grace
        period) get pinned open indefinitely by mouse movement over an empty
        cell that never itself asks for a hide."""
        if self.is_used():
            _get_cell_tooltip().move_to(QCursor.pos())
        else:
            _get_cell_tooltip().hide_soon()
        super().mouseMoveEvent(event)

    def _sync_tooltip(self):
        """Show/update the tooltip at the current cursor position, or hide it
        when this pipe has nothing to show."""
        tooltip = self._get_tooltip()
        if tooltip:
            _get_cell_tooltip().show_at(tooltip, QCursor.pos())
        else:
            _get_cell_tooltip().hide_soon()

    def _get_tooltip(self) -> str:
        """Generate tooltip HTML. Empty (no tooltip) when this pipe is not used."""
        if not self.is_used():
            return ""

        s = self.scaler
        lines = []

        screen = self.model.get_screen(s.screen) if self.model and s.screen else None

        if s.screen:
            if screen and screen.label:
                lines.append(f"Screen {s.screen} - {screen.label}")
            else:
                lines.append(f"Screen {s.screen}")

        if s.layer:
            lines.append(f"Layer {s.layer}")

        capacity_line = get_capacity_html(s.capability)
        if is_truthy_capa(s.cutnfill_capa):
            capacity_line += " " + get_cutnfill_html()
        lines.append(capacity_line)

        lines.append("Mixer" if is_truthy_capa(s.seamless_capa) else "Split")

        if s.layer and screen:
            layer_obj = screen.get_layer(s.layer)
            if layer_obj and layer_obj.regions and screen.has_multiple_regions():
                lines.append(get_region_html(layer_obj.regions))

        if s.channel is not None and screen and screen.is_stereo_3d:
            lines.append(get_stereo_channel_html(s.channel))

        if s.slice is not None:
            lines.append(f"Slice: {s.slice}")

        return "<html>" + "<br>".join(lines) + "</html>"

    def paintEvent(self, event):
        """Custom paint for background, border and mixer content. Cells have
        no border by default; the only border shown is the white highlight on
        an exact screen+layer+slice match with the hovered cell. A dimmed
        cell is painted at reduced opacity so the hovered layer reads clearly
        against the rest of the grid."""
        used = self.is_used()

        if used and self.scaler.is_enabled:
            if self.scaler.layer:
                bg_color = get_layer_color(self.scaler.layer)
                text_color = get_layer_text_color(self.scaler.layer)
            elif self.scaler.screen:
                bg_color = get_screen_color(self.scaler.screen)
                text_color = COLORS['text_primary']
            else:
                bg_color = COLORS['status_active']
                text_color = COLORS['text_primary']
        else:
            bg_color = COLORS['bg_dark']
            text_color = COLORS['text_primary']

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setOpacity(self.opacity)

        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(bg_color))
        if self.bordered:
            painter.setPen(QPen(QColor(self.BORDER_COLOR), 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 5, 5)

        if not used:
            if len(self.pipe_ids) > 1:
                self._paint_empty_dividers(painter)
            painter.end()
            return

        # Draw text with proper color (small cell, but keep text prominent)
        painter.setPen(QColor(text_color))
        font = QFont()
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)

        if self.scaler.is_enabled and self.scaler.screen:
            text = f"S{self.scaler.screen}"
            if self.scaler.layer:
                text += f"\nL{self.scaler.layer}"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        else:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self.scaler.id))

        painter.end()

    def _paint_empty_dividers(self, painter):
        """Draw thin vertical lines at each pipe boundary inside a merged empty
        cell, so the number of joined (unused) pipes stays visible."""
        pen = QPen(QColor(COLORS['status_inactive']))
        pen.setWidth(1)
        painter.setPen(pen)

        segment_width = self.width() / len(self.pipe_ids)
        for i in range(1, len(self.pipe_ids)):
            x = round(segment_width * i)
            painter.drawLine(x, 3, x, self.height() - 3)


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

    def __init__(self, device: Device, vpu: VPU, model=None, parent=None):
        super().__init__(parent)
        self.device = device
        self.vpu = vpu
        self.model = model  # VPUModel, forwarded to pipe cells for the stereo-3D lookup
        self.pipe_widgets = []
        self.dev_color = device_color(device.id)
        self._device_highlight = False

        self.setMinimumWidth(300)
        self._apply_card_style()
        self.setup_ui()

    def _apply_card_style(self):
        """The card always has a border - only its color changes for the
        hovered/focus state (direct hover or a sibling card of the same
        hovered device), never the background."""
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
            # Tight vertical margin/spacing: the two rows of a pair (odd+even
            # mixer) are usually tied together, so they should read as one
            # unit - the bigger gap belongs between different pairs (see
            # rows_layout.setSpacing above).
            pair_layout.setContentsMargins(4, 2, 4, 2)
            pair_layout.setSpacing(1)

            for scaler in pair_scalers:
                row_layout = QHBoxLayout()
                row_layout.setSpacing(0)

                for pipe_run in self._compute_pipe_runs(scaler):
                    pipe_widget = PipeCellWidget(scaler, pipe_run, self.model)
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

    def set_hover_state(self, scaler: Optional[Scaler]):
        """Update every cell's dim/border state for the given hovered scaler.
        Empty (unused) pipe slots are never dimmed - only active mixers
        compete for attention. Among active cells, the hovered layer stays
        at full opacity, other layers on the same screen dim by 70%, and
        cells on any other screen dim by 90%. Every cell on the same
        screen+layer (regardless of slice) gets the white border highlight.
        Pass None to clear all dim/border state."""
        for widget in self.pipe_widgets:
            if scaler is None or not widget.is_used():
                widget.set_dim_and_border(opacity=PipeCellWidget.FULL_OPACITY, bordered=False)
                continue
            s = widget.scaler
            same_screen = s.screen == scaler.screen
            same_layer = same_screen and s.layer == scaler.layer
            if same_layer:
                opacity = PipeCellWidget.FULL_OPACITY
            elif same_screen:
                opacity = PipeCellWidget.SAME_SCREEN_DIM_OPACITY
            else:
                opacity = PipeCellWidget.OTHER_SCREEN_DIM_OPACITY
            widget.set_dim_and_border(opacity=opacity, bordered=same_layer)
