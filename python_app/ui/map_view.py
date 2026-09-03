import math
from typing import List, Tuple, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsView, 
    QGraphicsScene, QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem,
    QInputDialog, QDialog, QFormLayout, QLineEdit, QTableWidget,
    QComboBox, QSpinBox, QHeaderView, QAbstractItemView, QLabel
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPen, QBrush, QColor, QPainter

from core.models import Zone, ZoneConnection

class ConnectionEditDialog(QDialog):
    def __init__(self, zone: Zone, all_zones: List[Zone], current_conns: List[ZoneConnection], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Area: {zone.name}")
        self.resize(500, 400)
        self.zone = zone
        self.all_zones = all_zones
        self.result_conns = list(current_conns)
        
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QDialog { background-color: #0f172a; color: white; }
            QLabel { color: white; }
            QTableWidget { background-color: #1e293b; color: white; border: 1px solid #334155; }
            QHeaderView::section { background-color: #334155; color: white; padding: 6px; }
            QLineEdit, QSpinBox { background-color: #1e293b; color: white; border: 1px solid #334155; padding: 6px; }
            QPushButton { background-color: #3b82f6; color: white; padding: 6px 14px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #2563eb; }
        """)
        
        # Name
        form = QFormLayout()
        self.name_edit = QLineEdit(zone.name)
        form.addRow("Area Name:", self.name_edit)
        layout.addLayout(form)
        
        layout.addWidget(QLabel("Explicit Connections (Overrides auto-distance):"))
        self.conn_table = QTableWidget(0, 2)
        self.conn_table.setHorizontalHeaderLabels(["Target Area", "Time (Mins)"])
        self.conn_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.conn_table.verticalHeader().setDefaultSectionSize(40)
        self.conn_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.conn_table)
        
        # Populate existing conns
        for c in current_conns:
            if c.zone_a == zone.name or c.zone_b == zone.name:
                other = c.zone_b if c.zone_a == zone.name else c.zone_a
                self.add_conn_row(other, c.travelTimeMinutes)
                
        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ Add Connection")
        add_btn.clicked.connect(lambda: self.add_conn_row("", 5))
        del_btn = QPushButton("🗑 Remove")
        del_btn.setStyleSheet("background-color: #475569;")
        del_btn.clicked.connect(self.remove_conn_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)
        
        save_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        save_layout.addStretch()
        save_layout.addWidget(save_btn)
        layout.addLayout(save_layout)
        
    def add_conn_row(self, target="", time=5):
        row = self.conn_table.rowCount()
        self.conn_table.insertRow(row)
        combo = QComboBox()
        combo.setStyleSheet("background-color: #1e293b; color: white; padding: 4px;")
        names = [z.name for z in self.all_zones if z.name != self.zone.name]
        combo.addItems(names)
        if target: combo.setCurrentText(target)
        spin = QSpinBox()
        spin.setRange(0, 999)
        spin.setValue(time)
        self.conn_table.setCellWidget(row, 0, combo)
        self.conn_table.setCellWidget(row, 1, spin)
        
    def remove_conn_row(self):
        row = self.conn_table.currentRow()
        if row >= 0:
            self.conn_table.removeRow(row)
            
    def get_data(self):
        new_name = self.name_edit.text().strip()
        conns = []
        seen_targets = set()
        for i in range(self.conn_table.rowCount()):
            combo = self.conn_table.cellWidget(i, 0)
            spin = self.conn_table.cellWidget(i, 1)
            if combo and spin:
                target = combo.currentText().strip()
                if target and target != new_name and target not in seen_targets:
                    seen_targets.add(target)
                    conns.append(ZoneConnection(new_name, target, spin.value()))
        return new_name, conns


class NodeItem(QGraphicsEllipseItem):
    def __init__(self, zone: Zone, map_view):
        super().__init__(-20, -20, 40, 40)
        self.zone = zone
        self.map_view = map_view
        self.is_dragged = False
        
        self.setBrush(QBrush(QColor("#3b82f6")))
        self.setPen(QPen(QColor("#60a5fa"), 2))
        self.setFlag(QGraphicsEllipseItem.ItemIsMovable)
        self.setFlag(QGraphicsEllipseItem.ItemIsSelectable)
        self.setFlag(QGraphicsEllipseItem.ItemSendsGeometryChanges)
        
        self.text = QGraphicsTextItem(zone.name, self)
        self.text.setDefaultTextColor(QColor("white"))
        font = self.text.font()
        font.setBold(True)
        self.text.setFont(font)
        self.update_text_pos()
        
    def update_text_pos(self):
        self.text.setPlainText(self.zone.name)
        rect = self.text.boundingRect()
        self.text.setPos(-rect.width()/2, -rect.height()/2 - 30)
        
    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.ItemPositionHasChanged:
            self.zone.x = value.x()
            self.zone.y = value.y()
            self.map_view.redraw_edges()
        return super().itemChange(change, value)
        
    def mousePressEvent(self, event):
        self.is_dragged = True
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        self.is_dragged = False
        super().mouseReleaseEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        self.map_view.edit_node(self)
        super().mouseDoubleClickEvent(event)


class LocationsMapTab(QWidget):
    def __init__(self, zones: List[Zone], connections: List[ZoneConnection]):
        super().__init__()
        self.zones = [Zone(name=z.name, id=z.id, hasActiveBlast=z.hasActiveBlast, x=z.x, y=z.y) for z in zones]
        self.connections = [ZoneConnection(c.zone_a, c.zone_b, c.travelTimeMinutes) for c in connections]
        
        self.init_layout_if_needed()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_physics)
        self.timer.start(30)
        
        self.layout = QVBoxLayout(self)
        
        tb = QHBoxLayout()
        add_btn = QPushButton("➕ Add Area")
        add_btn.clicked.connect(self.add_area)
        del_btn = QPushButton("🗑 Remove Selected")
        del_btn.setStyleSheet("background-color: #475569;")
        del_btn.clicked.connect(self.remove_selected)
        tb.addWidget(add_btn)
        tb.addWidget(del_btn)
        
        hint = QLabel("   💡 Tip: Drag nodes to set auto-distance (10px = 1m). Double click to edit explicit overrides.")
        hint.setStyleSheet("color: #94a3b8; font-style: italic;")
        tb.addWidget(hint)
        tb.addStretch()
        self.layout.addLayout(tb)
        
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor("#0f172a")))
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        self.layout.addWidget(self.view)
        
        self.node_items = {}
        self.edge_items = []
        
        self.populate_scene()
        
    def init_layout_if_needed(self):
        zeros = [z for z in self.zones if z.x == 0 and z.y == 0]
        cols = int(math.ceil(math.sqrt(len(zeros)))) if zeros else 1
        for i, z in enumerate(zeros):
            r, c = divmod(i, cols)
            z.x = (c + 1) * 100
            z.y = (r + 1) * 100
            
    def update_physics(self):
        k = 0.05
        forces = {z.name: [0.0, 0.0] for z in self.zones}
        
        for c in self.connections:
            if c.zone_a in self.node_items and c.zone_b in self.node_items:
                n1 = self.node_items[c.zone_a].zone
                n2 = self.node_items[c.zone_b].zone
                
                dx = n2.x - n1.x
                dy = n2.y - n1.y
                dist = math.hypot(dx, dy)
                if dist < 0.1:
                    dx, dy = 1.0, 0.0
                    dist = 1.0
                    
                target_dist = c.travelTimeMinutes * 10.0
                f = (dist - target_dist) * k
                fx = (dx / dist) * f
                fy = (dy / dist) * f
                
                forces[n1.name][0] += fx
                forces[n1.name][1] += fy
                forces[n2.name][0] -= fx
                forces[n2.name][1] -= fy
                
        moving = False
        for z in self.zones:
            node_item = self.node_items[z.name]
            if node_item.is_dragged:
                continue
                
            fx, fy = forces[z.name]
            if abs(fx) > 0.5 or abs(fy) > 0.5:
                z.x += fx
                z.y += fy
                node_item.setPos(z.x, z.y)
                moving = True
                
        if moving:
            self.redraw_edges()
            
    def populate_scene(self):
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()
        
        for z in self.zones:
            node = NodeItem(z, self)
            node.setPos(z.x, z.y)
            self.scene.addItem(node)
            self.node_items[z.name] = node
            
        self.redraw_edges()
        
    def redraw_edges(self):
        for e in self.edge_items:
            self.scene.removeItem(e)
        self.edge_items.clear()
        
        pen = QPen(QColor("#cbd5e1"), 2, Qt.DashLine)
        
        for c in self.connections:
            if c.zone_a in self.node_items and c.zone_b in self.node_items:
                n1 = self.node_items[c.zone_a]
                n2 = self.node_items[c.zone_b]
                
                line = QGraphicsLineItem(n1.pos().x(), n1.pos().y(), n2.pos().x(), n2.pos().y())
                line.setPen(pen)
                self.scene.addItem(line)
                self.edge_items.append(line)
                line.setZValue(-1)
                
    def add_area(self, area_name: Optional[str] = None):
        if not isinstance(area_name, str):
            name, ok = QInputDialog.getText(self, "Add Area", "Area Name:")
            if not ok or not name:
                return
        else:
            name = area_name
            
        name = name.strip()
        if name and name not in self.node_items:
            z = Zone(name=name, id=name, x=150.0, y=150.0)
            self.zones.append(z)
            node = NodeItem(z, self)
            node.setPos(z.x, z.y)
            self.scene.addItem(node)
            self.node_items[name] = node
            
            # Auto add a connection to every other node
            for other_z in self.zones:
                if other_z.name != name:
                    exists = any(
                        (c.zone_a == name and c.zone_b == other_z.name) or
                        (c.zone_a == other_z.name and c.zone_b == name)
                        for c in self.connections
                    )
                    if not exists:
                        self.connections.append(ZoneConnection(name, other_z.name, 5))
                        
            self.redraw_edges()
            
    def remove_selected(self):
        for item in self.scene.selectedItems():
            if isinstance(item, NodeItem):
                self.zones.remove(item.zone)
                self.scene.removeItem(item)
                del self.node_items[item.zone.name]
                self.connections = [c for c in self.connections if c.zone_a != item.zone.name and c.zone_b != item.zone.name]
        self.redraw_edges()
        
    def edit_node(self, node: NodeItem):
        dlg = ConnectionEditDialog(node.zone, self.zones, self.connections, self)
        if dlg.exec():
            new_name, new_conns = dlg.get_data()
            old_name = node.zone.name
            
            if new_name and new_name != old_name:
                node.zone.name = new_name
                node.zone.id = new_name
                node.update_text_pos()
                self.node_items[new_name] = node
                del self.node_items[old_name]
                
                for c in self.connections:
                    if c.zone_a == old_name: c.zone_a = new_name
                    if c.zone_b == old_name: c.zone_b = new_name
                    
            self.connections = [c for c in self.connections if c.zone_a != new_name and c.zone_b != new_name]
            self.connections.extend(new_conns)
            
            self.redraw_edges()
            
    def get_data(self) -> Tuple[List[Zone], List[ZoneConnection]]:
        return self.zones, self.connections
