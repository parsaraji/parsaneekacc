import os
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget
from PySide6.QtGui import QColor, QFontDatabase, QFont
from PySide6.QtCore import Qt

# Color Palette Constants (Soft Neumorphic Base)
COLOR_BG = "#E4E9F0"
COLOR_LIGHT_SHADOW = "#FFFFFF"
COLOR_DARK_SHADOW = "#B8C0CC"
COLOR_TEXT_PRIMARY = "#2C3E50"
COLOR_TEXT_SECONDARY = "#7F8C8D"
COLOR_ACCENT = "#2980B9"        # Soft blue/teal
COLOR_ACCENT_HOVER = "#3498DB"
COLOR_ACCENT_PRESSED = "#1B4F72"
COLOR_DANGER = "#E74C3C"        # Soft red/orange for debt/warning
COLOR_SUCCESS = "#2ECC71"
COLOR_CARD_BG = "#E4E9F0"
COLOR_INPUT_BG = "#E8EEF5"
COLOR_BORDER = "#D0D7DE"

GLOBAL_QSS = f"""
* {{
    font-family: 'Shabnam', 'Tahoma', 'Arial';
    color: {COLOR_TEXT_PRIMARY};
}}

QWidget {{
    background-color: {COLOR_BG};
}}

/* Main Window & Dialogs */
QMainWindow, QDialog {{
    background-color: {COLOR_BG};
}}

/* Neumorphic Push Buttons */
QPushButton {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_LIGHT_SHADOW};
    border-radius: 10px;
    padding: 8px 16px;
    font-weight: bold;
}}

QPushButton:hover {{
    background-color: #EAF0F8;
}}

QPushButton:pressed {{
    background-color: #D9E1EC;
    border: 1px solid {COLOR_DARK_SHADOW};
}}

QPushButton:disabled {{
    color: {COLOR_TEXT_SECONDARY};
    background-color: #ECEFF4;
}}

/* Primary Accent Buttons */
QPushButton[accent="true"] {{
    background-color: {COLOR_ACCENT};
    color: #FFFFFF;
    border: none;
}}

QPushButton[accent="true"]:hover {{
    background-color: {COLOR_ACCENT_HOVER};
}}

QPushButton[accent="true"]:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
}}

/* Danger Buttons */
QPushButton[danger="true"] {{
    background-color: {COLOR_DANGER};
    color: #FFFFFF;
    border: none;
}}

/* Inputs & Combo Boxes */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {{
    background-color: {COLOR_INPUT_BG};
    border: 1px solid {COLOR_DARK_SHADOW};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {COLOR_ACCENT};
    selection-color: #FFFFFF;
}}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
    border: 2px solid {COLOR_ACCENT};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top left;
    width: 20px;
    border-left-width: 0px;
}}

/* Tables & Grids - Flat, Clean, Performant */
QTableWidget, QTableView {{
    background-color: #FFFFFF;
    gridline-color: {COLOR_BORDER};
    border: 1px solid {COLOR_DARK_SHADOW};
    border-radius: 8px;
    selection-background-color: #D6EAF8;
    selection-color: {COLOR_TEXT_PRIMARY};
    alternate-background-color: #F8FAFC;
}}

QHeaderView::section {{
    background-color: #D9E2EC;
    color: {COLOR_TEXT_PRIMARY};
    font-weight: bold;
    padding: 6px;
    border: 1px solid {COLOR_BORDER};
}}

/* Tabs */
QTabWidget::pane {{
    border: 1px solid {COLOR_DARK_SHADOW};
    border-radius: 10px;
    background-color: {COLOR_BG};
}}

QTabBar::tab {{
    background-color: {COLOR_BG};
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 16px;
    margin-left: 2px;
}}

QTabBar::tab:selected {{
    background-color: {COLOR_ACCENT};
    color: #FFFFFF;
    font-weight: bold;
}}

/* Scrollbars */
QScrollBar:vertical {{
    background: {COLOR_BG};
    width: 10px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: {COLOR_DARK_SHADOW};
    min-height: 20px;
    border-radius: 5px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""

def load_fonts() -> bool:
    """Loads bundled Shabnam fonts into QFontDatabase."""
    fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")
    if not os.path.exists(fonts_dir):
        return False

    loaded_any = False
    for filename in os.listdir(fonts_dir):
        if filename.endswith(".ttf"):
            font_path = os.path.join(fonts_dir, filename)
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                loaded_any = True

    return loaded_any

def apply_theme(app: QApplication, font_family: str = "Shabnam") -> None:
    """Applies global QSS, font family, and RTL direction."""
    load_fonts()
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyleSheet(GLOBAL_QSS)

    font = QFont(font_family, 10)
    app.setFont(font)

def create_neumorphic_shadow(parent_widget: QWidget, is_pressed: bool = False) -> QGraphicsDropShadowEffect:
    """
    Creates dual neumorphic drop shadow effect for raised or pressed widgets.
    Qt allows one QGraphicsEffect per widget, so we apply dark shadow effect to widget
    with defined blur radius and offset.
    """
    shadow = QGraphicsDropShadowEffect(parent_widget)
    if is_pressed:
        shadow.setBlurRadius(8)
        shadow.setColor(QColor(184, 192, 204, 200)) # Dark top-left pressed feel
        shadow.setOffset(-2, -2)
    else:
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(184, 192, 204, 180)) # Dark bottom-right raised shadow
        shadow.setOffset(4, 4)
    return shadow
