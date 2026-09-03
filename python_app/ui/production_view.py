from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QMessageBox, QDialog, QFormLayout, QLineEdit, QComboBox, QSpinBox
)
from PySide6.QtCore import Qt
import uuid
from core.models import ProductionTask

class TaskAddDialog(QDialog):
    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Production Task")
        self.state_manager = state_manager
        
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit()
        self.desc_input = QLineEdit()
        
        self.machine_type_combo = QComboBox()
        # Collect unique machine types
        types = set(m.type for m in self.state_manager.state.machines)
        self.machine_type_combo.addItems(sorted(types))
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(15, 1440)
        self.duration_spin.setValue(120)
        
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 100)
        self.priority_spin.setValue(50)
        
        layout.addRow("Task Name:", self.name_input)
        layout.addRow("Description:", self.desc_input)
        layout.addRow("Machine Type:", self.machine_type_combo)
        layout.addRow("Est. Duration (mins):", self.duration_spin)
        layout.addRow("Priority (1-100, higher=first):", self.priority_spin)
        
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        layout.addRow(btn_layout)
        
    def get_task(self) -> ProductionTask:
        return ProductionTask(
            id=str(uuid.uuid4()),
            name=self.name_input.text() or "New Task",
            description=self.desc_input.text(),
            machineType=self.machine_type_combo.currentText(),
            priority=self.priority_spin.value(),
            estimatedDurationMinutes=self.duration_spin.value(),
            setupTimeFromPrevious=15,
            status='pending',
            assignedMachineId=None,
            completedAt=None
        )

class ProductionView(QWidget):
    def __init__(self, state_manager, parent=None):
        super().__init__(parent)
        self.state_manager = state_manager
        self.state_manager.state_changed.connect(self.refresh_table)
        
        layout = QVBoxLayout(self)
        
        header_lbl = QLabel("🚜 Production Queue")
        header_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
        layout.addWidget(header_lbl)
        
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Name", "Machine Type", "Priority", "Duration (mins)", "Status", "Assigned To"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("➕ Add Task")
        add_btn.clicked.connect(self.add_task)
        remove_btn = QPushButton("🗑 Remove Selected")
        remove_btn.clicked.connect(self.remove_task)
        
        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(remove_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        self.refresh_table()

    def add_task(self):
        dialog = TaskAddDialog(self.state_manager, self)
        if dialog.exec():
            task = dialog.get_task()
            self.state_manager.production_queue.add_task(task)
            self.refresh_table()
            
    def remove_task(self):
        selected = self.table.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        task_id = self.table.item(row, 0).data(Qt.UserRole)
        self.state_manager.production_queue.remove_task(task_id)
        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(0)
        tasks = self.state_manager.production_queue.tasks
        for i, t in enumerate(tasks):
            self.table.insertRow(i)
            
            name_item = QTableWidgetItem(t.name)
            name_item.setData(Qt.UserRole, t.id)
            
            self.table.setItem(i, 0, name_item)
            self.table.setItem(i, 1, QTableWidgetItem(t.machineType))
            self.table.setItem(i, 2, QTableWidgetItem(str(t.priority)))
            self.table.setItem(i, 3, QTableWidgetItem(str(t.estimatedDurationMinutes)))
            self.table.setItem(i, 4, QTableWidgetItem(t.status))
            self.table.setItem(i, 5, QTableWidgetItem(t.assignedMachineId or "--"))
