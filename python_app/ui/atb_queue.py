from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QDrag, QColor
import json
from core.state_manager import format_operator_short_name

class ATBQueueWidget(QWidget):
    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.setFixedWidth(250)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("Standby / Spare (ATB Queue)")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #f59e0b; padding: 10px;")
        layout.addWidget(title)
        
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e293b;
                border: none;
            }
            QListWidget::item {
                border-bottom: 1px solid #334155;
                padding: 10px;
            }
        """)
        self.list_widget.setDragEnabled(True)
        # Override startDrag to pass operator ID
        self.list_widget.startDrag = self.start_drag
        layout.addWidget(self.list_widget)
        
        self.state_manager.state_changed.connect(self.update_ui)
        self.state_manager.time_ticked.connect(self.update_ui)
        self.update_ui()

    def update_ui(self):
        self.list_widget.clear()
        
        # Sort available operators by ATB gauge (standbyTimeMinutes) descending
        available_ops = [op for op in self.state_manager.state.operators if op.status == 'standby']
        available_ops.sort(key=lambda x: x.standbyTimeMinutes, reverse=True)
        
        for op in available_ops:
            item = QListWidgetItem()
            # Set the operator name as UserRole data so we can retrieve it during drag
            item.setData(Qt.UserRole, op.name)
            
            stats = self.state_manager.get_operator_shift_stats(op.name)
            target_breaks = self.state_manager.state.settings.targetBreaksPerShift
            short_n = format_operator_short_name(op.name)
            text = f"👷 {short_n} (Spare)\nStandby: {op.standbyTimeMinutes}m | Breaks: {op.breaksTaken}/{target_breaks}\nMach: {stats['machine_str']} | Work: {stats['work_str']}"
            item.setText(text)
            
            # Color logic based on standby gauge
            if op.standbyTimeMinutes > 60:
                item.setForeground(QColor("#f87171")) # Red
            elif op.standbyTimeMinutes > 30:
                item.setForeground(QColor("#fbbf24")) # Yellow
            else:
                item.setForeground(QColor("#e2e8f0")) # Slate
                
            self.list_widget.addItem(item)
            
        # Also list operators on official break
        break_ops = [op for op in self.state_manager.state.operators if op.status == 'on_break']
        if break_ops:
            break_label = QListWidgetItem("--- ON OFFICIAL BREAK ---")
            break_label.setFlags(Qt.NoItemFlags)
            break_label.setForeground(QColor("#a78bfa"))
            self.list_widget.addItem(break_label)
            
            for op in break_ops:
                short_n = format_operator_short_name(op.name)
                item = QListWidgetItem(f"☕ {short_n} (Official Break)")
                item.setForeground(QColor("#c084fc"))
                item.setFlags(Qt.NoItemFlags) # Disable drag for break ops
                self.list_widget.addItem(item)

        # List operators on planned leave / absent
        absent_ops = [op for op in self.state_manager.state.operators if op.status == 'absent']
        if absent_ops:
            absent_label = QListWidgetItem(f"--- ABSENT / LEAVE ({len(absent_ops)}) ---")
            absent_label.setFlags(Qt.NoItemFlags)
            absent_label.setForeground(QColor("#a855f7"))
            self.list_widget.addItem(absent_label)
            
            for op in absent_ops:
                short_n = format_operator_short_name(op.name)
                item = QListWidgetItem(f"🏖 {short_n} (Absent)")
                item.setForeground(QColor("#c084fc"))
                item.setFlags(Qt.NoItemFlags)
                self.list_widget.addItem(item)

    def start_drag(self, supportedActions):
        item = self.list_widget.currentItem()
        if not item:
            return
            
        op_id = item.data(Qt.UserRole)
        if not op_id:
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        # Pass operator id as plain text
        mime_data.setText(op_id)
        drag.setMimeData(mime_data)
        
        drag.exec_(supportedActions)
