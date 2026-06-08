"""
Tema visual de la aplicacion: paleta blanco / negro / gris / azul.
Hoja de estilos Qt (QSS) aplicada a nivel de QApplication.
"""

# Paleta
AZUL        = "#1f6feb"
AZUL_OSCURO = "#1a5fd0"
AZUL_CLARO  = "#e8f0fe"
NEGRO       = "#1b1f24"
GRIS_FONDO  = "#f4f6f9"
GRIS_BORDE  = "#d0d7de"
GRIS_TEXTO  = "#57606a"
BLANCO      = "#ffffff"

STYLESHEET = f"""
QWidget {{
    background-color: {GRIS_FONDO};
    color: {NEGRO};
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
}}

QLabel#title {{
    color: {AZUL};
    font-size: 20px;
    font-weight: bold;
    padding: 6px;
}}
QLabel#alertTitle {{ color: {AZUL_OSCURO}; font-size: 15px; }}
QLabel#warnLabel {{ color: #c0392b; }}

QGroupBox {{
    background-color: {BLANCO};
    border: 1px solid {GRIS_BORDE};
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {AZUL};
}}

QPushButton {{
    background-color: {BLANCO};
    color: {NEGRO};
    border: 1px solid {GRIS_BORDE};
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{ border-color: {AZUL}; color: {AZUL}; }}
QPushButton:disabled {{ color: {GRIS_TEXTO}; background-color: {GRIS_FONDO}; }}

QPushButton#primaryButton {{
    background-color: {AZUL};
    color: {BLANCO};
    border: none;
    font-weight: bold;
}}
QPushButton#primaryButton:hover {{ background-color: {AZUL_OSCURO}; }}

/* Toggle de vista Basico/Experto: azul si activo, gris si no */
QPushButton#viewToggle {{
    background-color: {GRIS_BORDE};
    color: {GRIS_TEXTO};
    border: none;
    padding: 2px 8px;
    font-size: 12px;
}}
QPushButton#viewToggle:hover {{ color: {NEGRO}; }}
QPushButton#viewToggle:checked {{
    background-color: {AZUL};
    color: {BLANCO};
    font-weight: bold;
}}

QTabWidget::pane {{ border: 1px solid {GRIS_BORDE}; border-radius: 6px;
                    background: {BLANCO}; }}
QTabBar::tab {{
    background: {GRIS_FONDO};
    color: {GRIS_TEXTO};
    padding: 8px 18px;
    border: 1px solid {GRIS_BORDE};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {BLANCO};
    color: {AZUL};
    font-weight: bold;
    border-bottom: 2px solid {AZUL};
}}

QTableWidget {{
    background-color: {BLANCO};
    alternate-background-color: {AZUL_CLARO};
    gridline-color: {GRIS_BORDE};
    border: 1px solid {GRIS_BORDE};
    border-radius: 6px;
    selection-background-color: {AZUL};
    selection-color: {BLANCO};
}}
QHeaderView::section {{
    background-color: {NEGRO};
    color: {BLANCO};
    padding: 6px 10px;
    border: none;
    border-right: 1px solid {GRIS_BORDE};
    font-weight: bold;
}}

QLineEdit, QDateEdit, QTimeEdit, QComboBox, QSpinBox, QPlainTextEdit {{
    background-color: {BLANCO};
    border: 1px solid {GRIS_BORDE};
    border-radius: 5px;
    padding: 4px 6px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus {{ border: 1px solid {AZUL}; }}

QComboBox::drop-down {{ border: none; width: 22px; }}

QStatusBar {{ background-color: {NEGRO}; color: {BLANCO}; }}
QStatusBar QLabel {{ background: transparent; color: {BLANCO}; }}

QCheckBox::indicator:checked {{ background-color: {AZUL}; border: 1px solid {AZUL}; }}
QCheckBox::indicator {{ width: 15px; height: 15px; border: 1px solid {GRIS_BORDE};
                        border-radius: 3px; background: {BLANCO}; }}
"""


def apply_theme(app) -> None:
    """Aplica el tema a la QApplication."""
    app.setStyleSheet(STYLESHEET)
