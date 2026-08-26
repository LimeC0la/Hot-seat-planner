from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QFont, QBrush, QPen, QPolygonF
from PySide6.QtCore import Qt, QRectF, QPointF
from datetime import datetime, timedelta

def get_shift_bounds(now):
    if 7 <= now.hour < 19:
        start = now.replace(hour=7, minute=0, second=0, microsecond=0)
        end = now.replace(hour=19, minute=0, second=0, microsecond=0)
    elif now.hour >= 19:
        start = now.replace(hour=19, minute=0, second=0, microsecond=0)
        end = (now + timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
    else: # now.hour < 7
        start = (now - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        end = now.replace(hour=7, minute=0, second=0, microsecond=0)
    return start, end


class TimelineRulerWidget(QWidget):
    """
    Renders the unified 12-hour shift time ruler (07:00 -> 19:00) with tick marks.
    Designed to sit at the top of a multi-track Gantt timeline board.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        self.current_time = None

    def set_current_time(self, current_time):
        self.current_time = current_time
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = float(self.width())
        if width <= 10:
            painter.end()
            return
            
        now = self.current_time or datetime.now()
        min_time, max_time = get_shift_bounds(now)
        total_duration = (max_time - min_time).total_seconds()
        
        hour_font = QFont("Segoe UI", 8, QFont.Bold)
        painter.setFont(hour_font)
        
        num_hours = 12
        for i in range(num_hours + 1):
            hour_time = min_time + timedelta(hours=i)
            hour_sec = i * 3600.0
            x = (hour_sec / total_duration) * width
            x_pos = max(1.0, min(width - 1.0, x))
            
            # Bottom tick mark
            painter.setPen(QPen(QColor("#475569"), 1))
            painter.drawLine(QPointF(x_pos, 16), QPointF(x_pos, 23))
            
            # Clock hour label
            time_str = hour_time.strftime("%H:%M")
            painter.setPen(QColor("#94a3b8")) # slate-400
            
            if i == 0:
                rect_label = QRectF(x, 1, 45, 14)
                painter.drawText(rect_label, Qt.AlignLeft | Qt.AlignVCenter, time_str)
            elif i == num_hours:
                rect_label = QRectF(x - 45, 1, 45, 14)
                painter.drawText(rect_label, Qt.AlignRight | Qt.AlignVCenter, time_str)
            else:
                rect_label = QRectF(x - 22, 1, 44, 14)
                painter.drawText(rect_label, Qt.AlignCenter, time_str)
                
        # Current time red tick on ruler
        current_sec = (now - min_time).total_seconds()
        if 0 <= current_sec <= total_duration:
            marker_x = (current_sec / total_duration) * width
            poly = QPolygonF([
                QPointF(marker_x, 24),
                QPointF(marker_x - 4, 17),
                QPointF(marker_x + 4, 17),
            ])
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(poly)
            
        painter.end()


class TimelineTrackWidget(QWidget):
    """
    Compact Gantt track widget (height ~28px) without duplicate hour text labels.
    Aligns pixel-perfect with TimelineRulerWidget above it.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.segments = []
        self.current_time = None

    def set_segments(self, segments, current_time=None):
        self.segments = segments
        if current_time is not None:
            self.current_time = current_time
        self.update()

    def set_current_time(self, current_time):
        self.current_time = current_time
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = float(self.width())
        if width <= 10:
            painter.end()
            return
            
        track_y = 1.0
        track_h = float(self.height() - 2.0)
        track_rect = QRectF(0, track_y, width, track_h)
        
        # 1. Draw background track
        painter.setBrush(QBrush(QColor("#0f172a"))) # slate-950
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRoundedRect(track_rect, 4, 4)
        
        now = self.current_time or datetime.now()
        min_time, max_time = get_shift_bounds(now)
        total_duration = (max_time - min_time).total_seconds()
        
        # 2. Draw Hour Gridlines through track
        num_hours = 12
        for i in range(1, num_hours):
            hour_sec = i * 3600.0
            x = (hour_sec / total_duration) * width
            x_line = max(1.0, min(width - 1.0, x))
            painter.setPen(QPen(QColor("#1e293b"), 1, Qt.SolidLine))
            painter.drawLine(QPointF(x_line, track_y + 1), QPointF(x_line, track_y + track_h - 1))
            
        # 3. Draw Segments
        actual_font = QFont("Segoe UI", 9, QFont.Bold)
        planned_font = QFont("Segoe UI", 8, QFont.Normal)
        planned_font.setItalic(True)

        for s in self.segments:
            start_sec = (s['start'] - min_time).total_seconds()
            end_time = s['end'] if s['end'] else now
            end_sec = (end_time - min_time).total_seconds()
            
            x1 = (start_sec / total_duration) * width
            x2 = (end_sec / total_duration) * width
            
            x1 = max(0.0, min(width, x1))
            x2 = max(0.0, min(width, x2))
            
            if x2 <= x1:
                continue
                
            bar_width = max(x2 - x1, 4.0)
            rect = QRectF(x1, track_y + 1, bar_width, track_h - 2)
            
            is_planned = s.get('is_planned', False)
            base_color = QColor(s['color'])

            if is_planned:
                fill_color = QColor(base_color)
                fill_color.setAlpha(70)
                painter.setBrush(QBrush(fill_color))
                painter.setPen(QPen(base_color, 1.2, Qt.DashLine))
            else:
                painter.setBrush(QBrush(base_color))
                painter.setPen(Qt.NoPen)

            painter.drawRoundedRect(rect, 3, 3)
            
            if bar_width > 22:
                painter.setPen(QColor("#ffffff") if not is_planned else QColor("#e2e8f0"))
                painter.setFont(actual_font if not is_planned else planned_font)
                painter.drawText(rect, Qt.AlignCenter, s['label'])
                
        # 4. Draw Current Time Marker (Red Line & Pointer)
        current_sec = (now - min_time).total_seconds()
        if 0 <= current_sec <= total_duration:
            marker_x = (current_sec / total_duration) * width
            painter.setPen(QPen(QColor("#ef4444"), 2))
            painter.drawLine(QPointF(marker_x, track_y), QPointF(marker_x, track_y + track_h))
            
            poly = QPolygonF([
                QPointF(marker_x, track_y + 2),
                QPointF(marker_x - 3, track_y - 2),
                QPointF(marker_x + 3, track_y - 2),
            ])
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(poly)
            
        painter.end()


class TimelineWidget(QWidget):
    """
    Legacy standalone timeline widget with its own hour labels on top.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.segments = [] 
        self.current_time = None

    def set_segments(self, segments, current_time=None):
        self.segments = segments
        if current_time is not None:
            self.current_time = current_time
        self.update()

    def set_current_time(self, current_time):
        self.current_time = current_time
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = float(self.width())
        track_y = 18.0
        track_h = 30.0
        track_rect = QRectF(0, track_y, width, track_h)
        
        painter.setBrush(QBrush(QColor("#0f172a")))
        painter.setPen(QPen(QColor("#334155"), 1))
        painter.drawRoundedRect(track_rect, 6, 6)
        
        now = self.current_time or datetime.now()
        min_time, max_time = get_shift_bounds(now)
        total_duration = (max_time - min_time).total_seconds()
        
        hour_font = QFont("Segoe UI", 8)
        painter.setFont(hour_font)
        
        num_hours = 12
        for i in range(num_hours + 1):
            hour_time = min_time + timedelta(hours=i)
            hour_sec = i * 3600.0
            x = (hour_sec / total_duration) * width
            x_line = max(1.0, min(width - 1.0, x))
            
            if 0 < i < num_hours:
                painter.setPen(QPen(QColor("#1e293b"), 1, Qt.SolidLine))
                painter.drawLine(QPointF(x_line, track_y + 1), QPointF(x_line, track_y + track_h - 1))
                painter.setPen(QPen(QColor("#475569"), 1))
                painter.drawLine(QPointF(x_line, track_y - 3), QPointF(x_line, track_y))
            
            time_str = hour_time.strftime("%H:%M")
            painter.setPen(QColor("#94a3b8"))
            
            if i == 0:
                rect_label = QRectF(x, 1, 45, 14)
                painter.drawText(rect_label, Qt.AlignLeft | Qt.AlignVCenter, time_str)
            elif i == num_hours:
                rect_label = QRectF(x - 45, 1, 45, 14)
                painter.drawText(rect_label, Qt.AlignRight | Qt.AlignVCenter, time_str)
            else:
                rect_label = QRectF(x - 22, 1, 44, 14)
                painter.drawText(rect_label, Qt.AlignCenter, time_str)
        
        actual_font = QFont("Segoe UI", 9, QFont.Bold)
        planned_font = QFont("Segoe UI", 8, QFont.Normal)
        planned_font.setItalic(True)

        for s in self.segments:
            start_sec = (s['start'] - min_time).total_seconds()
            end_time = s['end'] if s['end'] else now
            end_sec = (end_time - min_time).total_seconds()
            
            x1 = (start_sec / total_duration) * width
            x2 = (end_sec / total_duration) * width
            x1 = max(0.0, min(width, x1))
            x2 = max(0.0, min(width, x2))
            
            if x2 <= x1:
                continue
                
            bar_width = max(x2 - x1, 4.0)
            rect = QRectF(x1, track_y + 2, bar_width, track_h - 4)
            
            is_planned = s.get('is_planned', False)
            base_color = QColor(s['color'])

            if is_planned:
                fill_color = QColor(base_color)
                fill_color.setAlpha(80)
                painter.setBrush(QBrush(fill_color))
                painter.setPen(QPen(base_color, 1.5, Qt.DashLine))
            else:
                painter.setBrush(QBrush(base_color))
                painter.setPen(Qt.NoPen)

            painter.drawRoundedRect(rect, 4, 4)
            
            if bar_width > 30:
                painter.setPen(QColor("#ffffff") if not is_planned else QColor("#e2e8f0"))
                painter.setFont(actual_font if not is_planned else planned_font)
                painter.drawText(rect, Qt.AlignCenter, s['label'])
                
        current_sec = (now - min_time).total_seconds()
        if 0 <= current_sec <= total_duration:
            marker_x = (current_sec / total_duration) * width
            painter.setPen(QPen(QColor("#ef4444"), 2))
            painter.drawLine(QPointF(marker_x, track_y - 2), QPointF(marker_x, track_y + track_h + 2))
            
            poly = QPolygonF([
                QPointF(marker_x, track_y - 1),
                QPointF(marker_x - 4, track_y - 6),
                QPointF(marker_x + 4, track_y - 6),
            ])
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(poly)
            
        painter.end()
