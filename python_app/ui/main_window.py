from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTabWidget,
    QLabel, QPushButton, QFrame, QCheckBox
)
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

from .atb_queue import ATBQueueWidget
from .views import ZoneView, EquipmentView, OperatorsView

class MainWindow(QMainWindow):
    def __init__(self, state_manager):
        super().__init__()
        self.state_manager = state_manager
        self.setWindowTitle("ReliefScheduler - Python Edition")
        self.resize(1120, 800)
        
        # Dark Theme
        self.setStyleSheet("QMainWindow { background-color: #0f172a; }")
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Sidebar
        self.sidebar = ATBQueueWidget(self.state_manager)
        layout.addWidget(self.sidebar)
        
        # Main Area
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 8, 10, 4)
        header_layout.setSpacing(12)
        
        header = QLabel("ReliefScheduler")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #f59e0b;")
        header_layout.addWidget(header)
        
        header_layout.addSpacing(10)
        
        # --- Simulation Playback Control Bar ---
        sim_controls = QFrame()
        sim_controls.setStyleSheet("""
            QFrame {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
            }
        """)
        sim_layout = QHBoxLayout(sim_controls)
        sim_layout.setContentsMargins(8, 4, 8, 4)
        sim_layout.setSpacing(8)
        
        # Digital Clock Readout
        self.clock_lbl = QLabel("🕒 07:00 (Day Shift)")
        self.clock_lbl.setStyleSheet("""
            color: #38bdf8;
            font-size: 13px;
            font-weight: bold;
            padding: 3px 10px;
            background-color: #0f172a;
            border: 1px solid #0284c7;
            border-radius: 4px;
        """)
        sim_layout.addWidget(self.clock_lbl)
        
        # Play / Pause button
        self.play_pause_btn = QPushButton("⏸ Pause")
        self.play_pause_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: white;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        self.play_pause_btn.clicked.connect(self.on_toggle_pause)
        sim_layout.addWidget(self.play_pause_btn)
        
        # Speed buttons (1x, 2x, 4x)
        self.speed_btns = {}
        for spd in [1.0, 2.0, 4.0]:
            btn = QPushButton(f"{int(spd)}x")
            btn.setFixedWidth(36)
            btn.clicked.connect(lambda _, s=spd: self.on_change_speed(s))
            sim_layout.addWidget(btn)
            self.speed_btns[spd] = btn
        self._update_speed_btn_styles()
        
        # Reset to 07:00 button
        self.reset_btn = QPushButton("⏮ 07:00")
        self.reset_btn.setToolTip("Reset simulation time to 07:00 (Shift Start)")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #cbd5e1;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px 8px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #475569; }
        """)
        self.reset_btn.clicked.connect(self.on_reset_shift)
        sim_layout.addWidget(self.reset_btn)
        
        # Auto-Accept Swaps Checkbox
        self.auto_accept_cb = QCheckBox("⚡ Auto-Accept Swaps")
        self.auto_accept_cb.setToolTip("Automatically execute planned breaks and relief swaps when scheduled time arrives")
        self.auto_accept_cb.setStyleSheet("""
            QCheckBox {
                color: #fde047;
                font-weight: bold;
                font-size: 11px;
                padding: 2px 6px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid #ca8a04;
                background-color: #0f172a;
            }
            QCheckBox::indicator:checked {
                background-color: #eab308;
            }
        """)
        self.auto_accept_cb.toggled.connect(self.state_manager.set_auto_accept_swaps)
        sim_layout.addWidget(self.auto_accept_cb)
        
        header_layout.addWidget(sim_controls)
        header_layout.addStretch()
        
        # Setup / Allocation Wizard button
        self.wizard_btn = QPushButton("🎯 Daily Setup Wizard")
        self.wizard_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669; 
                color: white; 
                border: 1px solid #10b981;
                border-radius: 4px; 
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.wizard_btn.clicked.connect(self.show_allocation_wizard)
        header_layout.addWidget(self.wizard_btn)

        # Settings button
        self.edit_btn = QPushButton("⚙ Edit")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; 
                color: white; 
                border-radius: 4px; 
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2563eb; }
        """)
        self.edit_btn.clicked.connect(self.show_settings)
        header_layout.addWidget(self.edit_btn)
        
        main_layout.addLayout(header_layout)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; background: #0f172a; }
            QTabBar::tab { background: #1e293b; color: #94a3b8; padding: 8px 16px; border: 1px solid #334155; }
            QTabBar::tab:selected { background: #334155; color: white; border-bottom: none; }
        """)
        
        self.zone_view = ZoneView(self.state_manager)
        self.equip_view = EquipmentView(self.state_manager)
        self.op_view = OperatorsView(self.state_manager)
        
        from .production_view import ProductionView
        self.prod_view = ProductionView(self.state_manager)
        
        from .reports_view import ReportsView
        self.reports_view = ReportsView(self.state_manager)
        
        self.tabs.addTab(self.zone_view, "Zone View")
        self.tabs.addTab(self.equip_view, "Equipment View")
        self.tabs.addTab(self.op_view, "Operators View")
        self.tabs.addTab(self.prod_view, "Production Queue")
        self.tabs.addTab(self.reports_view, "Analytics")
        
        main_layout.addWidget(self.tabs)
        layout.addWidget(main_area, 1) # Expand main area
        
        self.zone_view.update_view()
        self.equip_view.update_view()
        self.op_view.update_view()
        
        # Connect timer signal to update the clock display
        self.state_manager.time_ticked.connect(self.update_simulation_ui)
        self.update_simulation_ui()

    def update_simulation_ui(self):
        cur_time = self.state_manager.get_current_time()
        shift_name = "Day Shift" if 7 <= cur_time.hour < 19 else "Night Shift"
        self.clock_lbl.setText(f"🕒 {cur_time.strftime('%H:%M')} ({shift_name})")
        
        if self.state_manager.is_paused:
            self.play_pause_btn.setText("▶ Play")
            self.play_pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #16a34a;
                    color: white;
                    border: 1px solid #22c55e;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #15803d; }
            """)
        else:
            self.play_pause_btn.setText("⏸ Pause")
            self.play_pause_btn.setStyleSheet("""
                QPushButton {
                    background-color: #334155;
                    color: white;
                    border: 1px solid #475569;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-weight: bold;
                }
                QPushButton:hover { background-color: #475569; }
            """)
        self._update_speed_btn_styles()

    def _update_speed_btn_styles(self):
        cur_speed = self.state_manager.speed_multiplier
        for spd, btn in self.speed_btns.items():
            if abs(spd - cur_speed) < 0.01:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3b82f6;
                        color: white;
                        border: 1px solid #60a5fa;
                        border-radius: 4px;
                        padding: 4px 6px;
                        font-weight: bold;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #0f172a;
                        color: #94a3b8;
                        border: 1px solid #334155;
                        border-radius: 4px;
                        padding: 4px 6px;
                        font-weight: normal;
                    }
                    QPushButton:hover { background-color: #334155; color: white; }
                """)

    def on_toggle_pause(self):
        self.state_manager.toggle_pause()
        self.update_simulation_ui()

    def on_change_speed(self, multiplier):
        self.state_manager.set_speed(multiplier)
        self._update_speed_btn_styles()

    def on_reset_shift(self):
        self.state_manager.reset_to_start_of_shift()
        self.update_simulation_ui()

    def show_allocation_wizard(self):
        from .allocation_wizard import AllocationWizardDialog
        dialog = AllocationWizardDialog(self.state_manager, self)
        if dialog.exec():
            self.state_manager.state_changed.emit()

    def show_settings(self):
        from .settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.state_manager, self)
        if dialog.exec():
            # If settings were saved, update views
            self.state_manager.state_changed.emit()


