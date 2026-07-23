"""
Log panel: timestamped, searchable, filterable protocol/debug log.

Features:
- Timestamps (HH:MM:SS.mmm) added on receipt
- Include filter (only rows containing text) and exclude filter
- Case sensitive / insensitive toggle
- Tag filter (SEND / RECV / INFO / ERROR / ...)
- Pause autoscroll, clear
- Entries are batched via a flush timer so protocol bursts stay smooth
"""

import re
from datetime import datetime

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox, QComboBox,
    QPushButton, QTableView, QHeaderView, QAbstractItemView, QLabel
)

from theme import PALETTE


TAG_PATTERN = re.compile(r"^\[(\w+)\]\s*(.*)", re.DOTALL)

TAG_COLORS = {
    "ERROR": PALETTE["red"],
    "SEND": "#5aa9e6",
    "RECV": "#3fd08b",
    "INFO": PALETTE["accent"],
    "PARSED": PALETTE["text_dim"],
    "CONNECTION": PALETTE["amber"],
}

MAX_ENTRIES = 20000


class LogTableModel(QAbstractTableModel):
    """Backing model: list of (timestamp, tag, message)."""

    HEADERS = ["Time", "Tag", "Message"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries = []
        self._mono = QFont("Consolas")
        self._mono.setStyleHint(QFont.StyleHint.Monospace)
        self._mono.setPointSize(9)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return 3

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        timestamp, tag, message = self.entries[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return (timestamp, tag, message)[col]
        if role == Qt.ItemDataRole.ForegroundRole:
            if col == 0:
                return QColor(PALETTE["muted"])
            if col == 1:
                return QColor(TAG_COLORS.get(tag, PALETTE["text_dim"]))
            if tag == "ERROR":
                return QColor(PALETTE["red"])
            return QColor(PALETTE["text"])
        if role == Qt.ItemDataRole.FontRole:
            return self._mono
        return None

    def append_entries(self, batch):
        """Append a batch of (timestamp, tag, message) tuples."""
        if not batch:
            return
        start = len(self.entries)
        self.beginInsertRows(QModelIndex(), start, start + len(batch) - 1)
        self.entries.extend(batch)
        self.endInsertRows()

        overflow = len(self.entries) - MAX_ENTRIES
        if overflow > 0:
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            del self.entries[:overflow]
            self.endRemoveRows()

    def clear(self):
        self.beginResetModel()
        self.entries.clear()
        self.endResetModel()


class LogFilterProxy(QSortFilterProxyModel):
    """Include/exclude text filtering with case toggle and tag filter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.include_text = ""
        self.exclude_text = ""
        self.case_sensitive = False
        self.tag = None  # None = all tags

    def set_filters(self, include_text: str, exclude_text: str,
                    case_sensitive: bool, tag):
        self.include_text = include_text
        self.exclude_text = exclude_text
        self.case_sensitive = case_sensitive
        self.tag = tag
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        timestamp, tag, message = self.sourceModel().entries[source_row]

        if self.tag and tag != self.tag:
            return False

        haystack = f"{tag} {message}"
        include = self.include_text
        exclude = self.exclude_text
        if not self.case_sensitive:
            haystack = haystack.lower()
            include = include.lower()
            exclude = exclude.lower()

        if include and include not in haystack:
            return False
        if exclude and exclude in haystack:
            return False
        return True


class LogPanel(QWidget):
    """Complete log view with filter toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending = []
        self._known_tags = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        # --- Filter toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search / include…")
        self.search_input.setClearButtonEnabled(True)
        toolbar.addWidget(self.search_input, 2)

        self.exclude_input = QLineEdit()
        self.exclude_input.setPlaceholderText("Exclude…")
        self.exclude_input.setClearButtonEnabled(True)
        toolbar.addWidget(self.exclude_input, 1)

        self.tag_combo = QComboBox()
        self.tag_combo.addItem("All tags", None)
        self.tag_combo.setMinimumWidth(110)
        toolbar.addWidget(self.tag_combo)

        self.case_check = QCheckBox("Aa")
        self.case_check.setToolTip("Case sensitive")
        toolbar.addWidget(self.case_check)

        self.autoscroll_check = QCheckBox("Follow")
        self.autoscroll_check.setChecked(True)
        self.autoscroll_check.setToolTip("Auto-scroll to newest entries")
        toolbar.addWidget(self.autoscroll_check)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 11px;")
        toolbar.addWidget(self.count_label)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("ghost")
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # --- Table ---
        self.log_model = LogTableModel(self)
        self.proxy = LogFilterProxy(self)
        self.proxy.setSourceModel(self.log_model)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 115)
        self.table.setColumnWidth(1, 100)
        header.setHighlightSections(False)

        layout.addWidget(self.table)

        # --- Wiring ---
        clear_btn.clicked.connect(self._clear)
        self.search_input.textChanged.connect(self._apply_filters)
        self.exclude_input.textChanged.connect(self._apply_filters)
        self.case_check.toggled.connect(self._apply_filters)
        self.tag_combo.currentIndexChanged.connect(self._apply_filters)

        # Flush pending entries on a timer so bursts don't freeze the UI
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(150)
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start()

    def append(self, message: str):
        """Queue a raw '[TAG] message' line; timestamp is added here."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        match = TAG_PATTERN.match(message)
        if match:
            tag, text = match.group(1), match.group(2)
        else:
            tag, text = "", message
        self._pending.append((timestamp, tag, text))

    def _flush(self):
        if not self._pending:
            return
        batch, self._pending = self._pending, []
        self.log_model.append_entries(batch)

        # Grow the tag filter dropdown as new tags show up
        for _, tag, _ in batch:
            if tag and tag not in self._known_tags:
                self._known_tags.add(tag)
                self.tag_combo.addItem(tag, tag)

        self._update_count()
        if self.autoscroll_check.isChecked():
            self.table.scrollToBottom()

    def _apply_filters(self):
        self.proxy.set_filters(
            self.search_input.text(),
            self.exclude_input.text(),
            self.case_check.isChecked(),
            self.tag_combo.currentData(),
        )
        self._update_count()

    def _update_count(self):
        shown = self.proxy.rowCount()
        total = self.log_model.rowCount()
        self.count_label.setText(f"{shown}/{total}" if shown != total else f"{total}")

    def _clear(self):
        self.log_model.clear()
        self._pending.clear()
        self._update_count()
