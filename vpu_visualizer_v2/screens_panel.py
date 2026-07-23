"""
Screens panel: merged Screens + Layers + Summary view.

- Overview strip with aggregate stats (replaces the old text Summary tab)
- Search and filter bar (free text, screen, capability)
- One card per active screen; each layer is a row with icons/chips for
  capability, mask, regions, and its VPU mapping (device / VPU / mixer / pipes)
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QLineEdit, QComboBox, QSizePolicy
)

from theme import PALETTE, device_color, make_chip
from vpu_widget import (
    get_layer_color, get_layer_text_color, get_screen_color,
    get_capability_color, get_capacity_icon_path, is_truthy_capa
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
    """Icon for DUAL/4K/5K capabilities, text chip otherwise."""
    icon_path = get_capacity_icon_path(capability)
    if icon_path:
        label = QLabel()
        label.setPixmap(QPixmap(icon_path).scaled(
            36, 16, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        label.setToolTip(f"Capability: {capability}")
        label.setStyleSheet("background: transparent;")
        return label
    text = str(capability) if capability else "–"
    return make_chip(text, get_capability_color(capability),
                     tooltip=f"Capability: {capability}")


class LayerRow(QWidget):
    """One layer of a screen: colored layer chip + property icons + VPU mapping."""

    def __init__(self, screen, layer, mappings, parent=None):
        super().__init__(parent)
        self.search_tokens = self._build_search_tokens(screen, layer, mappings)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        layer_chip = make_chip(
            f"L{layer.id}", get_layer_color(layer.id), get_layer_text_color(layer.id),
            tooltip=f"Layer {layer.id}")
        layer_chip.setMinimumWidth(34)
        layer_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(layer_chip)

        layout.addWidget(_capability_widget(layer.capability))

        if layer.mask:
            layout.addWidget(make_chip("MASK", "#3a3f5c", PALETTE['text'],
                                       tooltip="Mask enabled"))

        if layer.regions:
            regions_text = ", ".join(map(str, layer.regions))
            layout.addWidget(make_chip(f"R {regions_text}", PALETTE['surface_alt'],
                                       PALETTE['text_dim'],
                                       tooltip=f"Used in regions: {regions_text}"))

        layout.addStretch()

        # VPU mapping chips: which device/VPU/mixer serves this layer
        if mappings:
            for device, vpu, scaler in mappings:
                pipes = [str(v) for v in scaler.pipes.values() if v and v != "NONE"]
                pipes_text = ",".join(dict.fromkeys(pipes)) or "–"
                text = f"D{device.id}·V{vpu.vpu_id}·M{scaler.id} → P{pipes_text}"
                tooltip_lines = [
                    f"Device {device.id}, VPU {vpu.vpu_id}, Mixer {scaler.id}",
                    f"Capability: {scaler.capability}",
                    "Mode: " + ("Mixer (seamless)" if is_truthy_capa(scaler.seamless_capa) else "Split"),
                ]
                if scaler.channel is not None:
                    tooltip_lines.append(f"Channel: {scaler.channel}")
                if scaler.slice is not None:
                    tooltip_lines.append(f"Slice: {scaler.slice}")
                if is_truthy_capa(scaler.cutnfill_capa):
                    tooltip_lines.append("Cut & fill")
                tooltip_lines.append(f"Pipes: {pipes_text}")

                color = device_color(device.id)
                chip = make_chip(text, "rgba(255,255,255,0.05)", color,
                                 tooltip="\n".join(tooltip_lines))
                layout.addWidget(chip)
        else:
            layout.addWidget(make_chip("unmapped", PALETTE['surface_alt'],
                                       PALETTE['muted'],
                                       tooltip="No enabled mixer serves this layer"))

    @staticmethod
    def _build_search_tokens(screen, layer, mappings) -> str:
        tokens = [f"s{screen.id}", f"screen {screen.id}",
                  f"l{layer.id}", f"layer {layer.id}",
                  str(layer.capability or "")]
        if layer.mask:
            tokens.append("mask")
        tokens.extend(str(r) for r in layer.regions)
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


class ScreenCard(QFrame):
    """Card for one active screen with its layer rows."""

    def __init__(self, screen, model, parent=None):
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

        dot = QLabel("●")
        dot.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
        header.addWidget(dot)

        title = QLabel(f"Screen {screen.id}")
        title.setStyleSheet("font-weight: 600; font-size: 14px; background: transparent;")
        header.addWidget(title)

        if screen.optimized:
            header.addWidget(make_chip("⚡ optimized", "rgba(232,179,62,0.15)",
                                       PALETTE['amber'], tooltip="Screen is optimized"))

        n = len(screen.layers)
        count = QLabel(f"{n} layer" + ("s" if n != 1 else ""))
        count.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 11px; background: transparent;")
        header.addWidget(count)

        header.addStretch()
        layout.addLayout(header)

        for layer in screen.layers:
            mappings = model.get_layer_mappings(screen.id, layer.id)
            row = LayerRow(screen, layer, mappings)
            self.layer_rows.append(row)
            layout.addWidget(row)

        self._search_tokens = f"s{screen.id} screen {screen.id}".lower()

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
            row.setVisible(visible)
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
        self.stat_mixers = StatCard("Mixers in use")
        self.stat_pipes = StatCard("Pipes in use")
        self.stat_screens = StatCard("Active screens")
        self.stat_layers = StatCard("Layers")
        for card in (self.stat_devices, self.stat_vpus, self.stat_mixers,
                     self.stat_pipes, self.stat_screens, self.stat_layers):
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

        for screen in screens:
            card = ScreenCard(screen, self.model)
            self.cards.append(card)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        stats = self.model.get_stats()
        self.stat_devices.set_value(str(stats["devices"]))
        self.stat_vpus.set_value(str(stats["vpus"]))
        self.stat_mixers.set_value(f"{stats['mixers_used']}/{stats['mixers_total']}")
        self.stat_pipes.set_value(str(stats["pipes_used"]))
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
