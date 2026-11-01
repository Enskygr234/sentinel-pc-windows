"""Premium koyu tema (mor/mavi vurgu)."""

PURPLE = "#8B5CF6"
BLUE = "#3B82F6"
CYAN = "#22D3EE"
GREEN = "#34D399"
AMBER = "#FBBF24"
RED = "#F87171"

BG = "#0B0B15"
SIDEBAR = "#10101C"
CARD = "#161626"
CARD2 = "#1D1D32"
BORDER = "#28283F"
TEXT = "#E8E8F2"
MUTED = "#9494B0"


def level_color(percent: float) -> str:
    if percent >= 90:
        return RED
    if percent >= 70:
        return AMBER
    return GREEN


QSS = f"""
* {{ font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif; font-size: 10pt; color: {TEXT}; }}
QMainWindow, QWidget#Root, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; }}
QWidget#Sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QLabel#Logo {{ font-size: 15pt; font-weight: 700; color: {PURPLE}; padding: 6px 8px; }}
QLabel#LogoSub {{ color: {MUTED}; font-size: 8.5pt; padding: 0 8px 10px 8px; }}
QPushButton#NavButton {{
    text-align: left; padding: 10px 14px; border: none; border-radius: 10px;
    background: transparent; color: {MUTED}; font-size: 10.5pt;
}}
QPushButton#NavButton:hover {{ background: {CARD2}; color: {TEXT}; }}
QPushButton#NavButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PURPLE}, stop:1 {BLUE});
    color: white; font-weight: 600;
}}
QLabel#PageTitle {{ font-size: 20pt; font-weight: 700; }}
QLabel#PageSubtitle, QLabel#Muted {{ color: {MUTED}; }}
QLabel#CardTitle {{ font-size: 11pt; font-weight: 600; }}
QLabel#BigValue {{ font-size: 20pt; font-weight: 700; }}
QLabel#Warn {{ color: {AMBER}; }}
QFrame#Card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 16px; }}
QPushButton {{ background: {CARD2}; border: 1px solid {BORDER}; border-radius: 9px; padding: 7px 14px; }}
QPushButton:hover {{ border-color: {PURPLE}; }}
QPushButton:disabled {{ color: {MUTED}; background: {CARD}; }}
QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PURPLE}, stop:1 {BLUE});
    color: white; border: none; font-weight: 600;
}}
QPushButton#Danger {{ color: {RED}; }}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
    background: #12121E; border: 1px solid {BORDER}; border-radius: 9px; padding: 6px 8px;
    selection-background-color: {PURPLE};
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {PURPLE}; }}
QComboBox QAbstractItemView {{ background: {CARD}; border: 1px solid {BORDER}; selection-background-color: #2D1F5C; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QTableWidget, QTreeWidget, QListWidget {{
    background: {CARD}; border: 1px solid {BORDER}; border-radius: 12px;
    alternate-background-color: {CARD2}; gridline-color: {BORDER};
}}
QTableWidget::item:selected, QTreeWidget::item:selected {{ background: #2D1F5C; color: {TEXT}; }}
QHeaderView::section {{
    background: {CARD2}; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px; font-weight: 600;
}}
QProgressBar {{ background: {CARD2}; border: none; border-radius: 5px; height: 10px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ border-radius: 5px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PURPLE}, stop:1 {BLUE}); }}
QCheckBox::indicator {{ width: 16px; height: 16px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {PURPLE}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QToolTip {{ background: {CARD}; color: {TEXT}; border: 1px solid {BORDER}; padding: 4px; }}
QStatusBar {{ background: {SIDEBAR}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QMenu {{ background: {CARD}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: #2D1F5C; }}
"""
