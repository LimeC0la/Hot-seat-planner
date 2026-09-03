from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QTextEdit, QSplitter
)
from PySide6.QtCore import Qt

class ReportsView(QWidget):
    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.state_manager.time_ticked.connect(self.refresh_data)
        
        layout = QVBoxLayout(self)
        
        header_lbl = QLabel("📊 Telemetry & Analytics")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #a78bfa;")
        layout.addWidget(header_lbl)
        
        splitter = QSplitter(Qt.Vertical)
        
        # Top half: Analytics Summary
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setStyleSheet("background-color: #0f172a; color: #f8fafc; font-family: Consolas, monospace;")
        splitter.addWidget(self.summary_text)
        
        # Bottom half: Event Log Table
        self.log_table = QTableWidget(0, 4)
        self.log_table.setHorizontalHeaderLabels(["Timestamp", "Type", "Operator/Machine", "Details"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        splitter.addWidget(self.log_table)
        
        layout.addWidget(splitter)
        
        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 Refresh Analytics")
        refresh_btn.clicked.connect(self.refresh_data)
        btn_layout.addWidget(refresh_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        self.refresh_data(force=True)

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_data(force=True)

    def refresh_data(self, force: bool = False):
        if not force and not self.isVisible():
            return
        # 1. Update Analytics Summary
        from core.telemetry import ScheduleAnalytics
        
        now = self.state_manager.get_current_time()
        events = self.state_manager.telemetry.get_events(since=None)
        
        utilization = ScheduleAnalytics.calculate_utilization(events)
        compliance = ScheduleAnalytics.calculate_break_compliance(
            events,
            self.state_manager.state.settings,
            getattr(self.state_manager.state, 'operators', [])
        )
        fatigue = ScheduleAnalytics.calculate_fatigue_risk(
            events,
            getattr(self.state_manager.state, 'operators', [])
        )
        
        summary_html = "<h3>Shift Analytics Summary</h3>"
        
        summary_html += "<h4>Fleet & Operator Utilization</h4><ul>"
        for k, v in utilization.items():
            name = k.replace("_", " ").title()
            val_str = f"{v * 100:.1f}%" if isinstance(v, (int, float)) and v <= 1.0 else str(v)
            summary_html += f"<li><b>{name}</b>: {val_str}</li>"
        summary_html += "</ul>"
        
        summary_html += "<h4>Break Compliance</h4><ul>"
        for op, data in compliance.items():
            if isinstance(data, dict):
                breaks_taken = data.get('breaks_taken', 0)
                target_breaks = data.get('target_breaks', 0)
                summary_html += f"<li><b>{op}</b>: {breaks_taken}/{target_breaks} breaks taken</li>"
            elif isinstance(data, (int, float)) and data <= 1.0:
                summary_html += f"<li><b>{op.replace('_', ' ').title()}</b>: {data * 100:.1f}%</li>"
            else:
                summary_html += f"<li><b>{op}</b>: {data}</li>"
        summary_html += "</ul>"
        
        summary_html += "<h4>Fatigue & Safety Risk</h4><ul>"
        for op, risk in fatigue.items():
            if isinstance(risk, dict):
                score = risk.get('alertness_score', 1.0)
                level = risk.get('risk_level', 'Low')
                summary_html += f"<li><b>{op}</b>: Alertness {score * 100:.0f}% ({level} Risk)</li>"
            else:
                summary_html += f"<li><b>{op.replace('_', ' ').title()}</b>: {risk}</li>"
        summary_html += "</ul>"
        
        self.summary_text.setHtml(summary_html)
        
        # 2. Update Log Table
        self.log_table.setRowCount(0)
        # Show last 50 events, newest first
        for i, ev in enumerate(reversed(events[-50:])):
            self.log_table.insertRow(i)
            self.log_table.setItem(i, 0, QTableWidgetItem(ev.timestamp))
            
            type_item = QTableWidgetItem(ev.event_type)
            if ev.event_type == "DISRUPTION_DETECTED":
                type_item.setForeground(Qt.red)
            elif ev.event_type == "REPLAN_TRIGGERED":
                type_item.setForeground(Qt.yellow)
                
            self.log_table.setItem(i, 1, type_item)
            
            om_str = f"{ev.operator_name or ''} / {ev.machine_name or ''}"
            self.log_table.setItem(i, 2, QTableWidgetItem(om_str))
            
            details_str = ", ".join(f"{k}={v}" for k,v in ev.details.items())
            self.log_table.setItem(i, 3, QTableWidgetItem(details_str))
