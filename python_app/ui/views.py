from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QPushButton, QFrame, QApplication
)
from PySide6.QtCore import Qt, QSize, QPoint, QMimeData, QTimer, QRectF
from PySide6.QtGui import QColor, QFont, QDrag, QPixmap, QPainter, QBrush, QPen
from datetime import datetime
import dateutil.parser

from .timeline_widget import TimelineWidget, TimelineRulerWidget, TimelineTrackWidget
from core.state_manager import format_operator_short_name


class MachineRowWidget(QFrame):
    """
    Compact single-track row for a machine (~36px height).
    Left column: Machine ID + Status / Action button.
    Right column: Pixel-aligned TimelineTrackWidget.
    Supports drag-and-drop: can be dragged to move zones, or have operators dropped onto it.
    """
    def __init__(self, machine, state_manager, parent=None):
        super().__init__(parent)
        self.machine = machine
        self.state_manager = state_manager
        self.drag_start_pos = None
        self.is_hovered = False
        
        self.setFixedHeight(36)
        self.setAcceptDrops(True)
        self.setCursor(Qt.OpenHandCursor)
        
        self.setStyleSheet("""
            MachineRowWidget {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(10)
        
        # Left column (fixed width ~170px)
        left_col = QWidget()
        left_col.setFixedWidth(170)
        left_layout = QHBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        
        # Machine Name (Clean code without (Truck) or (Digger))
        self.name_lbl = QLabel(f"🚜 {machine.name}")
        self.name_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f8fafc; background: transparent;")
        left_layout.addWidget(self.name_lbl)
        
        left_layout.addStretch()
        
        # Status / Action Button
        self.status_badge = QLabel()
        left_layout.addWidget(self.status_badge)
        
        self.activate_btn = QPushButton("Activate")
        self.activate_btn.setFixedHeight(22)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: 1px solid #10b981;
                border-radius: 3px;
                padding: 1px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.activate_btn.clicked.connect(self.on_activate)
        left_layout.addWidget(self.activate_btn)
        
        self.relieve_btn = QPushButton("Relieve")
        self.relieve_btn.setFixedHeight(22)
        self.relieve_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #e2e8f0;
                border: 1px solid #475569;
                border-radius: 3px;
                padding: 1px 8px;
                font-weight: 500;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #475569; color: white; }
        """)
        self.relieve_btn.clicked.connect(self.on_relieve)
        left_layout.addWidget(self.relieve_btn)
        
        layout.addWidget(left_col)
        
        # Right column: Compact timeline track
        self.timeline_track = TimelineTrackWidget()
        layout.addWidget(self.timeline_track, 1)
        
        self.update_ui()
        self.state_manager.time_ticked.connect(self.update_ui)

    def update_ui(self):
        is_nr = self.machine.status == 'not_required'
        if is_nr:
            self.status_badge.setText("⊘")
            self.status_badge.setToolTip("Not Required (Parked)")
            self.status_badge.setStyleSheet("color: #94a3b8; font-weight: bold; font-size: 12px;")
            self.status_badge.setVisible(True)
            self.activate_btn.setVisible(True)
            self.relieve_btn.setVisible(False)
            self.name_lbl.setStyleSheet("font-weight: normal; font-size: 13px; color: #64748b; background: transparent;")
            self.setStyleSheet("""
                MachineRowWidget {
                    background-color: #0f172a;
                    border: 1px dashed #334155;
                    border-radius: 4px;
                }
            """)
        else:
            self.status_badge.setVisible(False)
            self.activate_btn.setVisible(False)
            self.name_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f8fafc; background: transparent;")
            self.relieve_btn.setVisible(self.machine.currentOperatorId is not None)
            self.setStyleSheet("""
                MachineRowWidget {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 4px;
                }
            """)
            
        segments = self.state_manager.get_machine_segments(self.machine.name)
        self.timeline_track.set_segments(segments, self.state_manager.get_current_time())

    def on_activate(self):
        self.state_manager.set_machine_status(self.machine.name, 'operational')

    def on_relieve(self):
        if self.machine.currentOperatorId:
            self.state_manager.send_on_break(self.machine.currentOperatorId)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.pos())
            if isinstance(child, QPushButton):
                self.drag_start_pos = None
            else:
                self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_start_pos:
            if (event.pos() - self.drag_start_pos).manhattanLength() >= QApplication.startDragDistance():
                self.drag_start_pos = None
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(f"MACHINE:{self.machine.name}")
                drag.setMimeData(mime_data)
                
                pixmap = QPixmap(180, 36)
                pixmap.fill(Qt.transparent)
                p = QPainter(pixmap)
                p.setRenderHint(QPainter.Antialiasing)
                p.setBrush(QBrush(QColor("#1e293b")))
                p.setPen(QPen(QColor("#3b82f6"), 2))
                p.drawRoundedRect(1, 1, 178, 34, 4, 4)
                p.setPen(QColor("#ffffff"))
                p.setFont(QFont("Segoe UI", 10, QFont.Bold))
                p.drawText(QRectF(10, 0, 160, 36), Qt.AlignVCenter | Qt.AlignLeft, f"🚜 {self.machine.name}")
                p.end()
                
                drag.setPixmap(pixmap)
                drag.setHotSpot(QPoint(90, 18))
                drag.exec_(Qt.MoveAction)
                return
        super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("OPERATOR:") or not text.startswith("MACHINE:"):
                event.acceptProposedAction()
                self.is_hovered = True
                self.update()
                return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            text = event.mimeData().text()
            if text.startswith("OPERATOR:") or not text.startswith("MACHINE:"):
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self.is_hovered = False
        self.update()

    def dropEvent(self, event):
        self.is_hovered = False
        self.update()
        text = event.mimeData().text()
        if text.startswith("OPERATOR:") or not text.startswith("MACHINE:"):
            op_id = text.replace("OPERATOR:", "").strip()
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda o=op_id, m=self.machine.name: self.state_manager.assign_operator(o, m))
        else:
            event.ignore()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.is_hovered:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor("#10b981"), 2, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)
            painter.end()


# For backward compatibility
MachineWidget = MachineRowWidget


class ZoneSectionWidget(QFrame):
    """
    Location / Pit container card.
    Contains a section header, a unified top timeline ruler, and compact machine rows.
    """
    def __init__(self, zone_name, is_unassigned=False, machines=None, state_manager=None, parent=None):
        super().__init__(parent)
        self.zone_name = zone_name
        self.is_unassigned = is_unassigned
        self.machines = machines or []
        self.state_manager = state_manager
        self.is_drag_hovered = False
        
        self.setAcceptDrops(True)
        
        self.setStyleSheet("""
            ZoneSectionWidget {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Section Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(2, 0, 2, 2)
        if self.is_unassigned:
            title_lbl = QLabel(f"📦 Unassigned Machines ({len(self.machines)})")
            title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #fbbf24; background: transparent;")
            hint_lbl = QLabel("Drag machines here to unassign from pits")
            hint_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; font-style: italic; background: transparent;")
            header_layout.addWidget(title_lbl)
            header_layout.addSpacing(10)
            header_layout.addWidget(hint_lbl)
        else:
            title_lbl = QLabel(f"📍 {self.zone_name}")
            title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #f8fafc; background: transparent;")
            count_lbl = QLabel(f"{len(self.machines)} machines")
            count_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background-color: #1e293b; padding: 2px 8px; border-radius: 3px;")
            header_layout.addWidget(title_lbl)
            header_layout.addWidget(count_lbl)
            
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        if self.machines:
            # Table Column Header + Shared Time Ruler
            ruler_row = QWidget()
            ruler_row_layout = QHBoxLayout(ruler_row)
            ruler_row_layout.setContentsMargins(8, 0, 8, 0)
            ruler_row_layout.setSpacing(10)
            
            col_lbl = QLabel("EQUIPMENT")
            col_lbl.setFixedWidth(170)
            col_lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b; letter-spacing: 1px;")
            ruler_row_layout.addWidget(col_lbl)
            
            self.ruler = TimelineRulerWidget()
            if self.state_manager:
                self.ruler.set_current_time(self.state_manager.get_current_time())
                self.state_manager.time_ticked.connect(lambda: self.ruler.set_current_time(self.state_manager.get_current_time()))
            ruler_row_layout.addWidget(self.ruler, 1)
            
            layout.addWidget(ruler_row)
            
            # Stack of compact machine rows
            for m in self.machines:
                layout.addWidget(MachineRowWidget(m, self.state_manager))
        else:
            placeholder = QLabel("Drop machines here to assign to this location")
            placeholder.setStyleSheet("""
                color: #64748b;
                font-style: italic;
                padding: 10px;
                background-color: #1e293b;
                border: 1px dashed #334155;
                border-radius: 4px;
            """)
            placeholder.setAlignment(Qt.AlignCenter)
            layout.addWidget(placeholder)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("MACHINE:"):
            event.acceptProposedAction()
            self.is_drag_hovered = True
            self.update()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText() and event.mimeData().text().startswith("MACHINE:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.is_drag_hovered = False
        self.update()

    def dropEvent(self, event):
        self.is_drag_hovered = False
        self.update()
        text = event.mimeData().text()
        if text.startswith("MACHINE:"):
            machine_name = text.split("MACHINE:", 1)[1].strip()
            target_zone = "" if self.is_unassigned else self.zone_name
            event.acceptProposedAction()
            QTimer.singleShot(0, lambda m=machine_name, z=target_zone: self.state_manager.move_machine_to_zone(m, z))
        else:
            event.ignore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        
        bg_color = QColor("#1e293b") if self.is_drag_hovered else QColor("#0f172a")
        border_color = QColor("#3b82f6") if self.is_drag_hovered else QColor("#334155")
        
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2 if self.is_drag_hovered else 1, Qt.DashLine if self.is_drag_hovered else Qt.SolidLine))
        painter.drawRoundedRect(rect, 8, 8)
        painter.end()


class BaseListView(QScrollArea):
    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background-color: #0f172a; }")
        
        self.container = QWidget()
        self.container.setStyleSheet("background-color: #0f172a;")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(14)
        self.layout.setAlignment(Qt.AlignTop)
        self.setWidget(self.container)
        
        self.state_manager.state_changed.connect(self.update_view)
        
    def clear_layout(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def update_view(self):
        pass


class ZoneView(BaseListView):
    def update_view(self):
        if QApplication.mouseButtons() != Qt.NoButton:
            QTimer.singleShot(100, self.update_view)
            return

        self.clear_layout()
        
        known_zones = [z.name for z in self.state_manager.state.zones]
        
        unassigned_machines = [
            m for m in self.state_manager.state.machines
            if not m.zoneId or (m.zoneId not in known_zones and m.zoneId != "")
        ]
        
        if unassigned_machines:
            self.layout.addWidget(
                ZoneSectionWidget(
                    "Unassigned",
                    is_unassigned=True,
                    machines=unassigned_machines,
                    state_manager=self.state_manager
                )
            )
            
        if not self.state_manager.state.zones:
            no_zones_lbl = QLabel("No locations configured. Click 'Edit' at the top right to add locations.")
            no_zones_lbl.setStyleSheet("color: #94a3b8; font-size: 14px; padding: 20px;")
            self.layout.addWidget(no_zones_lbl)
            return

        for zone in self.state_manager.state.zones:
            machines_in_zone = [
                m for m in self.state_manager.state.machines
                if m.zoneId == zone.name or m.zoneId == zone.id
            ]
            self.layout.addWidget(
                ZoneSectionWidget(
                    zone.name,
                    is_unassigned=False,
                    machines=machines_in_zone,
                    state_manager=self.state_manager
                )
            )


class EquipmentCategoryWidget(QFrame):
    """
    Groups machines of the same type with a shared time ruler.
    """
    def __init__(self, cat_title, machines, state_manager, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            EquipmentCategoryWidget {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Category Title
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(2, 0, 2, 2)
        title_lbl = QLabel(f"🚜 {cat_title}")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #f8fafc; background: transparent;")
        count_lbl = QLabel(f"{len(machines)} units")
        count_lbl.setStyleSheet("font-size: 11px; color: #94a3b8; background-color: #1e293b; padding: 2px 8px; border-radius: 3px;")
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(count_lbl)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Table Header with Time Ruler
        ruler_row = QWidget()
        ruler_row_layout = QHBoxLayout(ruler_row)
        ruler_row_layout.setContentsMargins(8, 0, 8, 0)
        ruler_row_layout.setSpacing(10)
        
        col_lbl = QLabel("MACHINE")
        col_lbl.setFixedWidth(170)
        col_lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b; letter-spacing: 1px;")
        ruler_row_layout.addWidget(col_lbl)
        
        self.ruler = TimelineRulerWidget()
        self.ruler.set_current_time(state_manager.get_current_time())
        state_manager.time_ticked.connect(lambda: self.ruler.set_current_time(state_manager.get_current_time()))
        ruler_row_layout.addWidget(self.ruler, 1)
        layout.addWidget(ruler_row)
        
        for m in machines:
            layout.addWidget(MachineRowWidget(m, state_manager))


class EquipmentView(BaseListView):
    def update_view(self):
        if QApplication.mouseButtons() != Qt.NoButton:
            QTimer.singleShot(100, self.update_view)
            return

        self.clear_layout()
        types = sorted(list(set([m.type for m in self.state_manager.state.machines if m.type])))
        if not types:
            self.layout.addWidget(QLabel("No machines configured.", styleSheet="color: #64748b; padding: 10px;"))
            return
            
        for t in types:
            machines = [m for m in self.state_manager.state.machines if m.type == t]
            plural_name = f"{t}s" if not t.endswith("s") else t
            self.layout.addWidget(EquipmentCategoryWidget(plural_name, machines, self.state_manager))


class OperatorRowWidget(QFrame):
    """
    Compact single-track row for an operator (~36px height).
    Left column: Short Name (First + Last Initial e.g. Alice S.) + Status Badge + Metric.
    Right column: Pixel-aligned TimelineTrackWidget.
    """
    def __init__(self, operator, state_manager, parent=None):
        super().__init__(parent)
        self.operator = operator
        self.state_manager = state_manager

        self.setFixedHeight(36)
        self.setStyleSheet("""
            OperatorRowWidget {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 4px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(10)

        # Left column (fixed width ~220px)
        left_col = QWidget()
        left_col.setFixedWidth(220)
        left_layout = QHBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        short_name = format_operator_short_name(operator.name)
        self.name_lbl = QLabel(f"👷 {short_name}")
        self.name_lbl.setToolTip(operator.name)
        self.name_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f8fafc; background: transparent;")
        left_layout.addWidget(self.name_lbl)

        left_layout.addStretch()

        self.status_lbl = QLabel()
        left_layout.addWidget(self.status_lbl)

        self.present_btn = QPushButton("Return")
        self.present_btn.setFixedHeight(22)
        self.present_btn.setStyleSheet("""
            QPushButton {
                background-color: #065f46;
                color: #6ee7b7;
                border: 1px solid #059669;
                border-radius: 3px;
                padding: 1px 6px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #047857; color: white; }
        """)
        self.present_btn.clicked.connect(self.on_mark_present)
        left_layout.addWidget(self.present_btn)

        layout.addWidget(left_col)

        # Right column: Compact timeline track
        self.timeline_track = TimelineTrackWidget()
        layout.addWidget(self.timeline_track, 1)

        self.update_ui()
        self.state_manager.time_ticked.connect(self.update_ui)

    def on_mark_present(self):
        self.state_manager.set_operator_absent(self.operator.name, False)

    def update_ui(self):
        stats = self.state_manager.get_operator_shift_stats(self.operator.name)
        status = stats['status']
        if status == 'absent':
            self.present_btn.setVisible(True)
            self.status_lbl.setText("🏖 Away")
            self.status_lbl.setStyleSheet("background-color: #6b21a8; color: #f3e8ff; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 11px;")
            self.name_lbl.setStyleSheet("font-weight: normal; font-size: 13px; color: #64748b; background: transparent;")
            self.setStyleSheet("""
                OperatorRowWidget {
                    background-color: #0f172a;
                    border: 1px dashed #334155;
                    border-radius: 4px;
                }
            """)
        elif status == 'working':
            self.present_btn.setVisible(False)
            curr_mach = stats['current_machine'] or "Working"
            self.status_lbl.setText(f"🚜 {curr_mach}")
            self.status_lbl.setStyleSheet("background-color: #0284c7; color: white; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 11px;")
            self.name_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f8fafc; background: transparent;")
            self.setStyleSheet("""
                OperatorRowWidget {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 4px;
                }
            """)
        elif status == 'on_break':
            self.present_btn.setVisible(False)
            self.status_lbl.setText("☕ Break")
            self.status_lbl.setStyleSheet("background-color: #7c3aed; color: white; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 11px;")
            self.name_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f8fafc; background: transparent;")
            self.setStyleSheet("""
                OperatorRowWidget {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 4px;
                }
            """)
        else:
            self.present_btn.setVisible(False)
            standby_m = stats['standby_minutes']
            self.status_lbl.setText(f"⏳ Standby")
            self.status_lbl.setStyleSheet("background-color: #d97706; color: white; border-radius: 3px; padding: 1px 6px; font-weight: bold; font-size: 11px;")
            self.name_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #f8fafc; background: transparent;")
            self.setStyleSheet("""
                OperatorRowWidget {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 4px;
                }
            """)

        # Set tooltip with detailed metrics
        if status != 'absent':
            target_breaks = self.state_manager.state.settings.targetBreaksPerShift
            self.setToolTip(
                f"👷 {self.operator.name}\n"
                f"Machine Time: {stats['machine_str']}\n"
                f"Standby Time: {stats['standby_str']}\n"
                f"Total Work: {stats['work_str']}\n"
                f"Official Breaks: {stats['breaks_taken']}/{target_breaks}"
            )
        else:
            self.setToolTip(f"👷 {self.operator.name} (Absent today)")

        segments = self.state_manager.get_operator_segments(self.operator.name)
        self.timeline_track.set_segments(segments, self.state_manager.get_current_time())


# For backward compatibility
OperatorTimelineWidget = OperatorRowWidget


class OperatorsView(BaseListView):
    def update_view(self):
        if QApplication.mouseButtons() != Qt.NoButton:
            QTimer.singleShot(100, self.update_view)
            return

        self.clear_layout()

        active_operators = [op for op in self.state_manager.state.operators if op.status != 'absent']
        if not active_operators:
            self.layout.addWidget(QLabel("No active crew on shift today.", styleSheet="color: #64748b; padding: 10px;"))
            return

        # Top Section Container
        board_frame = QFrame()
        board_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)
        board_layout = QVBoxLayout(board_frame)
        board_layout.setContentsMargins(12, 10, 12, 10)
        board_layout.setSpacing(6)

        # Legend Bar
        legend_layout = QHBoxLayout()
        legend_layout.setContentsMargins(2, 0, 2, 4)
        legend_layout.setSpacing(14)

        title_lbl = QLabel(f"👥 Crew Roster ({len(active_operators)} operators on shift)")
        title_lbl.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 15px; background: transparent;")
        legend_layout.addWidget(title_lbl)

        mach_leg = QLabel("■ Operating")
        mach_leg.setStyleSheet("color: #38bdf8; font-weight: 500; font-size: 11px; background: transparent;")
        legend_layout.addWidget(mach_leg)

        standby_leg = QLabel("■ Standby")
        standby_leg.setStyleSheet("color: #fbbf24; font-weight: 500; font-size: 11px; background: transparent;")
        legend_layout.addWidget(standby_leg)

        break_leg = QLabel("■ Break")
        break_leg.setStyleSheet("color: #c084fc; font-weight: 500; font-size: 11px; background: transparent;")
        legend_layout.addWidget(break_leg)

        plan_leg = QLabel("◌ Projected Plan")
        plan_leg.setStyleSheet("color: #94a3b8; font-style: italic; font-size: 11px; background: transparent;")
        legend_layout.addWidget(plan_leg)

        legend_layout.addStretch()
        board_layout.addLayout(legend_layout)

        # Table Header with Time Ruler
        ruler_row = QWidget()
        ruler_row_layout = QHBoxLayout(ruler_row)
        ruler_row_layout.setContentsMargins(8, 0, 8, 0)
        ruler_row_layout.setSpacing(10)

        col_lbl = QLabel("CREW MEMBER")
        col_lbl.setFixedWidth(220)
        col_lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #64748b; letter-spacing: 1px;")
        ruler_row_layout.addWidget(col_lbl)

        self.ruler = TimelineRulerWidget()
        self.ruler.set_current_time(self.state_manager.get_current_time())
        self.state_manager.time_ticked.connect(lambda: self.ruler.set_current_time(self.state_manager.get_current_time()))
        ruler_row_layout.addWidget(self.ruler, 1)
        board_layout.addWidget(ruler_row)

        # Operator rows (active operators only)
        for op in active_operators:
            board_layout.addWidget(OperatorRowWidget(op, self.state_manager))

        self.layout.addWidget(board_frame)
