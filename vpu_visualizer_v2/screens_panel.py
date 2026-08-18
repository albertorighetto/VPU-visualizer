"""
Screens panel: merged Screens + Layers + Summary view.

- Overview strip with aggregate stats (replaces the old text Summary tab)
- Search and filter bar (free text, screen, capability)
- One card per active screen; each layer is a row with icons/chips for
  capability, mask, regions, and its VPU mapping (device / VPU / mixer / pipes)
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame, QScrollArea,
    QLineEdit, QComboBox, QSizePolicy
)

from theme import PALETTE, device_color, make_chip
from vpu_widget import (
    get_layer_color, get_layer_text_color, get_screen_color,
    get_capability_color, get_capacity_weight, is_truthy_capa,
    STEREO3D_ICON_PATH, REGION_ICON_PATH, SCREEN_ICON_PATH, MASK_ICON_PATH,
    MIXER_ICON_PATH, SPLIT_ICON_PATH, WEIGHT_ICON_PATH, WEIGHT_CHIP_COLOR,
    format_stereo_channel
)


class StatCard(QFrame):
    """Small stat tile: big value + caption."""

    def __init__(self, caption: str, parent=None):
        super().__init__(parent)
        self.setProperty("card", True)
        self.setMinimumWidth(110)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(2)

        self.value_label = QLabel("–")
        self.value_label.setStyleSheet(
            "font-size: 20px; font-weight: 700; background: transparent;")
        layout.addWidget(self.value_label)

        caption_label = QLabel(caption)
        caption_label.setStyleSheet(
            f"color: {PALETTE['muted']}; font-size: 11px; background: transparent;")
        layout.addWidget(caption_label)

    def set_value(self, text: str):
        self.value_label.setText(text)


def _capability_widget(capability) -> QWidget:
    """Weight chip (purple, weight icon + pipe-count number) for DUAL/4K/5K
    capabilities, text chip otherwise."""
    weight = get_capacity_weight(capability)
    if weight is not None:
        return _icon_chip(WEIGHT_ICON_PATH, f"<b>{weight}</b>", WEIGHT_CHIP_COLOR, "#ffffff",
                          tooltip=f"Capability: {capability}")
    text = f"<b>{capability}</b>" if capability else "<b>–</b>"
    return make_chip(text, get_capability_color(capability),
                     tooltip=f"Capability: {capability}")


def _layer_mode_text(mappings):
    """'Mixer' or 'Split', from the first mixer mapped to this layer (mixers
    serving the same layer share the same mode in practice). None if unmapped."""
    if not mappings:
        return None
    _, _, scaler = mappings[0]
    return "Mixer" if is_truthy_capa(scaler.seamless_capa) else "Split"


def _icon_chip(icon_path: str, text: str, bg: str, fg: str, tooltip: str = None,
               text_width: int = None) -> QWidget:
    """Chip-styled pill (same look as make_chip) with a small icon before the text.
    `text_width`, if given, fixes (and centers) the text label at that width so
    chips built from different text of the same family (e.g. Mixer/Split) always
    render at an identical total width."""
    container = QWidget()
    container.setStyleSheet(f"background-color: {bg}; border-radius: 4px;")
    row = QHBoxLayout(container)
    row.setContentsMargins(7, 2, 7, 2)
    row.setSpacing(4)

    icon = QLabel()
    icon.setPixmap(QPixmap(icon_path).scaled(
        12, 12, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation))
    icon.setStyleSheet("background: transparent;")
    row.addWidget(icon)

    label = QLabel(text)
    label.setStyleSheet(f"color: {fg}; font-size: 11px; font-weight: 600; background: transparent;")
    if text_width is not None:
        label.setFixedWidth(text_width)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    row.addWidget(label)

    if tooltip:
        container.setToolTip(tooltip)
    return container


_MODE_LABEL_WIDTH = None


def _mode_label_width() -> int:
    """Fixed label width covering the wider of 'Mixer'/'Split' text, so the mode
    chip is the same total width regardless of which one it shows."""
    global _MODE_LABEL_WIDTH
    if _MODE_LABEL_WIDTH is None:
        font = QFont()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.DemiBold)
        metrics = QFontMetrics(font)
        _MODE_LABEL_WIDTH = max(metrics.horizontalAdvance("Mixer"),
                                metrics.horizontalAdvance("Split"))
    return _MODE_LABEL_WIDTH


def _screen_icon_widget() -> QWidget:
    """Screens icon shown before the screen title."""
    label = QLabel()
    label.setPixmap(QPixmap(SCREEN_ICON_PATH).scaled(
        16, 16, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation))
    label.setStyleSheet("background: transparent;")
    return label


def _stereo3d_widget() -> QWidget:
    """Icon badge for a stereoscopic 3D screen (Web RCS's own stereo-3d icon)."""
    label = QLabel()
    label.setPixmap(QPixmap(STEREO3D_ICON_PATH).scaled(
        20, 20, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation))
    label.setToolTip("Stereoscopic 3D")
    label.setStyleSheet("background: transparent;")
    return label


def _mask_icon_widget() -> QWidget:
    """Icon badge shown when a layer has masking enabled."""
    label = QLabel()
    label.setPixmap(QPixmap(MASK_ICON_PATH).scaled(
        16, 16, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation))
    label.setToolTip("Mask enabled")
    label.setStyleSheet("background: transparent;")
    return label


def _reserve_size_when_hidden(widget: QWidget):
    """Make a hidden widget keep occupying its layout space - used to turn a
    real chip/badge into a transparent placeholder that reserves its column."""
    policy = widget.sizePolicy()
    policy.setRetainSizeWhenHidden(True)
    widget.setSizePolicy(policy)


def _region_chip(region_id) -> QWidget:
    """Single region badge: icon + 'Rn'."""
    container = QWidget()
    container.setStyleSheet("background: transparent;")
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(3)

    icon = QLabel()
    icon.setPixmap(QPixmap(REGION_ICON_PATH).scaled(
        14, 14, Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation))
    icon.setStyleSheet("background: transparent;")
    row.addWidget(icon)

    text = QLabel(f"R{region_id}")
    text.setStyleSheet(f"color: {PALETTE['text_dim']}; font-size: 11px; background: transparent;")
    row.addWidget(text)

    return container


def _mapping_chip_placeholder(device_id: int, vpu_id: int) -> QWidget:
    """Invisible chip reserving the same width as a real Device/VPU chip, so a
    layer that skips a device+VPU used elsewhere in the screen doesn't collapse
    that column and throw off alignment with other layer rows."""
    chip = make_chip(f"Device {device_id} - VPU {vpu_id}", "transparent", "transparent")
    _reserve_size_when_hidden(chip)
    chip.setVisible(False)
    return chip


def _mapping_chip(screen, device, vpu, scalers) -> QWidget:
    """One chip for a device/VPU combination serving a layer (possibly through
    several mixers on that same device+VPU, each detailed in the tooltip)."""
    mixer_blocks = []
    for scaler in scalers:
        pipes = [str(v) for v in scaler.pipes.values() if v and v != "NONE"]
        pipes_text = ",".join(dict.fromkeys(pipes)) or "–"
        block_lines = [
            f"Mixer {scaler.id}",
            f"Capability: {scaler.capability}",
            "Mode: " + ("Mixer (seamless)" if is_truthy_capa(scaler.seamless_capa) else "Split"),
        ]
        if scaler.channel is not None and screen.is_stereo_3d:
            block_lines.append(format_stereo_channel(scaler.channel))
        if scaler.slice is not None:
            block_lines.append(f"Slice: {scaler.slice}")
        if is_truthy_capa(scaler.cutnfill_capa):
            block_lines.append("Cut & fill")
        block_lines.append(f"Pipes: {pipes_text}")
        mixer_blocks.append("\n".join(block_lines))

    text = f"Device {device.id} - VPU {vpu.vpu_id}"
    tooltip = "\n\n".join(mixer_blocks)
    color = device_color(device.id)
    return make_chip(text, "rgba(255,255,255,0.05)", color, tooltip=tooltip)


class LayerRow:
    """One layer of a screen: a left part (layer chip + capacity/mask, built as
    a normal flowing row, untouched), then a regions group and a VPU mapping
    chip group. The caller places all of these into a shared grid so each
    group starts at the same x position across every layer row of the screen
    card - a layout effect only, the columns have no visible border/background.

    Both groups are built from the globally-valid key sets (every region ID
    used by any multi-region screen, every device+VPU in the whole system -
    see ScreensPanel._rebuild), not just the ones this screen/layer actually
    uses: a slot for a key this screen/layer doesn't use gets a transparent
    placeholder instead of being omitted, so e.g. region 3 or device 2's VPU 3
    always lands in the same relative slot for every layer row of every
    screen card, keeping cards aligned with each other as well as internally.

    Within the VPU chips group, chips are ordered by each device+VPU's global
    position in the system (device-major, vpu-minor - see
    VPUModel.ordered_vpu_keys)."""

    def __init__(self, screen, layer, mappings, vpu_keys, all_region_ids):
        self.search_tokens = self._build_search_tokens(screen, layer, mappings)

        self.left_widget = QWidget()
        self.left_widget.setStyleSheet("background: transparent;")
        left = QHBoxLayout(self.left_widget)
        left.setContentsMargins(0, 2, 0, 2)
        left.setSpacing(8)

        layer_chip = make_chip(
            f"L{layer.id}", get_layer_color(layer.id), get_layer_text_color(layer.id),
            tooltip=f"Layer {layer.id}")
        layer_chip.setMinimumWidth(34)
        layer_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(layer_chip)

        left.addWidget(_capability_widget(layer.capability))

        mode_text = _layer_mode_text(mappings)
        if mode_text:
            mode_icon = MIXER_ICON_PATH if mode_text == "Mixer" else SPLIT_ICON_PATH
            left.addWidget(_icon_chip(mode_icon, mode_text, PALETTE['border'], PALETTE['text'],
                                      tooltip=f"Mode: {mode_text}",
                                      text_width=_mode_label_width()))

        if layer.mask:
            left.addWidget(_mask_icon_widget())

        # Built whenever *any* visible screen uses multiple regions, even for
        # a screen/layer that doesn't itself - with every cell hidden in that
        # case - rather than left as None. An empty grid cell (nothing ever
        # added at that (row, column)) can size/space slightly differently
        # under Qt than a cell holding a real, retain-size-when-hidden widget,
        # which was the source of the alignment drift for no-regions screens.
        # Keeping every row's regions group structurally identical (same
        # chips, same order) guarantees the column lines up pixel-for-pixel
        # across every screen card.
        self.regions_widget = None
        if all_region_ids:
            self.regions_widget = QWidget()
            self.regions_widget.setStyleSheet("background: transparent;")
            regions_layout = QHBoxLayout(self.regions_widget)
            regions_layout.setContentsMargins(0, 0, 0, 0)
            regions_layout.setSpacing(6)

            screen_region_ids = ({str(r) for r in screen.region_validity}
                                 if screen.has_multiple_regions() else set())
            layer_region_ids = {str(r) for r in layer.regions}
            for region_id in all_region_ids:
                cell = _region_chip(region_id)
                if region_id not in screen_region_ids or region_id not in layer_region_ids:
                    _reserve_size_when_hidden(cell)
                    cell.setVisible(False)
                regions_layout.addWidget(cell)

        self.chips_widget = QWidget()
        self.chips_widget.setStyleSheet("background: transparent;")
        chips = QHBoxLayout(self.chips_widget)
        chips.setContentsMargins(0, 0, 0, 0)
        chips.setSpacing(6)

        if mappings:
            groups = {}
            for device, vpu, scaler in mappings:
                key = (device.id, vpu.vpu_id)
                groups.setdefault(key, (device, vpu, []))[2].append(scaler)

            for key in vpu_keys:
                if key in groups:
                    device, vpu, scalers = groups[key]
                    chips.addWidget(_mapping_chip(screen, device, vpu, scalers))
                else:
                    chips.addWidget(_mapping_chip_placeholder(*key))
        else:
            chips.addWidget(make_chip("unmapped", PALETTE['surface_alt'],
                                      PALETTE['muted'],
                                      tooltip="No enabled mixer serves this layer"))

    @staticmethod
    def _build_search_tokens(screen, layer, mappings) -> str:
        tokens = [f"s{screen.id}", f"screen {screen.id}",
                  f"l{layer.id}", f"layer {layer.id}",
                  str(layer.capability or "")]
        if layer.mask:
            tokens.append("mask")
        if screen.has_multiple_regions():
            tokens.extend(f"r{r}" for r in layer.regions)
        for device, vpu, scaler in mappings:
            tokens.extend([f"d{device.id}", f"device {device.id}",
                           f"v{vpu.vpu_id}", f"vpu {vpu.vpu_id}",
                           f"m{scaler.id}", f"mixer {scaler.id}",
                           str(scaler.capability or "")])
        return " ".join(tokens).lower()

    def matches(self, search: str, capability: str) -> bool:
        if search and search not in self.search_tokens:
            return False
        if capability and capability.lower() not in self.search_tokens:
            return False
        return True

    def set_visible(self, visible: bool):
        self.left_widget.setVisible(visible)
        if self.regions_widget is not None:
            self.regions_widget.setVisible(visible)
        self.chips_widget.setVisible(visible)


class ScreenCard(QFrame):
    """Card for one active screen with its layer rows."""

    def __init__(self, screen, model, vpu_keys, all_region_ids, parent=None):
        super().__init__(parent)
        self.screen_id = screen.id
        self.setProperty("card", True)
        self.layer_rows = []

        color = get_screen_color(screen.id)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        header = QHBoxLayout()
        header.setSpacing(8)

        header.addWidget(_screen_icon_widget())

        title = QLabel(f"Screen {screen.id}")
        title.setStyleSheet(f"font-weight: 600; font-size: 14px; background: transparent;")
        header.addWidget(title)

        n = len(screen.layers)
        count = QLabel(f"{n} layer" + ("s" if n != 1 else ""))
        count.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 11px; background: transparent;")
        header.addWidget(count)
        
        if screen.optimized:
            header.addWidget(make_chip("⚡ optimized", "rgba(242,113,28,0.15)",
                                       PALETTE['amber'], tooltip="Screen is optimized"))

        if screen.is_stereo_3d:
            header.addWidget(_stereo3d_widget())

        header.addStretch()
        layout.addLayout(header)

        mappings_by_layer = {
            layer.id: model.get_layer_mappings(screen.id, layer.id) for layer in screen.layers
        }

        # Layer rows share one grid: column 0 is each row's left part, column 1
        # the regions group, column 2 the VPU chips group - each group starts
        # at the same x position across rows. Columns 1/2 are always reserved
        # (even for a screen without multiple regions, or a layer that maps
        # nothing there) and built from the globally-valid key sets passed in
        # by ScreensPanel, so cards line up with each other, not just
        # internally - set_shared_column_widths() below finishes the job by
        # forcing column 0/1 to the same width on every card. Explicit
        # left/vcenter alignment keeps each cell at its natural size instead
        # of stretching.
        self._grid = grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        cell_align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        regions_col = 1
        chips_col = 2

        for row_index, layer in enumerate(screen.layers):
            row = LayerRow(screen, layer, mappings_by_layer[layer.id], vpu_keys, all_region_ids)
            self.layer_rows.append(row)
            grid.addWidget(row.left_widget, row_index, 0, cell_align)
            if row.regions_widget is not None:
                grid.addWidget(row.regions_widget, row_index, regions_col, cell_align)
            grid.addWidget(row.chips_widget, row_index, chips_col, cell_align)

        # Without explicit stretch factors, QGridLayout shares out any leftover
        # width (the card is wider than the content needs) across all columns,
        # which pushes the regions/chips groups apart with unwanted gaps. Pin
        # every real column to 0 and dump all leftover width into a trailing
        # spacer column instead, so the groups stay packed tight on the left.
        for col in range(chips_col + 1):
            grid.setColumnStretch(col, 0)
        grid.setColumnStretch(chips_col + 1, 1)

        layout.addLayout(grid)

        self._search_tokens = f"s{screen.id} screen {screen.id}".lower()

    def left_column_width(self) -> int:
        return max((row.left_widget.sizeHint().width() for row in self.layer_rows), default=0)

    def regions_column_width(self) -> int:
        return max((row.regions_widget.sizeHint().width() for row in self.layer_rows
                    if row.regions_widget is not None), default=0)

    def set_shared_column_widths(self, left_width: int, regions_width: int):
        """Force this card's left/regions columns to the widths shared across
        every visible screen card, so layer rows align between cards as well
        as within one (see ScreensPanel._rebuild)."""
        self._grid.setColumnMinimumWidth(0, left_width)
        self._grid.setColumnMinimumWidth(1, regions_width)

    def apply_filter(self, search: str, capability: str) -> bool:
        """Show/hide layer rows; returns True if the card stays visible."""
        if not self.layer_rows:
            # A screen without layers stays visible unless a filter excludes it
            if capability:
                return False
            return not search or search in self._search_tokens

        any_visible = False
        for row in self.layer_rows:
            visible = row.matches(search, capability)
            row.set_visible(visible)
            any_visible = any_visible or visible
        return any_visible


class ScreensPanel(QWidget):
    """Merged Screens + Layers + Summary tab."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self._seen_version = -1

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        # --- Overview strip ---
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        self.stat_devices = StatCard("Devices")
        self.stat_vpus = StatCard("VPUs")
        self.stat_vpu_usage = StatCard("VPU usage")
        self.stat_screens = StatCard("Active screens")
        self.stat_layers = StatCard("Layers")
        for card in (self.stat_devices, self.stat_vpus, self.stat_vpu_usage,
                     self.stat_screens, self.stat_layers):
            stats_row.addWidget(card)
        stats_row.addStretch()
        layout.addLayout(stats_row)

        # --- Filter bar ---
        filters = QHBoxLayout()
        filters.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search screens, layers, devices… (e.g. S1, L3, D2, 4K)")
        self.search_input.setClearButtonEnabled(True)
        filters.addWidget(self.search_input, 2)

        self.screen_combo = QComboBox()
        self.screen_combo.addItem("All screens", None)
        self.screen_combo.setMinimumWidth(120)
        filters.addWidget(self.screen_combo)

        self.cap_combo = QComboBox()
        self.cap_combo.addItem("All capabilities", "")
        for cap in ("DUAL", "4K", "5K", "8K"):
            self.cap_combo.addItem(cap, cap)
        self.cap_combo.setMinimumWidth(140)
        filters.addWidget(self.cap_combo)

        layout.addLayout(filters)

        # --- Screen cards ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.cards_layout = QVBoxLayout(self.container)
        self.cards_layout.setContentsMargins(0, 0, 8, 8)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.empty_label = QLabel("No active screens")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet(f"color: {PALETTE['muted']}; padding: 40px;")
        self.cards_layout.insertWidget(0, self.empty_label)

        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)

        self.cards = []

        self.search_input.textChanged.connect(self._apply_filters)
        self.screen_combo.currentIndexChanged.connect(self._apply_filters)
        self.cap_combo.currentIndexChanged.connect(self._apply_filters)

    def refresh(self):
        """Rebuild the panel if the model changed since the last refresh."""
        if self.model.version == self._seen_version:
            return
        self._seen_version = self.model.version
        self._rebuild()

    def _rebuild(self):
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards = []

        screens = self.model.active_screens()

        # Keep the screen filter combo in sync (preserving the selection)
        selected = self.screen_combo.currentData()
        self.screen_combo.blockSignals(True)
        self.screen_combo.clear()
        self.screen_combo.addItem("All screens", None)
        for screen in screens:
            self.screen_combo.addItem(f"Screen {screen.id}", screen.id)
            if screen.id == selected:
                self.screen_combo.setCurrentIndex(self.screen_combo.count() - 1)
        self.screen_combo.blockSignals(False)

        # Global key sets shared by every card, so the same device+VPU or
        # region ID always lands in the same column across all visible
        # screens, not just within one screen's own rows.
        vpu_keys = self.model.ordered_vpu_keys()
        multi_region_screens = [s for s in screens if s.has_multiple_regions()]
        all_region_ids = sorted(
            {str(r) for s in multi_region_screens for r in s.region_validity},
            key=lambda r: int(r))

        for screen in screens:
            card = ScreenCard(screen, self.model, vpu_keys, all_region_ids)
            self.cards.append(card)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        # Force every card's left/regions columns to the same width (the
        # widest across all cards), including cards with no regions column of
        # their own, so the VPU-chip group starts at an identical x position
        # on every screen card.
        max_left = max((c.left_column_width() for c in self.cards), default=0)
        max_regions = max((c.regions_column_width() for c in self.cards), default=0)
        for c in self.cards:
            c.set_shared_column_widths(max_left, max_regions)

        stats = self.model.get_stats()
        usage_pct = (stats["mixers_used"] / stats["mixers_total"] * 100) if stats["mixers_total"] else 0
        self.stat_devices.set_value(str(stats["devices"]))
        self.stat_vpus.set_value(str(stats["vpus"]))
        self.stat_vpu_usage.set_value(f"{usage_pct:.0f}%")
        self.stat_screens.set_value(str(stats["screens"]))
        self.stat_layers.set_value(str(stats["layers"]))

        self._apply_filters()

    def _apply_filters(self):
        search = self.search_input.text().strip().lower()
        screen_id = self.screen_combo.currentData()
        capability = self.cap_combo.currentData() or ""

        any_visible = False
        for card in self.cards:
            if screen_id is not None and card.screen_id != screen_id:
                card.setVisible(False)
                continue
            visible = card.apply_filter(search, capability)
            card.setVisible(visible)
            any_visible = any_visible or visible

        self.empty_label.setVisible(not any_visible)
        if not self.cards:
            self.empty_label.setText("No active screens")
        elif not any_visible:
            self.empty_label.setText("No layers match the current filters")
