"""
Log panel: timestamped, searchable, filterable protocol/debug log.

Features:
- Timestamps (HH:MM:SS.mmm) added on receipt
- Include filter (only rows containing text) and exclude filter
- Case sensitive / insensitive toggle
- One checkbox per tag seen so far (SEND / RECV / INFO / ERROR / ...),
  independently toggleable - unchecking one just hides that tag
- Pause autoscroll, clear
- Entries are batched via a flush timer so protocol bursts stay smooth
"""

import json
import re
from datetime import datetime

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QCheckBox,
    QPushButton, QTableView, QHeaderView, QAbstractItemView, QLabel, QMenu
)

from theme import PALETTE


TAG_PATTERN = re.compile(r"^\[(\w+)\]\s*(.*)", re.DOTALL)

TAG_COLORS = {
    "ERROR": PALETTE["red"],
    "SEND": "#5aa9e6",
    "RECV": PALETTE["green"],
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
    """Include/exclude text filtering with case toggle and per-tag checkboxes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.include_text = ""
        self.exclude_text = ""
        self.case_sensitive = False
        self.hidden_tags = set()  # tags unchecked in the toolbar

    def set_filters(self, include_text: str, exclude_text: str,
                    case_sensitive: bool, hidden_tags: set):
        self.include_text = include_text
        self.exclude_text = exclude_text
        self.case_sensitive = case_sensitive
        self.hidden_tags = hidden_tags
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        timestamp, tag, message = self.sourceModel().entries[source_row]

        if tag in self.hidden_tags:
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
        self.tag_checks = {}  # tag -> QCheckBox, grown as new tags show up

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

        tags_label = QLabel("Tags:")
        tags_label.setStyleSheet(f"color: {PALETTE['muted']}; font-size: 11px;")
        toolbar.addWidget(tags_label)

        # One checkbox per tag, added on demand as new tags show up in _flush.
        self.tags_layout = QHBoxLayout()
        self.tags_layout.setSpacing(6)
        toolbar.addLayout(self.tags_layout)

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
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

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
        self.table.customContextMenuRequested.connect(self._show_context_menu)

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

        # Grow the tag checkboxes as new tags show up
        for _, tag, _ in batch:
            if tag and tag not in self.tag_checks:
                self._add_tag_checkbox(tag)

        self._update_count()
        if self.autoscroll_check.isChecked():
            self.table.scrollToBottom()

    def _add_tag_checkbox(self, tag: str):
        """Add a checked-by-default toggle for a newly-seen tag."""
        check = QCheckBox(tag)
        check.setChecked(True)
        check.setToolTip(f"Show {tag} messages")
        check.setStyleSheet(f"color: {TAG_COLORS.get(tag, PALETTE['text_dim'])};")
        check.toggled.connect(self._apply_filters)
        self.tag_checks[tag] = check
        self.tags_layout.addWidget(check)

    def _apply_filters(self):
        hidden_tags = {tag for tag, check in self.tag_checks.items() if not check.isChecked()}
        self.proxy.set_filters(
            self.search_input.text(),
            self.exclude_input.text(),
            self.case_check.isChecked(),
            hidden_tags,
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

    def _show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        source_row = self.proxy.mapToSource(index).row()
        _, _, message = self.log_model.entries[source_row]
        path, value = self._extract_path_value(message)

        menu = QMenu(self)
        copy_path_action = menu.addAction("Copy path")
        copy_path_action.setEnabled(path is not None)
        copy_value_action = menu.addAction("Copy value")
        copy_value_action.setEnabled(value is not None)
        menu.addSeparator()
        filter_path_action = menu.addAction("Filter by path")
        filter_path_action.setEnabled(path is not None)
        filter_value_action = menu.addAction("Filter by value")
        filter_value_action.setEnabled(value is not None)

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action is copy_path_action:
            QApplication.clipboard().setText(path)
        elif action is copy_value_action:
            QApplication.clipboard().setText(value)
        elif action is filter_path_action:
            self.search_input.setText(path)
        elif action is filter_value_action:
            self.search_input.setText(value)

    @staticmethod
    def _extract_path_value(message: str):
        """Best-effort extraction of the AWJ "path"/"value" fields from a
        SEND/RECV log line's JSON payload (see AWJClient.send_get/send_replace
        and the raw device messages), for the row's context menu."""
        try:
            payload = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return None, None
        if not isinstance(payload, dict) or "path" not in payload:
            return None, None

        path = payload["path"]
        if not isinstance(path, str):
            path = json.dumps(path)

        value = payload.get("value")
        if value is not None and not isinstance(value, str):
            value = json.dumps(value)

        return path, value
