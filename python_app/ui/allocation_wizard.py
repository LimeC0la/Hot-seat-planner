from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QComboBox, QCheckBox, QGridLayout,
    QMessageBox, QStackedWidget, QSizePolicy, QButtonGroup, QRadioButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from typing import Dict, List, Set, Optional

# Machine category groupings
DIGGER_TYPES = {"Digger", "Excavator", "Shovel"}
ROM_TYPES = {"ROM Loader", "Loader", "ROM"}
TRUCK_TYPES = {"Truck", "Haul Truck", "Dump Truck"}

def is_digger(mach_type: str) -> bool:
    return any(dt.lower() in mach_type.lower() for dt in DIGGER_TYPES)

def is_rom_loader(mach_type: str) -> bool:
    return any(rt.lower() in mach_type.lower() for rt in ROM_TYPES)

def is_truck(mach_type: str) -> bool:
    return any(tt.lower() in mach_type.lower() for tt in TRUCK_TYPES)

def is_auxiliary(mach_type: str) -> bool:
    return not (is_digger(mach_type) or is_rom_loader(mach_type) or is_truck(mach_type))

def is_operator_qualified_for_machine(op, machine) -> bool:
    if not machine or not machine.type:
        return True
    return machine.type in op.qualifications

class StepIndicator(QFrame):
    step_clicked = Signal(int)

    def __init__(self, steps: List[str], current_step: int = 0, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.current_step = current_step
        self.buttons: List[QPushButton] = []
        
        self.setStyleSheet("""
            StepIndicator {
                background-color: #1e293b;
                border-bottom: 1px solid #334155;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        for idx, step_name in enumerate(steps):
            btn = QPushButton(f"{idx + 1}. {step_name}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, i=idx: self.step_clicked.emit(i))
            layout.addWidget(btn)
            self.buttons.append(btn)
            
            if idx < len(steps) - 1:
                arrow = QLabel("›")
                arrow.setStyleSheet("color: #475569; font-size: 16px; font-weight: bold;")
                layout.addWidget(arrow)
                
        self.update_styles()

    def set_current_step(self, step_idx: int):
        self.current_step = step_idx
        self.update_styles()

    def update_styles(self):
        for idx, btn in enumerate(self.buttons):
            if idx == self.current_step:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3b82f6;
                        color: white;
                        border: 1px solid #60a5fa;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-weight: bold;
                        font-size: 12px;
                    }
                """)
            elif idx < self.current_step:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0f172a;
                        color: #10b981;
                        border: 1px solid #059669;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-weight: 600;
                        font-size: 12px;
                    }
                    QPushButton:hover { background-color: #1e293b; }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0f172a;
                        color: #64748b;
                        border: 1px solid #334155;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-weight: normal;
                        font-size: 12px;
                    }
                    QPushButton:hover { background-color: #1e293b; color: #94a3b8; }
                """)


class AttendanceStepWidget(QWidget):
    attendance_changed = Signal()

    def __init__(self, wizard, parent=None):
        super().__init__(parent)
        self.wizard = wizard
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        # Header Info
        header_lbl = QLabel("Step 1: Attendance & Planned Leave")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(header_lbl)
        
        desc_lbl = QLabel("Search and mark operators who are absent, sick, or on planned leave today. Absent operators will be removed from available equipment rosters and relief schedules.")
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 13px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        
        # Search & Action Bar
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Type operator name or qualification (e.g. 'John', 'Digger')...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e293b;
                color: white;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #3b82f6; }
        """)
        self.search_input.textChanged.connect(self.update_list)
        search_layout.addWidget(self.search_input, 1)
        
        clear_search_btn = QPushButton("Clear")
        clear_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #475569; color: white; }
        """)
        clear_search_btn.clicked.connect(lambda: self.search_input.clear())
        search_layout.addWidget(clear_search_btn)
        
        all_present_btn = QPushButton("Mark All Present")
        all_present_btn.setStyleSheet("""
            QPushButton {
                background-color: #065f46;
                color: #6ee7b7;
                border: 1px solid #059669;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #047857; color: white; }
        """)
        all_present_btn.clicked.connect(self.mark_all_present)
        search_layout.addWidget(all_present_btn)
        
        layout.addLayout(search_layout)
        
        # Summary Counter Badge Bar
        self.counter_lbl = QLabel()
        self.counter_lbl.setStyleSheet("""
            background-color: #1e293b;
            color: #38bdf8;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13px;
            font-weight: 500;
        """)
        layout.addWidget(self.counter_lbl)
        
        # Scroll Area for Operator Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #334155; border-radius: 6px; background-color: #0f172a; }")
        
        self.cards_container = QWidget()
        self.cards_container.setStyleSheet("background-color: #0f172a;")
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(12, 12, 12, 12)
        self.cards_layout.setSpacing(8)
        self.cards_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll, 1)

    def mark_all_present(self):
        self.wizard.absent_operators.clear()
        self.update_list()
        self.attendance_changed.emit()

    def toggle_operator_absence(self, op_name: str):
        if op_name in self.wizard.absent_operators:
            self.wizard.absent_operators.remove(op_name)
        else:
            self.wizard.absent_operators.add(op_name)
            for m_name, assigned_op in list(self.wizard.allocations.items()):
                if assigned_op == op_name:
                    self.wizard.allocations[m_name] = None
        self.update_list()
        self.attendance_changed.emit()

    def update_list(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
                
        all_ops = self.wizard.state_manager.state.operators
        total_count = len(all_ops)
        absent_count = len(self.wizard.absent_operators)
        present_count = total_count - absent_count
        
        self.counter_lbl.setText(f"👥 Roster Summary:  ✅ Present Today: {present_count}  |  🏖 Absent / Leave: {absent_count}  |  Total Crew: {total_count}")
        
        query = self.search_input.text().strip().lower()
        
        sorted_ops = sorted(
            all_ops,
            key=lambda o: (1 if o.name in self.wizard.absent_operators else 0, o.name.lower())
        )
        
        matched_ops = []
        for op in sorted_ops:
            if not query:
                matched_ops.append(op)
            else:
                matches_name = query in op.name.lower()
                matches_qual = any(query in q.lower() for q in op.qualifications)
                if matches_name or matches_qual:
                    matched_ops.append(op)
                    
        if not matched_ops:
            no_match = QLabel("No operators matching search query.")
            no_match.setStyleSheet("color: #64748b; font-style: italic; padding: 20px;")
            no_match.setAlignment(Qt.AlignCenter)
            self.cards_layout.addWidget(no_match)
            return
            
        for op in matched_ops:
            is_absent = op.name in self.wizard.absent_operators
            
            card = QFrame()
            if is_absent:
                card.setStyleSheet("""
                    QFrame {
                        background-color: #1e1b2e;
                        border: 1px solid #4c1d95;
                        border-radius: 6px;
                    }
                """)
            else:
                card.setStyleSheet("""
                    QFrame {
                        background-color: #1e293b;
                        border: 1px solid #334155;
                        border-radius: 6px;
                    }
                """)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(12, 8, 12, 8)
            card_layout.setSpacing(12)
            
            icon_str = "🏖" if is_absent else "👷"
            name_str = f"{icon_str} <b>{op.name}</b>"
            name_lbl = QLabel(name_str)
            name_lbl.setStyleSheet(f"font-size: 14px; color: {'#cbd5e1' if is_absent else '#f8fafc'}; background: transparent;")
            card_layout.addWidget(name_lbl)
            
            quals_layout = QHBoxLayout()
            quals_layout.setSpacing(4)
            for q in op.qualifications:
                q_badge = QLabel(q)
                q_badge.setStyleSheet("""
                    background-color: #0f172a;
                    color: #38bdf8;
                    border: 1px solid #0284c7;
                    border-radius: 4px;
                    padding: 1px 6px;
                    font-size: 11px;
                """)
                quals_layout.addWidget(q_badge)
            card_layout.addLayout(quals_layout)
            card_layout.addStretch()
            
            if is_absent:
                btn = QPushButton("Mark Present")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #065f46;
                        color: #6ee7b7;
                        border: 1px solid #059669;
                        border-radius: 4px;
                        padding: 4px 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #047857; color: white; }
                """)
            else:
                btn = QPushButton("Mark Absent")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #7f1d1d;
                        color: #fca5a5;
                        border: 1px solid #dc2626;
                        border-radius: 4px;
                        padding: 4px 10px;
                        font-weight: bold;
                    }
                    QPushButton:hover { background-color: #991b1b; color: white; }
                """)
            btn.clicked.connect(lambda _, name=op.name: self.toggle_operator_absence(name))
            card_layout.addWidget(btn)
            
            self.cards_layout.addWidget(card)


class EquipmentAssignmentRow(QFrame):
    assignment_changed = Signal()

    def __init__(self, machine, wizard, parent=None):
        super().__init__(parent)
        self.machine = machine
        self.wizard = wizard
        
        self.is_not_required = machine.name in self.wizard.not_required_machines
        
        self.setStyleSheet("""
            EquipmentAssignmentRow {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        title_text = f"🚜 <b>{machine.name}</b> <span style='color: #94a3b8;'>({machine.type})</span>"
        self.title_lbl = QLabel(title_text)
        self.title_lbl.setStyleSheet("font-size: 14px; color: #f8fafc; background: transparent;")
        info_layout.addWidget(self.title_lbl)
        
        zone_text = f"📍 Location: {machine.zoneId if machine.zoneId else 'Unassigned'}"
        self.zone_lbl = QLabel(zone_text)
        self.zone_lbl.setStyleSheet("font-size: 11px; color: #64748b; background: transparent;")
        info_layout.addWidget(self.zone_lbl)
        
        layout.addLayout(info_layout, 1)
        
        self.status_cb = QCheckBox("Operational")
        self.status_cb.setChecked(not self.is_not_required)
        self.status_cb.setStyleSheet("""
            QCheckBox {
                color: #e2e8f0;
                font-weight: 500;
                font-size: 12px;
            }
            QCheckBox::indicator:checked {
                background-color: #10b981;
                border: 1px solid #059669;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #334155;
                border: 1px solid #475569;
                border-radius: 3px;
            }
        """)
        self.status_cb.toggled.connect(self.on_status_toggled)
        layout.addWidget(self.status_cb)
        
        self.op_combo = QComboBox()
        self.op_combo.setMinimumWidth(220)
        self.op_combo.setStyleSheet("""
            QComboBox {
                background-color: #0f172a;
                color: white;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 12px;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background-color: #1e293b;
                color: white;
                selection-background-color: #3b82f6;
                border: 1px solid #334155;
            }
            QComboBox:disabled {
                background-color: #1e293b;
                color: #64748b;
                border-color: #334155;
            }
        """)
        self.op_combo.currentIndexChanged.connect(self.on_operator_selected)
        layout.addWidget(self.op_combo)
        
        # New options based on machine type
        from .allocation_wizard import is_digger
        
        self.options_layout = QVBoxLayout()
        if is_digger(self.machine.type):
            pri_layout = QHBoxLayout()
            pri_layout.addWidget(QLabel("Priority:"))
            self.priority_spin = QSpinBox()
            self.priority_spin.setRange(1, 10)
            self.priority_spin.setValue(getattr(self.machine, 'priority', 3))
            self.priority_spin.setToolTip("1 is Highest Priority")
            self.priority_spin.valueChanged.connect(self.on_priority_changed)
            pri_layout.addWidget(self.priority_spin)
            self.options_layout.addLayout(pri_layout)
            
            trk_layout = QHBoxLayout()
            trk_layout.addWidget(QLabel("Req. Trucks:"))
            self.trucks_spin = QSpinBox()
            self.trucks_spin.setRange(0, 20)
            self.trucks_spin.setValue(getattr(self.machine, 'requiredTrucks', 4))
            self.trucks_spin.valueChanged.connect(self.on_trucks_changed)
            trk_layout.addWidget(self.trucks_spin)
            self.options_layout.addLayout(trk_layout)
        else:
            circ_layout = QHBoxLayout()
            circ_layout.addWidget(QLabel("Circuit:"))
            self.circuit_combo = QComboBox()
            self.circuit_combo.addItem("General / Unassigned", "")
            self.circuit_combo.currentIndexChanged.connect(self.on_circuit_changed)
            circ_layout.addWidget(self.circuit_combo)
            self.options_layout.addLayout(circ_layout)
            
        layout.addLayout(self.options_layout)
        
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setToolTip("Clear Operator Assignment")
        self.clear_btn.setFixedSize(28, 28)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #94a3b8;
                border: 1px solid #475569;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #ef4444; color: white; border-color: #dc2626; }
            QPushButton:disabled { background-color: transparent; border-color: transparent; color: transparent; }
        """)
        self.clear_btn.clicked.connect(self.clear_assignment)
        layout.addWidget(self.clear_btn)
        
        self.refresh_ui()

    def on_status_toggled(self, is_operational: bool):
        if is_operational:
            if self.machine.name in self.wizard.not_required_machines:
                self.wizard.not_required_machines.remove(self.machine.name)
        else:
            self.wizard.not_required_machines.add(self.machine.name)
            self.wizard.allocations[self.machine.name] = None
            
        self.refresh_ui()
        self.assignment_changed.emit()

    def on_operator_selected(self, index: int):
        if not self.status_cb.isChecked():
            return
        op_name = self.op_combo.currentData()
        current_in_wizard = self.wizard.allocations.get(self.machine.name, None)
        
        if op_name != current_in_wizard:
            if op_name:
                for other_m, other_op in list(self.wizard.allocations.items()):
                    if other_m != self.machine.name and other_op == op_name:
                        self.wizard.allocations[other_m] = None
                        
            self.wizard.allocations[self.machine.name] = op_name
            self.assignment_changed.emit()

    def on_priority_changed(self, value: int):
        self.machine.priority = value

    def on_trucks_changed(self, value: int):
        self.machine.requiredTrucks = value

    def on_circuit_changed(self, index: int):
        self.machine.circuitGroup = self.circuit_combo.currentData()

    def clear_assignment(self):
        self.wizard.allocations[self.machine.name] = None
        self.refresh_ui()
        self.assignment_changed.emit()

    def refresh_ui(self):
        self.is_not_required = self.machine.name in self.wizard.not_required_machines
        self.status_cb.blockSignals(True)
        self.status_cb.setChecked(not self.is_not_required)
        self.status_cb.setText("Operational" if not self.is_not_required else "⊘ Not Required")
        self.status_cb.blockSignals(False)
        
        if self.is_not_required:
            self.setStyleSheet("""
                EquipmentAssignmentRow {
                    background-color: #0f172a;
                    border: 1px dashed #334155;
                    border-radius: 6px;
                }
            """)
            self.title_lbl.setStyleSheet("font-size: 14px; color: #64748b; background: transparent;")
            self.op_combo.setEnabled(False)
            self.clear_btn.setEnabled(False)
            self.op_combo.blockSignals(True)
            self.op_combo.clear()
            self.op_combo.addItem("⊘ Parked / Inactive", None)
            self.op_combo.blockSignals(False)
        else:
            self.setStyleSheet("""
                EquipmentAssignmentRow {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 6px;
                }
            """)
            self.title_lbl.setStyleSheet("font-size: 14px; color: #f8fafc; background: transparent;")
            self.op_combo.setEnabled(True)
            self.clear_btn.setEnabled(True)
            
            currently_assigned_op = self.wizard.allocations.get(self.machine.name, None)
            
            # Find all operators assigned to other operational machines
            assigned_to_other_machines = {
                op_name for m_name, op_name in self.wizard.allocations.items()
                if op_name and m_name != self.machine.name
            }
            
            all_ops = self.wizard.state_manager.state.operators
            qualified_available_ops = [
                op for op in all_ops
                if op.name not in self.wizard.absent_operators
                and is_operator_qualified_for_machine(op, self.machine)
                and op.name not in assigned_to_other_machines
            ]
            
            self.op_combo.blockSignals(True)
            self.op_combo.clear()
            self.op_combo.addItem("-- Unassigned / Empty --", None)
            
            selected_idx = 0
            for idx, op in enumerate(qualified_available_ops):
                self.op_combo.addItem(f"👷 {op.name}", op.name)
                if op.name == currently_assigned_op:
                    selected_idx = idx + 1
                    
            if currently_assigned_op and selected_idx == 0:
                self.op_combo.addItem(f"👷 {currently_assigned_op}", currently_assigned_op)
                selected_idx = self.op_combo.count() - 1
                
            self.op_combo.setCurrentIndex(selected_idx)
            self.op_combo.blockSignals(False)
            
            from .allocation_wizard import is_digger
            if hasattr(self, 'circuit_combo') and not is_digger(self.machine.type):
                self.circuit_combo.blockSignals(True)
                current_circ = getattr(self.machine, 'circuitGroup', "")
                self.circuit_combo.clear()
                self.circuit_combo.addItem("General / Unassigned", "")
                
                # Find active diggers
                active_diggers = [m.name for m in self.wizard.state_manager.state.machines 
                                  if is_digger(m.type) and m.name not in self.wizard.not_required_machines]
                
                sel_idx = 0
                for i, d_name in enumerate(active_diggers):
                    self.circuit_combo.addItem(f"🚜 Circuit: {d_name}", d_name)
                    if d_name == current_circ:
                        sel_idx = i + 1
                        
                self.circuit_combo.setCurrentIndex(sel_idx)
                self.circuit_combo.blockSignals(False)


class EquipmentCategoryStepWidget(QWidget):
    step_data_changed = Signal()

    def __init__(self, step_title: str, description: str, filter_func, wizard, is_truck_step: bool = False, parent=None):
        super().__init__(parent)
        self.step_title = step_title
        self.description = description
        self.filter_func = filter_func
        self.wizard = wizard
        self.is_truck_step = is_truck_step
        self.row_widgets: List[EquipmentAssignmentRow] = []
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        header_layout = QHBoxLayout()
        title_lbl = QLabel(step_title)
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f8fafc;")
        header_layout.addWidget(title_lbl)
        
        if is_truck_step:
            header_layout.addStretch()
            
            auto_fill_btn = QPushButton("⚡ Auto-Fill Remaining Operators")
            auto_fill_btn.setToolTip("Fill empty operational trucks with available qualified drivers")
            auto_fill_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0284c7;
                    color: white;
                    border: 1px solid #38bdf8;
                    border-radius: 6px;
                    padding: 6px 14px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background-color: #0369a1; }
            """)
            auto_fill_btn.clicked.connect(self.auto_fill_trucks)
            header_layout.addWidget(auto_fill_btn)
            
            clear_trucks_btn = QPushButton("Clear Trucks")
            clear_trucks_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: #cbd5e1;
                    border: 1px solid #475569;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-weight: 500;
                }
                QPushButton:hover { background-color: #475569; color: white; }
            """)
            clear_trucks_btn.clicked.connect(self.clear_all_category_machines)
            header_layout.addWidget(clear_trucks_btn)
            
        layout.addLayout(header_layout)
        
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 13px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        
        self.stats_lbl = QLabel()
        self.stats_lbl.setStyleSheet("""
            background-color: #1e293b;
            color: #fbbf24;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13px;
            font-weight: 500;
        """)
        layout.addWidget(self.stats_lbl)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #334155; border-radius: 6px; background-color: #0f172a; }")
        
        self.container = QWidget()
        self.container.setStyleSheet("background-color: #0f172a;")
        self.rows_layout = QVBoxLayout(self.container)
        self.rows_layout.setContentsMargins(12, 12, 12, 12)
        self.rows_layout.setSpacing(8)
        self.rows_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)

    def auto_fill_trucks(self):
        truck_machines = [
            m for m in self.wizard.state_manager.state.machines
            if self.filter_func(m.type) and m.name not in self.wizard.not_required_machines
        ]
        
        assigned_op_names = {op_name for op_name in self.wizard.allocations.values() if op_name}
        
        available_truck_drivers = [
            op for op in self.wizard.state_manager.state.operators
            if op.name not in self.wizard.absent_operators
            and "Truck" in op.qualifications
            and op.name not in assigned_op_names
        ]
        
        fill_count = 0
        driver_idx = 0
        for m in truck_machines:
            current_op = self.wizard.allocations.get(m.name, None)
            if not current_op and driver_idx < len(available_truck_drivers):
                chosen_driver = available_truck_drivers[driver_idx]
                self.wizard.allocations[m.name] = chosen_driver.name
                driver_idx += 1
                fill_count += 1
                
        self.refresh_rows()
        self.step_data_changed.emit()

    def clear_all_category_machines(self):
        cat_machines = [m for m in self.wizard.state_manager.state.machines if self.filter_func(m.type)]
        for m in cat_machines:
            self.wizard.allocations[m.name] = None
        self.refresh_rows()
        self.step_data_changed.emit()

    def refresh_rows(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.row_widgets.clear()
        
        matching_machines = [m for m in self.wizard.state_manager.state.machines if self.filter_func(m.type)]
        
        if not matching_machines:
            no_mach = QLabel(f"No machines found for this category.")
            no_mach.setStyleSheet("color: #64748b; font-style: italic; padding: 20px;")
            no_mach.setAlignment(Qt.AlignCenter)
            self.rows_layout.addWidget(no_mach)
            self.stats_lbl.setText("No machines in this category.")
            return
            
        operational_count = 0
        assigned_count = 0
        
        for m in matching_machines:
            is_nr = m.name in self.wizard.not_required_machines
            assigned_op = self.wizard.allocations.get(m.name, None)
            if not is_nr:
                operational_count += 1
                if assigned_op:
                    assigned_count += 1
                    
            row = EquipmentAssignmentRow(m, self.wizard)
            row.assignment_changed.connect(self.on_child_assignment_changed)
            self.rows_layout.addWidget(row)
            self.row_widgets.append(row)
            
        self.stats_lbl.setText(
            f"📊 Total Equipment: {len(matching_machines)} | Active / Operational: {operational_count} | Assigned Operators: {assigned_count} | Not Required: {len(matching_machines) - operational_count}"
        )

    def on_child_assignment_changed(self):
        for row in self.row_widgets:
            row.refresh_ui()

        matching_machines = [m for m in self.wizard.state_manager.state.machines if self.filter_func(m.type)]
        operational_count = 0
        assigned_count = 0
        for m in matching_machines:
            is_nr = m.name in self.wizard.not_required_machines
            assigned_op = self.wizard.allocations.get(m.name, None)
            if not is_nr:
                operational_count += 1
                if assigned_op:
                    assigned_count += 1
        self.stats_lbl.setText(
            f"📊 Total Equipment: {len(matching_machines)} | Active / Operational: {operational_count} | Assigned Operators: {assigned_count} | Not Required: {len(matching_machines) - operational_count}"
        )
        self.step_data_changed.emit()


class ReviewStepWidget(QWidget):
    def __init__(self, wizard, parent=None):
        super().__init__(parent)
        self.wizard = wizard
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        
        title_lbl = QLabel("Step 6: Shift Review & Launch")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel("Review today's shift setup. Any leftover unassigned operators will automatically start on Standby (Hot Seat relief pool). Click 'Apply & Start Shift' to activate the schedule.")
        desc_lbl.setStyleSheet("color: #94a3b8; font-size: 13px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #334155; border-radius: 6px; background-color: #0f172a; }")
        
        self.container = QWidget()
        self.container.setStyleSheet("background-color: #0f172a;")
        self.summary_layout = QVBoxLayout(self.container)
        self.summary_layout.setContentsMargins(14, 14, 14, 14)
        self.summary_layout.setSpacing(14)
        self.summary_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.container)
        layout.addWidget(scroll, 1)
        
        opts_frame = QFrame()
        opts_frame.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px;")
        opts_layout = QHBoxLayout(opts_frame)
        opts_layout.setContentsMargins(12, 8, 12, 8)
        opts_layout.setSpacing(20)
        
        self.reset_clock_cb = QCheckBox("Reset Clock to Shift Start (07:00)")
        self.reset_clock_cb.setChecked(True)
        self.reset_clock_cb.setStyleSheet("color: #e2e8f0; font-weight: 500;")
        opts_layout.addWidget(self.reset_clock_cb)
        
        self.reset_metrics_cb = QCheckBox("Reset Shift Work/Break History for Fresh Day")
        self.reset_metrics_cb.setChecked(True)
        self.reset_metrics_cb.setStyleSheet("color: #e2e8f0; font-weight: 500;")
        opts_layout.addWidget(self.reset_metrics_cb)
        
        opts_layout.addStretch()
        
        self.optimize_btn = QPushButton("✨ Optimize Allocation")
        self.optimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #8b5cf6;
                color: white;
                border: 1px solid #7c3aed;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #7c3aed; }
        """)
        self.optimize_btn.clicked.connect(self.run_optimization)
        opts_layout.addWidget(self.optimize_btn)
        
        layout.addWidget(opts_frame)
        
    def run_optimization(self):
        wizard = self.wizard
        all_ops = [op for op in wizard.state_manager.state.operators if op.name not in wizard.absent_operators]
        total_ops = len(all_ops)
        
        settings = wizard.state_manager.state.settings
        shift_mins = 720
        break_mins_per_op = settings.targetBreaksPerShift * settings.breakDurationMinutes
        total_op_mins = total_ops * (shift_mins - break_mins_per_op)
        
        all_machines = wizard.state_manager.state.machines
        current_active_machines = [m for m in all_machines if m.name not in wizard.not_required_machines]
        diggers = [m for m in current_active_machines if is_digger(m.type)]
        
        # Build circuits
        # circuit_map maps digger_name -> list of machines in its circuit (including the digger itself)
        circuit_map = {d.name: [d] for d in diggers}
        general_machines = []
        
        for m in current_active_machines:
            if not is_digger(m.type):
                c_grp = getattr(m, 'circuitGroup', "")
                if c_grp and c_grp in circuit_map:
                    circuit_map[c_grp].append(m)
                else:
                    general_machines.append(m)
                    
        def calc_score(active_machines_list, deficit_mins):
            score = 0
            machine_times = {m.name: shift_mins for m in active_machines_list}
            if deficit_mins > 0:
                def get_pri(m):
                    if is_digger(m.type): return getattr(m, 'priority', 3)
                    return 5
                sorted_machines = sorted(active_machines_list, key=lambda m: get_pri(m), reverse=True)
                rem_def = deficit_mins
                for m in sorted_machines:
                    if rem_def <= 0: break
                    take = min(shift_mins, rem_def)
                    machine_times[m.name] -= take
                    rem_def -= take
                    
            # Calculate circuit-based score
            # A circuit's production is limited by the digger's time and number of operating trucks in the circuit
            for d in [m for m in active_machines_list if is_digger(m.type)]:
                # count trucks in this digger's circuit
                d_circuit = circuit_map.get(d.name, [d])
                active_trucks_in_circuit = sum(1 for tm in d_circuit if is_truck(tm.type) and tm in active_machines_list)
                
                # "1 digger with 20 trucks isnt as productive as 3 diggers with 5 trucks"
                # Diminishing returns on trucks: we can use a modifier or just sqrt(trucks) for demonstration, or cap it at requiredTrucks
                req = getattr(d, 'requiredTrucks', 4)
                if req <= 0: req = 1
                effective_trucks = min(active_trucks_in_circuit, req) + (max(0, active_trucks_in_circuit - req) * 0.2)
                
                pri = getattr(d, 'priority', 3)
                # Score = Operating Time * Effective Trucks * Priority Modifier
                score += machine_times[d.name] * effective_trucks * (11 - pri)
            return score
            
        required_mins = len(current_active_machines) * shift_mins
        deficit = required_mins - total_op_mins
        base_score = calc_score(current_active_machines, max(0, deficit))
        
        diggers_sorted = sorted(diggers, key=lambda m: getattr(m, 'priority', 3), reverse=True)
        
        best_score = base_score
        best_parked_machines = []
        
        current_test_machines = list(current_active_machines)
        parked_for_test = []
        
        for d in diggers_sorted:
            # Park the entire circuit
            for m in circuit_map.get(d.name, []):
                if m in current_test_machines:
                    current_test_machines.remove(m)
                    parked_for_test.append(m.name)
            
            req = len(current_test_machines) * shift_mins
            new_def = max(0, req - total_op_mins)
            test_score = calc_score(current_test_machines, new_def)
            
            if test_score > best_score:
                best_score = test_score
                best_parked_machines = list(parked_for_test)
                
        msg = f"<h3>Optimization Analysis</h3>"
        msg += f"Available Operator Time: {total_op_mins} mins (Guarantees {settings.targetBreaksPerShift} breaks/operator)<br>"
        msg += f"Required Machine Time: {required_mins} mins<br>"
        msg += f"Current Deficit: {max(0, deficit)} mins<br>"
        msg += f"Base Scenario Production Score: {base_score:.1f}<br><br>"
        
        if best_score > base_score:
            msg += f"<b>Recommended Action:</b> Park {', '.join(best_parked_machines)} (Low Priority Circuit) to act as Hot Seaters.<br>"
            msg += f"Predicted Improved Score: {best_score:.1f}<br><br>"
            msg += "Would you like to apply this recommendation?"
            reply = QMessageBox.question(self, "Optimization Recommendation", msg, QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                for m_name in best_parked_machines:
                    wizard.not_required_machines.add(m_name)
                    wizard.allocations[m_name] = None
                self.refresh_summary()
        else:
            msg += "<b>Recommended Action:</b> All machines manned is optimal.<br>"
            msg += "We have enough hot seaters or parking a digger loses too much production."
            QMessageBox.information(self, "Optimization Recommendation", msg)

    def refresh_summary(self):
        while self.summary_layout.count():
            item = self.summary_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
                
        all_machines = self.wizard.state_manager.state.machines
        all_operators = self.wizard.state_manager.state.operators
        
        active_machines = [m for m in all_machines if m.name not in self.wizard.not_required_machines]
        not_required_machines = [m for m in all_machines if m.name in self.wizard.not_required_machines]
        
        assigned_ops_set = set()
        
        # Section 1: Active Machines
        sec1 = self._create_section_card(
            f"🚜 Operational Equipment ({len(active_machines)} machines)",
            "#0284c7"
        )
        sec1_layout = QVBoxLayout(sec1)
        sec1_layout.setContentsMargins(12, 10, 12, 10)
        sec1_layout.setSpacing(6)
        
        if not active_machines:
            sec1_layout.addWidget(QLabel("No operational machines configured.", styleSheet="color: #64748b; font-style: italic;"))
        else:
            for m in active_machines:
                op_name = self.wizard.allocations.get(m.name, None)
                if op_name:
                    assigned_ops_set.add(op_name)
                    row_lbl = QLabel(f"• <b>{m.name}</b> ({m.type}) ➔ <span style='color: #4ade80; font-weight: bold;'>👷 {op_name}</span>")
                else:
                    row_lbl = QLabel(f"• <b>{m.name}</b> ({m.type}) ➔ <span style='color: #fbbf24; font-style: italic;'>⚠️ Unassigned (No Operator)</span>")
                row_lbl.setStyleSheet("font-size: 13px; color: #e2e8f0; background: transparent;")
                sec1_layout.addWidget(row_lbl)
        self.summary_layout.addWidget(sec1)
        
        # Section 2: Standby Relief Pool
        standby_ops = [
            op for op in all_operators
            if op.name not in self.wizard.absent_operators and op.name not in assigned_ops_set
        ]
        
        sec2 = self._create_section_card(
            f"⏳ Standby Relief Crew / Hot Seat Queue ({len(standby_ops)} operators)",
            "#d97706"
        )
        sec2_layout = QVBoxLayout(sec2)
        sec2_layout.setContentsMargins(12, 10, 12, 10)
        sec2_layout.setSpacing(6)
        
        if not standby_ops:
            sec2_layout.addWidget(QLabel("No operators on standby (All present crew are assigned to machines).", styleSheet="color: #64748b; font-style: italic;"))
        else:
            for op in standby_ops:
                quals_str = ", ".join(op.qualifications)
                op_lbl = QLabel(f"• <b>👷 {op.name}</b> <span style='color: #94a3b8; font-size: 11px;'>[Quals: {quals_str}]</span>")
                op_lbl.setStyleSheet("font-size: 13px; color: #fbbf24; background: transparent;")
                sec2_layout.addWidget(op_lbl)
        self.summary_layout.addWidget(sec2)
        
        # Section 3: Not Required Machines
        if not_required_machines:
            sec3 = self._create_section_card(
                f"⊘ Parked / Not Required Equipment ({len(not_required_machines)} machines)",
                "#475569"
            )
            sec3_layout = QVBoxLayout(sec3)
            sec3_layout.setContentsMargins(12, 10, 12, 10)
            sec3_layout.setSpacing(4)
            for m in not_required_machines:
                nr_lbl = QLabel(f"• {m.name} ({m.type}) - Parked (Will not factor into shift schedule)")
                nr_lbl.setStyleSheet("font-size: 12px; color: #94a3b8; background: transparent;")
                sec3_layout.addWidget(nr_lbl)
            self.summary_layout.addWidget(sec3)
            
        # Section 4: Absent Crew
        absent_ops = [op for op in all_operators if op.name in self.wizard.absent_operators]
        if absent_ops:
            sec4 = self._create_section_card(
                f"🏖 Absent / On Leave Today ({len(absent_ops)} operators)",
                "#7c3aed"
            )
            sec4_layout = QVBoxLayout(sec4)
            sec4_layout.setContentsMargins(12, 10, 12, 10)
            sec4_layout.setSpacing(4)
            for op in absent_ops:
                ab_lbl = QLabel(f"• 🏖 {op.name}")
                ab_lbl.setStyleSheet("font-size: 12px; color: #c084fc; background: transparent;")
                sec4_layout.addWidget(ab_lbl)
            self.summary_layout.addWidget(sec4)

    def _create_section_card(self, title: str, accent_color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #1e293b;
                border: 1px solid #334155;
                border-left: 4px solid {accent_color};
                border-radius: 6px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 8, 12, 8)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {accent_color}; padding-bottom: 4px; background: transparent;")
        card_layout.addWidget(title_lbl)
        return card


class AllocationWizardDialog(QDialog):
    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.setWindowTitle("Shift Setup & Equipment Allocation Wizard")
        self.resize(920, 720)
        
        self.absent_operators: Set[str] = set(
            op.name for op in self.state_manager.state.operators if op.status == 'absent'
        )
        self.not_required_machines: Set[str] = set(
            m.name for m in self.state_manager.state.machines if m.status == 'not_required'
        )
        self.allocations: Dict[str, Optional[str]] = {}
        assigned_so_far = set()
        for m in self.state_manager.state.machines:
            if (
                m.currentOperatorId
                and m.currentOperatorId not in self.absent_operators
                and m.currentOperatorId not in assigned_so_far
            ):
                self.allocations[m.name] = m.currentOperatorId
                assigned_so_far.add(m.currentOperatorId)
            else:
                self.allocations[m.name] = None

        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: white; }
            QLabel { color: white; }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        step_names = ["Attendance", "Diggers", "ROM Loaders", "Auxiliary", "Trucks", "Review"]
        self.step_indicator = StepIndicator(step_names, current_step=0)
        self.step_indicator.step_clicked.connect(self.go_to_step)
        main_layout.addWidget(self.step_indicator)
        
        self.pages = QStackedWidget()
        
        self.attendance_step = AttendanceStepWidget(self)
        self.pages.addWidget(self.attendance_step)
        
        self.diggers_step = EquipmentCategoryStepWidget(
            "Step 2: Assign Diggers / Excavators",
            "Assign an operator to each digger pit, or mark diggers as Not Required.",
            is_digger,
            self
        )
        self.pages.addWidget(self.diggers_step)
        
        self.rom_step = EquipmentCategoryStepWidget(
            "Step 3: Assign ROM Loaders",
            "Assign an operator to each ROM Loader, or mark as Not Required.",
            is_rom_loader,
            self
        )
        self.pages.addWidget(self.rom_step)
        
        self.aux_step = EquipmentCategoryStepWidget(
            "Step 4: Assign Support Equipment",
            "Assign operators to support machines (Dozers, Graders, Water Carts), or mark as Not Required.",
            is_auxiliary,
            self
        )
        self.pages.addWidget(self.aux_step)
        
        self.trucks_step = EquipmentCategoryStepWidget(
            "Step 5: Assign Haul Trucks",
            "Assign truck drivers or use 'Auto-Fill Remaining Operators' to populate trucks automatically.",
            is_truck,
            self,
            is_truck_step=True
        )
        self.pages.addWidget(self.trucks_step)
        
        self.review_step = ReviewStepWidget(self)
        self.pages.addWidget(self.review_step)
        
        main_layout.addWidget(self.pages, 1)
        
        footer = QFrame()
        footer.setStyleSheet("background-color: #1e293b; border-top: 1px solid #334155;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 12, 20, 12)
        footer_layout.setSpacing(12)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #475569; color: white; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)
        
        footer_layout.addStretch()
        
        self.back_btn = QPushButton("‹ Back")
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: white;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #475569; }
            QPushButton:disabled { background-color: #1e293b; color: #475569; border-color: #334155; }
        """)
        self.back_btn.clicked.connect(self.go_prev)
        footer_layout.addWidget(self.back_btn)
        
        self.next_btn = QPushButton("Next ›")
        self.next_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: 1px solid #60a5fa;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.next_btn.clicked.connect(self.go_next)
        footer_layout.addWidget(self.next_btn)
        
        self.apply_btn = QPushButton("🚀 Apply & Start Shift")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: white;
                border: 1px solid #10b981;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.apply_btn.clicked.connect(self.apply_and_finish)
        self.apply_btn.setVisible(False)
        footer_layout.addWidget(self.apply_btn)
        
        main_layout.addWidget(footer)
        
        self.go_to_step(0)

    def go_to_step(self, step_idx: int):
        if step_idx < 0 or step_idx >= self.pages.count():
            return
            
        self.pages.setCurrentIndex(step_idx)
        self.step_indicator.set_current_step(step_idx)
        
        self.back_btn.setEnabled(step_idx > 0)
        
        if step_idx == self.pages.count() - 1:
            self.next_btn.setVisible(False)
            self.apply_btn.setVisible(True)
            self.review_step.refresh_summary()
        else:
            self.next_btn.setVisible(True)
            self.apply_btn.setVisible(False)
            
        current_widget = self.pages.currentWidget()
        if isinstance(current_widget, AttendanceStepWidget):
            current_widget.update_list()
        elif isinstance(current_widget, EquipmentCategoryStepWidget):
            current_widget.refresh_rows()
        elif isinstance(current_widget, ReviewStepWidget):
            current_widget.refresh_summary()

    def go_prev(self):
        curr = self.pages.currentIndex()
        if curr > 0:
            self.go_to_step(curr - 1)

    def go_next(self):
        curr = self.pages.currentIndex()
        if curr < self.pages.count() - 1:
            self.go_to_step(curr + 1)

    def apply_and_finish(self):
        reset_time = self.review_step.reset_clock_cb.isChecked()
        reset_metrics = self.review_step.reset_metrics_cb.isChecked()
        
        self.state_manager.apply_daily_allocation(
            allocations=self.allocations,
            absent_operator_names=list(self.absent_operators),
            not_required_machine_names=list(self.not_required_machines),
            reset_shift_time=reset_time,
            reset_metrics=reset_metrics
        )
        
        self.accept()
