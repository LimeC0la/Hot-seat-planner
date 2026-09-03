from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QLineEdit, QFormLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QSpinBox, QCheckBox,
    QComboBox, QScrollArea, QFrame, QGridLayout, QAbstractItemView,
    QDoubleSpinBox
)
from PySide6.QtCore import Qt
from typing import List, Optional, Set, Tuple
from core.models import Zone, Operator, Machine, ZoneConnection
from ui.map_view import LocationsMapTab

STANDARD_EQUIPMENT_TYPES = [
    "Digger",
    "Truck",
    "ROM Loader",
    "Dozer",
    "Grader",
    "Water Cart"
]

class OperatorEditDialog(QDialog):
    def __init__(self, operator: Optional[Operator] = None, all_known_quals: Optional[List[str]] = None, parent=None):
        super().__init__(parent)
        self.operator = operator
        self.setWindowTitle("✏ Edit Operator" if operator else "➕ Add New Operator")
        self.resize(520, 500)
        
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: white; }
            QLabel { color: #e2e8f0; font-size: 13px; font-weight: 500; }
            QLineEdit, QComboBox {
                background-color: #1e293b;
                color: white;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #3b82f6; }
            QCheckBox { color: white; font-size: 13px; }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        
        # Name
        name_layout = QVBoxLayout()
        name_lbl = QLabel("Operator / Crew Name:")
        name_layout.addWidget(name_lbl)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. John Smith")
        if operator:
            self.name_input.setText(operator.name)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Qualifications Picker
        quals_box = QFrame()
        quals_box.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 10px;")
        quals_box_layout = QVBoxLayout(quals_box)
        quals_box_layout.setSpacing(8)
        
        quals_header = QHBoxLayout()
        quals_lbl = QLabel("Qualifications (Pick all that apply):")
        quals_lbl.setStyleSheet("font-weight: bold; color: #38bdf8;")
        quals_header.addWidget(quals_lbl)
        quals_header.addStretch()
        
        sel_all_btn = QPushButton("All")
        sel_all_btn.setFixedSize(40, 24)
        sel_all_btn.setStyleSheet("background-color: #334155; color: #cbd5e1; font-size: 11px; padding: 2px 4px;")
        sel_all_btn.clicked.connect(self.select_all_quals)
        quals_header.addWidget(sel_all_btn)
        
        clear_all_btn = QPushButton("None")
        clear_all_btn.setFixedSize(45, 24)
        clear_all_btn.setStyleSheet("background-color: #334155; color: #cbd5e1; font-size: 11px; padding: 2px 4px;")
        clear_all_btn.clicked.connect(self.clear_all_quals)
        quals_header.addWidget(clear_all_btn)
        
        quals_box_layout.addLayout(quals_header)
        
        # Qualifications Checkbox Grid
        self.qual_checkboxes: dict[str, QCheckBox] = {}
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 4, 0, 4)
        self.grid_layout.setSpacing(10)
        
        # Aggregate standard and known qualifications
        combined_quals = list(STANDARD_EQUIPMENT_TYPES)
        if all_known_quals:
            for q in all_known_quals:
                if q and q not in combined_quals:
                    combined_quals.append(q)
        if operator and operator.qualifications:
            for q in operator.qualifications:
                if q and q not in combined_quals:
                    combined_quals.append(q)
                    
        current_quals_set = set(operator.qualifications) if operator else set()
        
        for idx, q_name in enumerate(combined_quals):
            cb = QCheckBox(q_name)
            cb.setChecked(q_name in current_quals_set)
            row = idx // 2
            col = idx % 2
            self.grid_layout.addWidget(cb, row, col)
            self.qual_checkboxes[q_name] = cb
            
        quals_box_layout.addWidget(self.grid_widget)
        
        # Add Custom Qualification row
        custom_qual_layout = QHBoxLayout()
        self.custom_qual_input = QLineEdit()
        self.custom_qual_input.setPlaceholderText("Add custom qualification (e.g. Scraper)...")
        self.custom_qual_input.setStyleSheet("font-size: 12px; padding: 4px 8px;")
        custom_qual_layout.addWidget(self.custom_qual_input, 1)
        
        add_qual_btn = QPushButton("➕ Add")
        add_qual_btn.setStyleSheet("background-color: #065f46; color: #6ee7b7; font-size: 12px; padding: 4px 10px;")
        add_qual_btn.clicked.connect(self.add_custom_qualification)
        custom_qual_layout.addWidget(add_qual_btn)
        
        quals_box_layout.addLayout(custom_qual_layout)
        layout.addWidget(quals_box)
        
        # ── Phase 1: Competency Multipliers (§2.1) ──
        comp_box = QFrame()
        comp_box.setStyleSheet("background-color: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 10px;")
        comp_box_layout = QVBoxLayout(comp_box)
        comp_box_layout.setSpacing(6)
        
        comp_lbl = QLabel("Competency Multipliers (lower = faster/expert):")
        comp_lbl.setStyleSheet("font-weight: bold; color: #34d399;")
        comp_box_layout.addWidget(comp_lbl)
        
        comp_hint = QLabel("1.0 = baseline · 0.5 = expert · 1.5+ = novice")
        comp_hint.setStyleSheet("color: #64748b; font-size: 11px; font-style: italic;")
        comp_box_layout.addWidget(comp_hint)
        
        self.competency_spins: dict[str, QDoubleSpinBox] = {}
        self.comp_grid = QGridLayout()
        self.comp_grid.setContentsMargins(0, 4, 0, 4)
        self.comp_grid.setSpacing(8)
        
        existing_multipliers = operator.competencyMultipliers if operator else {}
        for idx, q_name in enumerate(combined_quals):
            label = QLabel(f"  {q_name}:")
            label.setStyleSheet("color: #94a3b8; font-size: 12px;")
            spin = QDoubleSpinBox()
            spin.setRange(0.5, 2.0)
            spin.setSingleStep(0.1)
            spin.setDecimals(1)
            spin.setValue(existing_multipliers.get(q_name, 1.0))
            spin.setStyleSheet("background-color: #0f172a; color: white; border: 1px solid #334155; border-radius: 4px; padding: 3px;")
            spin.setFixedWidth(70)
            row = idx // 2
            col = (idx % 2) * 2
            self.comp_grid.addWidget(label, row, col)
            self.comp_grid.addWidget(spin, row, col + 1)
            self.competency_spins[q_name] = spin
        
        comp_box_layout.addLayout(self.comp_grid)
        layout.addWidget(comp_box)
        
        # Status
        status_layout = QHBoxLayout()
        status_lbl = QLabel("Initial Status:")
        status_layout.addWidget(status_lbl)
        
        self.status_combo = QComboBox()
        self.status_combo.addItem("Standby / Spare", "standby")
        self.status_combo.addItem("Working", "working")
        self.status_combo.addItem("On Break", "on_break")
        self.status_combo.addItem("Absent / Leave", "absent")
        
        if operator:
            idx = self.status_combo.findData(operator.status)
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
        status_layout.addWidget(self.status_combo, 1)
        layout.addLayout(status_layout)
        
        layout.addStretch()
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #475569;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Operator")
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)

    def select_all_quals(self):
        for cb in self.qual_checkboxes.values():
            cb.setChecked(True)

    def clear_all_quals(self):
        for cb in self.qual_checkboxes.values():
            cb.setChecked(False)

    def add_custom_qualification(self):
        text = self.custom_qual_input.text().strip()
        if not text:
            return
        if text not in self.qual_checkboxes:
            cb = QCheckBox(text)
            cb.setChecked(True)
            idx = len(self.qual_checkboxes)
            row = idx // 2
            col = idx % 2
            self.grid_layout.addWidget(cb, row, col)
            self.qual_checkboxes[text] = cb
            self.custom_qual_input.clear()

    def save(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Operator name cannot be empty.")
            return
        self.accept()

    def get_data(self) -> Operator:
        name = self.name_input.text().strip()
        quals = [q_name for q_name, cb in self.qual_checkboxes.items() if cb.isChecked()]
        status = self.status_combo.currentData()
        
        # Build competency multipliers (only for qualified types, store non-default values)
        comp_multipliers = {}
        for q_name in quals:
            if q_name in self.competency_spins:
                val = round(self.competency_spins[q_name].value(), 1)
                comp_multipliers[q_name] = val
        
        return Operator(
            name=name,
            id=name,
            qualifications=quals,
            status=status,
            standbyTimeMinutes=self.operator.standbyTimeMinutes if self.operator else 0,
            breaksTaken=self.operator.breaksTaken if self.operator else 0,
            currentAssignmentId=self.operator.currentAssignmentId if self.operator else None,
            competencyMultipliers=comp_multipliers,
            cumulativeFatigueMinutes=self.operator.cumulativeFatigueMinutes if self.operator else 0.0,
            consecutiveShiftsWorked=self.operator.consecutiveShiftsWorked if self.operator else 0,
            lastFullRestEnd=self.operator.lastFullRestEnd if self.operator else None,
            alertnessScore=self.operator.alertnessScore if self.operator else 1.0,
        )


class MachineEditDialog(QDialog):
    def __init__(self, machine: Optional[Machine] = None, known_zones: Optional[List[str]] = None, all_known_types: Optional[List[str]] = None, parent=None):
        super().__init__(parent)
        self.machine = machine
        self.setWindowTitle("✏ Edit Machine" if machine else "➕ Add New Machine")
        self.resize(480, 400)
        
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: white; }
            QLabel { color: #e2e8f0; font-size: 13px; font-weight: 500; }
            QLineEdit, QComboBox {
                background-color: #1e293b;
                color: white;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #3b82f6; }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        
        # Machine Name
        name_layout = QVBoxLayout()
        name_lbl = QLabel("Machine Name / ID:")
        name_layout.addWidget(name_lbl)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g. EX-121, DT-235, LD-512")
        if machine:
            self.name_input.setText(machine.name)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # Machine Type Dropdown (Pickable)
        type_layout = QVBoxLayout()
        type_lbl = QLabel("Machine Type (Pick or Type Custom):")
        type_layout.addWidget(type_lbl)
        
        self.type_combo = QComboBox()
        self.type_combo.setEditable(True)
        
        # Add standard types
        types_set = set(STANDARD_EQUIPMENT_TYPES)
        if all_known_types:
            for t in all_known_types:
                if t:
                    types_set.add(t)
        if machine and machine.type:
            types_set.add(machine.type)
            
        for t in sorted(list(types_set)):
            self.type_combo.addItem(t)
            
        if machine and machine.type:
            self.type_combo.setCurrentText(machine.type)
        else:
            self.type_combo.setCurrentIndex(0)
            
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)
        
        # Zone / Location Dropdown
        zone_layout = QVBoxLayout()
        zone_lbl = QLabel("Assigned Location / Zone:")
        zone_layout.addWidget(zone_lbl)
        
        self.zone_combo = QComboBox()
        self.zone_combo.addItem("-- Unassigned --", "")
        if known_zones:
            for z in known_zones:
                self.zone_combo.addItem(f"📍 {z}", z)
                
        if machine and machine.zoneId:
            idx = self.zone_combo.findData(machine.zoneId)
            if idx >= 0:
                self.zone_combo.setCurrentIndex(idx)
        zone_layout.addWidget(self.zone_combo)
        layout.addLayout(zone_layout)
        
        # Status Dropdown
        status_layout = QVBoxLayout()
        status_lbl = QLabel("Operating Status:")
        status_layout.addWidget(status_lbl)
        
        self.status_combo = QComboBox()
        self.status_combo.addItem("Operational", "operational")
        self.status_combo.addItem("Not Required (Parked)", "not_required")
        self.status_combo.addItem("Maintenance / Out of Service", "maintenance")
        self.status_combo.addItem("Blast Exclusion", "blast_exclusion")
        
        if machine:
            idx = self.status_combo.findData(machine.status)
            if idx >= 0:
                self.status_combo.setCurrentIndex(idx)
        status_layout.addWidget(self.status_combo)
        layout.addLayout(status_layout)
        
        layout.addStretch()
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #475569;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Machine")
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)

    def save(self):
        name = self.name_input.text().strip()
        m_type = self.type_combo.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Machine name cannot be empty.")
            return
        if not m_type:
            QMessageBox.warning(self, "Validation Error", "Machine type cannot be empty.")
            return
        self.accept()

    def get_data(self) -> Machine:
        name = self.name_input.text().strip()
        m_type = self.type_combo.currentText().strip()
        zone_id = self.zone_combo.currentData() or ""
        status = self.status_combo.currentData()
        
        return Machine(
            name=name,
            id=name,
            type=m_type,
            zoneId=zone_id,
            status=status,
            transitTimeMinutes=0,
            currentOperatorId=self.machine.currentOperatorId if self.machine else None
        )


class GeneralSettingsTab(QWidget):
    def __init__(self, settings):
        super().__init__()
        layout = QFormLayout(self)
        layout.setSpacing(12)
        
        self.operating_spin = QSpinBox()
        self.operating_spin.setRange(15, 720)
        self.operating_spin.setSingleStep(15)
        self.operating_spin.setValue(settings.defaultOperatingTimeMinutes)
        
        self.break_spin = QSpinBox()
        self.break_spin.setRange(5, 180)
        self.break_spin.setSingleStep(5)
        self.break_spin.setValue(settings.breakDurationMinutes)

        self.break_cooldown_spin = QSpinBox()
        self.break_cooldown_spin.setRange(0, 360)
        self.break_cooldown_spin.setSingleStep(15)
        self.break_cooldown_spin.setValue(settings.breakCooldownMinutes)

        self.shift_window_start_spin = QSpinBox()
        self.shift_window_start_spin.setRange(0, 360)
        self.shift_window_start_spin.setSingleStep(15)
        self.shift_window_start_spin.setValue(settings.shiftBreakWindowStartOffsetMinutes)

        self.shift_window_end_spin = QSpinBox()
        self.shift_window_end_spin.setRange(0, 360)
        self.shift_window_end_spin.setSingleStep(15)
        self.shift_window_end_spin.setValue(settings.shiftBreakWindowEndOffsetMinutes)

        self.target_breaks_spin = QSpinBox()
        self.target_breaks_spin.setRange(1, 10)
        self.target_breaks_spin.setValue(settings.targetBreaksPerShift)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 999)
        self.duration_spin.setValue(settings.durationTimingBuffer)
        
        self.padding_spin = QSpinBox()
        self.padding_spin.setRange(0, 999)
        self.padding_spin.setValue(settings.paddingMinutes)
        
        self.even_work_cb = QCheckBox("Balance work hours evenly across crew (Prefer least hours worked)")
        self.even_work_cb.setChecked(settings.preferEvenWorkTime)
        
        self.auto_plan_cb = QCheckBox("Automatically project and plan future break schedule and relief")
        self.auto_plan_cb.setChecked(settings.autoPlanEnabled)
        
        layout.addRow("Max Continuous Operating Time (mins):", self.operating_spin)
        layout.addRow("Break Duration (mins):", self.break_spin)
        layout.addRow("Break Cooldown / Spacing (mins):", self.break_cooldown_spin)
        layout.addRow("No Breaks in First (mins of shift):", self.shift_window_start_spin)
        layout.addRow("No Breaks in Last (mins of shift):", self.shift_window_end_spin)
        layout.addRow("Target Breaks per Shift:", self.target_breaks_spin)
        layout.addRow("Duration Timing Buffer (mins):", self.duration_spin)
        layout.addRow("Padding Minutes:", self.padding_spin)
        layout.addRow("Relief Strategy:", self.even_work_cb)
        layout.addRow("Auto Planning:", self.auto_plan_cb)
        
        # ── Phase 1: Handover & Fatigue Settings ──
        sep_label = QLabel("── Hotseating & Fatigue ──")
        sep_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-top: 10px;")
        layout.addRow(sep_label)
        
        self.handover_spin = QSpinBox()
        self.handover_spin.setRange(0, 30)
        self.handover_spin.setSingleStep(1)
        self.handover_spin.setValue(settings.handoverDurationMinutes)
        layout.addRow("Hotseating Handover Duration (mins):", self.handover_spin)
        
        self.max_consec_shifts_spin = QSpinBox()
        self.max_consec_shifts_spin.setRange(1, 14)
        self.max_consec_shifts_spin.setValue(settings.maxConsecutiveShifts)
        layout.addRow("Max Consecutive Shifts Before Reset:", self.max_consec_shifts_spin)
        
        self.mandatory_reset_spin = QSpinBox()
        self.mandatory_reset_spin.setRange(12, 96)
        self.mandatory_reset_spin.setSingleStep(12)
        self.mandatory_reset_spin.setValue(settings.mandatoryResetHours)
        layout.addRow("Mandatory Reset Period (hours):", self.mandatory_reset_spin)
        
        # ── Phase 2: Advanced Break Scheduling (BAP) ──
        bap_label = QLabel("── Phase 2: BAP Settings ──")
        bap_label.setStyleSheet("color: #a78bfa; font-weight: bold; font-size: 13px; margin-top: 10px;")
        layout.addRow(bap_label)

        self.fractionable_cb = QCheckBox("Enable Fractionable Breaks")
        self.fractionable_cb.setChecked(settings.enableFractionableBreaks)
        self.fractionable_parts_spin = QSpinBox()
        self.fractionable_parts_spin.setRange(2, 4)
        self.fractionable_parts_spin.setValue(settings.fractionableBreakParts)
        layout.addRow(self.fractionable_cb, self.fractionable_parts_spin)

        self.variable_cb = QCheckBox("Enable Variable Break Length (Fatigue-based)")
        self.variable_cb.setChecked(settings.enableVariableBreakLength)
        layout.addRow(self.variable_cb)

        self.workstretch_spin = QSpinBox()
        self.workstretch_spin.setRange(60, 480)
        self.workstretch_spin.setSingleStep(15)
        self.workstretch_spin.setValue(settings.maxWorkstretchMinutes)
        layout.addRow("Max Workstretch (hard limit, mins):", self.workstretch_spin)

        self.circadian_cb = QCheckBox("Enable Circadian Low-Point Breaks")
        self.circadian_cb.setChecked(settings.enableCircadianScheduling)
        layout.addRow(self.circadian_cb)

        # ── Phase 3 & 4: Advanced Engines ──
        engine_label = QLabel("── Phase 3 & 4: Scheduling Engines ──")
        engine_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 13px; margin-top: 10px;")
        layout.addRow(engine_label)

        self.solver_cb = QCheckBox("Use Advanced Optimizer (OR-Tools CP-SAT) if available")
        self.solver_cb.setChecked(settings.useAdvancedSolver)
        layout.addRow(self.solver_cb)

        self.locked_horizon_spin = QSpinBox()
        self.locked_horizon_spin.setRange(0, 120)
        self.locked_horizon_spin.setSingleStep(5)
        self.locked_horizon_spin.setValue(settings.lockedHorizonMinutes)
        layout.addRow("Locked Horizon for Replanning (mins):", self.locked_horizon_spin)





class CrewTab(QWidget):
    def __init__(self, operators, parent=None):
        super().__init__(parent)
        self.operators_data = [
            Operator(
                name=o.name,
                qualifications=list(o.qualifications),
                id=o.id,
                status=o.status,
                standbyTimeMinutes=o.standbyTimeMinutes,
                breaksTaken=o.breaksTaken,
                currentAssignmentId=o.currentAssignmentId
            )
            for o in operators
        ]
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        hint_lbl = QLabel("💡 Tip: Double-click any row or click 'Edit Selected' to open the detailed qualifications picker.")
        hint_lbl.setStyleSheet("color: #94a3b8; font-style: italic; font-size: 12px;")
        layout.addWidget(hint_lbl)
        
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Crew Name", "Qualifications", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers) # Use popup dialog for editing!
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)
        
        self.refresh_table()
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add Operator")
        add_btn.clicked.connect(self.add_operator)
        
        edit_btn = QPushButton("✏ Edit Selected")
        edit_btn.setStyleSheet("background-color: #0284c7;")
        edit_btn.clicked.connect(self.edit_selected_operator)
        
        remove_btn = QPushButton("🗑 Remove Selected")
        remove_btn.setStyleSheet("background-color: #475569;")
        remove_btn.clicked.connect(self.remove_selected)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)

    def refresh_table(self):
        self.table.setRowCount(0)
        for op in self.operators_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(f"👷 {op.name}"))
            self.table.setItem(row, 1, QTableWidgetItem(", ".join(op.qualifications)))
            
            status_map = {
                'working': "🚜 Working",
                'standby': "⏳ Standby",
                'on_break': "☕ On Break",
                'absent': "🏖 Absent"
            }
            self.table.setItem(row, 2, QTableWidgetItem(status_map.get(op.status, op.status)))

    def on_row_double_clicked(self, row: int, col: int):
        self.edit_operator_at_row(row)

    def edit_selected_operator(self):
        selected_rows = list({item.row() for item in self.table.selectedItems()})
        if not selected_rows:
            QMessageBox.information(self, "Select Operator", "Please select an operator row to edit.")
            return
        self.edit_operator_at_row(selected_rows[0])

    def edit_operator_at_row(self, row: int):
        if row < 0 or row >= len(self.operators_data):
            return
        op = self.operators_data[row]
        all_quals = self._get_all_quals()
        dialog = OperatorEditDialog(op, all_known_quals=all_quals, parent=self)
        if dialog.exec():
            updated_op = dialog.get_data()
            self.operators_data[row] = updated_op
            self.refresh_table()
            self.table.selectRow(row)

    def add_operator(self):
        all_quals = self._get_all_quals()
        dialog = OperatorEditDialog(None, all_known_quals=all_quals, parent=self)
        if dialog.exec():
            new_op = dialog.get_data()
            self.operators_data.append(new_op)
            self.refresh_table()
            self.table.selectRow(len(self.operators_data) - 1)

    def remove_selected(self):
        selected_rows = sorted(list({item.row() for item in self.table.selectedItems()}), reverse=True)
        if not selected_rows:
            return
        for r in selected_rows:
            if 0 <= r < len(self.operators_data):
                self.operators_data.pop(r)
        self.refresh_table()

    def _get_all_quals(self) -> List[str]:
        quals = set()
        for op in self.operators_data:
            for q in op.qualifications:
                quals.add(q)
        return list(quals)

    def get_data(self) -> List[Operator]:
        return self.operators_data


class MachinesTab(QWidget):
    def __init__(self, machines, zones, parent=None):
        super().__init__(parent)
        self.zones = zones
        self.machines_data = [
            Machine(
                name=m.name,
                type=m.type,
                id=m.id,
                zoneId=m.zoneId,
                transitTimeMinutes=0,
                currentOperatorId=m.currentOperatorId,
                status=m.status
            )
            for m in machines
        ]
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        hint_lbl = QLabel("💡 Tip: Double-click any machine or click 'Edit Selected' to change type, location, and status.")
        hint_lbl.setStyleSheet("color: #94a3b8; font-style: italic; font-size: 12px;")
        layout.addWidget(hint_lbl)
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Machine Name", "Type", "Location", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.on_row_double_clicked)
        layout.addWidget(self.table)
        
        self.refresh_table()
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add Machine")
        add_btn.clicked.connect(self.add_machine)
        
        edit_btn = QPushButton("✏ Edit Selected")
        edit_btn.setStyleSheet("background-color: #0284c7;")
        edit_btn.clicked.connect(self.edit_selected_machine)
        
        remove_btn = QPushButton("🗑 Remove Selected")
        remove_btn.setStyleSheet("background-color: #475569;")
        remove_btn.clicked.connect(self.remove_selected)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)

    def refresh_table(self):
        self.table.setRowCount(0)
        for m in self.machines_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(f"🚜 {m.name}"))
            self.table.setItem(row, 1, QTableWidgetItem(m.type))
            self.table.setItem(row, 2, QTableWidgetItem(f"📍 {m.zoneId}" if m.zoneId else "Unassigned"))
            
            status_map = {
                'operational': "✅ Operational",
                'not_required': "⊘ Not Required",
                'maintenance': "🔧 Maintenance",
                'blast_exclusion': "💥 Blast Exclusion"
            }
            self.table.setItem(row, 3, QTableWidgetItem(status_map.get(m.status, m.status)))

    def on_row_double_clicked(self, row: int, col: int):
        self.edit_machine_at_row(row)

    def edit_selected_machine(self):
        selected_rows = list({item.row() for item in self.table.selectedItems()})
        if not selected_rows:
            QMessageBox.information(self, "Select Machine", "Please select a machine row to edit.")
            return
        self.edit_machine_at_row(selected_rows[0])

    def edit_machine_at_row(self, row: int):
        if row < 0 or row >= len(self.machines_data):
            return
        m = self.machines_data[row]
        known_zone_names = [z.name for z in self.zones]
        known_types = self._get_all_types()
        dialog = MachineEditDialog(m, known_zones=known_zone_names, all_known_types=known_types, parent=self)
        if dialog.exec():
            updated_m = dialog.get_data()
            self.machines_data[row] = updated_m
            self.refresh_table()
            self.table.selectRow(row)

    def add_machine(self):
        known_zone_names = [z.name for z in self.zones]
        known_types = self._get_all_types()
        dialog = MachineEditDialog(None, known_zones=known_zone_names, all_known_types=known_types, parent=self)
        if dialog.exec():
            new_m = dialog.get_data()
            self.machines_data.append(new_m)
            self.refresh_table()
            self.table.selectRow(len(self.machines_data) - 1)

    def remove_selected(self):
        selected_rows = sorted(list({item.row() for item in self.table.selectedItems()}), reverse=True)
        if not selected_rows:
            return
        for r in selected_rows:
            if 0 <= r < len(self.machines_data):
                self.machines_data.pop(r)
        self.refresh_table()

    def _get_all_types(self) -> List[str]:
        types = set()
        for m in self.machines_data:
            if m.type:
                types.add(m.type)
        return list(types)

    def get_data(self) -> List[Machine]:
        return self.machines_data


class SettingsDialog(QDialog):
    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.setWindowTitle("Shift & Site Configuration Settings")
        self.resize(860, 620)
        
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: white; }
            QLabel { color: white; }
            QTableWidget {
                background-color: #1e293b;
                color: white;
                gridline-color: #334155;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QTableWidget::item { padding: 6px; }
            QHeaderView::section { background-color: #334155; color: white; padding: 6px; font-weight: bold; }
            QLineEdit, QSpinBox {
                background-color: #1e293b;
                color: white;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 6px;
            }
            QCheckBox { color: white; }
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; }
            QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 8px 18px; border: 1px solid #334155; font-size: 13px; font-weight: 500; }
            QTabBar::tab:selected { background: #334155; color: white; border-bottom: none; font-weight: bold; }
        """)
        layout.addWidget(self.tabs)
        
        self.general_tab = GeneralSettingsTab(self.state_manager.state.settings)
        self.crew_tab = CrewTab(self.state_manager.state.operators)
        self.machines_tab = MachinesTab(self.state_manager.state.machines, self.state_manager.state.zones)
        self.locations_tab = LocationsMapTab(self.state_manager.state.zones, self.state_manager.state.zoneConnections)
        
        self.tabs.addTab(self.general_tab, "⚙ General Shift Rules")
        self.tabs.addTab(self.crew_tab, "👥 Crew & Qualifications")
        self.tabs.addTab(self.machines_tab, "🚜 Machines & Equipment")
        self.tabs.addTab(self.locations_tab, "📍 Locations & Pits")
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("background-color: #475569;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
        
    def save_settings(self):
        settings = self.state_manager.state.settings
        settings.defaultOperatingTimeMinutes = self.general_tab.operating_spin.value()
        settings.breakDurationMinutes = self.general_tab.break_spin.value()
        settings.breakCooldownMinutes = self.general_tab.break_cooldown_spin.value()
        settings.shiftBreakWindowStartOffsetMinutes = self.general_tab.shift_window_start_spin.value()
        settings.shiftBreakWindowEndOffsetMinutes = self.general_tab.shift_window_end_spin.value()
        settings.targetBreaksPerShift = self.general_tab.target_breaks_spin.value()
        settings.durationTimingBuffer = self.general_tab.duration_spin.value()
        settings.paddingMinutes = self.general_tab.padding_spin.value()
        settings.preferEvenWorkTime = self.general_tab.even_work_cb.isChecked()
        settings.autoPlanEnabled = self.general_tab.auto_plan_cb.isChecked()
        # Phase 1: Handover & Fatigue
        settings.handoverDurationMinutes = self.general_tab.handover_spin.value()
        settings.maxConsecutiveShifts = self.general_tab.max_consec_shifts_spin.value()
        settings.mandatoryResetHours = self.general_tab.mandatory_reset_spin.value()
        # Phase 2: BAP Settings
        settings.enableFractionableBreaks = self.general_tab.fractionable_cb.isChecked()
        settings.fractionableBreakParts = self.general_tab.fractionable_parts_spin.value()
        settings.enableVariableBreakLength = self.general_tab.variable_cb.isChecked()
        settings.maxWorkstretchMinutes = self.general_tab.workstretch_spin.value()
        settings.enableCircadianScheduling = self.general_tab.circadian_cb.isChecked()
        # Phase 3 & 4
        settings.useAdvancedSolver = self.general_tab.solver_cb.isChecked()
        settings.lockedHorizonMinutes = self.general_tab.locked_horizon_spin.value()
        
        zones, connections = self.locations_tab.get_data()
        self.state_manager.state.zones = zones
        self.state_manager.state.zoneConnections = connections
        
        # Save crew
        new_ops = self.crew_tab.get_data()
        old_ops_dict = {o.name: o for o in self.state_manager.state.operators}
        for op in new_ops:
            if op.name in old_ops_dict:
                old = old_ops_dict[op.name]
                if not op.status or op.status == 'standby':
                    op.status = old.status
                op.standbyTimeMinutes = old.standbyTimeMinutes
                op.breaksTaken = old.breaksTaken
                op.currentAssignmentId = old.currentAssignmentId
                # Preserve runtime fatigue state
                op.cumulativeFatigueMinutes = old.cumulativeFatigueMinutes
                op.alertnessScore = old.alertnessScore
                op.consecutiveShiftsWorked = old.consecutiveShiftsWorked
                op.lastFullRestEnd = old.lastFullRestEnd
        self.state_manager.state.operators = new_ops
        
        # Save machines
        new_machines = self.machines_tab.get_data()
        old_machines_dict = {m.name: m for m in self.state_manager.state.machines}
        for m in new_machines:
            if m.name in old_machines_dict:
                old = old_machines_dict[m.name]
                m.currentOperatorId = old.currentOperatorId
                if not m.status or m.status == 'operational':
                    m.status = old.status
        self.state_manager.state.machines = new_machines
        
        self.state_manager.save_state()
        self.state_manager.recompute_plan()
        self.accept()
