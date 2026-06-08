"""
Vista de ajustes: horario habitual, monitor en segundo plano y TOTP.
Permite configurar la franja horaria, dias laborables y el segundo factor.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTimeEdit, QCheckBox,
    QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit,
    QMessageBox, QScrollArea, QLineEdit,
)
from PyQt6.QtCore import QTime, Qt
from PyQt6.QtGui import QPixmap

from security.schedule import get_schedule, set_schedule
from security import totp
from store.anomaly_store import get_config, set_config

logger = logging.getLogger(__name__)

_DAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class HalfHourTimeEdit(QTimeEdit):
    """
    QTimeEdit cuyas flechas suben/bajan siempre 30 minutos, sin depender de
    la seccion (hora/minuto) seleccionada y con envoltura de medianoche.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDisplayFormat("HH:mm")
        self.setMinimumWidth(90)
        self.setWrapping(True)  # permite pasar de 23:30 a 00:00 y al reves

    def stepEnabled(self):
        # Habilita siempre ambas flechas, sin importar la seccion activa
        return (QTimeEdit.StepEnabledFlag.StepUpEnabled
                | QTimeEdit.StepEnabledFlag.StepDownEnabled)

    def stepBy(self, steps: int) -> None:
        self.setTime(self.time().addSecs(steps * 1800))


class SettingsView(QScrollArea):
    """
    Panel de configuración de horario, monitor y segundo factor.
    Es un area con scroll vertical: si la ventana es pequena, el usuario
    puede desplazarse con la rueda del raton para ver todo (incl. el TOTP).
    """

    def __init__(self, parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        content = QWidget()
        root = QVBoxLayout(content)
        root.setSpacing(12)
        root.setContentsMargins(12, 12, 12, 12)
        root.addWidget(self._schedule_group())
        root.addWidget(self._monitor_group())
        root.addWidget(self._totp_group())
        root.addStretch()
        self.setWidget(content)

    def _schedule_group(self) -> QGroupBox:
        box = QGroupBox("Horario habitual de uso")
        lay = QVBoxLayout(box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Desde:"))
        self.t_start = HalfHourTimeEdit()
        row.addWidget(self.t_start)
        row.addWidget(QLabel("Hasta:"))
        self.t_end = HalfHourTimeEdit()
        row.addWidget(self.t_end)
        row.addStretch()
        lay.addLayout(row)
        days_row = QHBoxLayout()
        self.day_checks = []
        for i, name in enumerate(_DAYS):
            c = QCheckBox(name[:3])
            self.day_checks.append(c)
            days_row.addWidget(c)
        days_row.addStretch()
        lay.addLayout(days_row)
        margin_row = QHBoxLayout()
        margin_row.addWidget(QLabel("Margen de tolerancia (horas):"))
        self.sp_margin = QDoubleSpinBox()
        self.sp_margin.setRange(0, 6)
        self.sp_margin.setSingleStep(0.5)
        self.sp_margin.setDecimals(1)
        self.sp_margin.setFixedWidth(80)
        margin_row.addWidget(self.sp_margin)
        margin_row.addStretch()
        lay.addLayout(margin_row)
        info = QLabel(
            "Se considera anómala una inserción que ocurra fuera del horario "
            "ampliado por el margen de tolerancia. En modo monitorización se "
            "genera una alerta; en modo estricto, además, el dispositivo se "
            "bloquea y requiere TOTP.")
        info.setWordWrap(True)
        lay.addWidget(info)
        btn_row = QHBoxLayout()
        self.btn_auto = QPushButton("Calcular desde mi actividad")
        self.btn_auto.setFixedHeight(34)
        self.btn_auto.clicked.connect(self._auto_schedule)
        btn = QPushButton("Guardar horario")
        btn.setObjectName("primaryButton")
        btn.setFixedHeight(34)
        btn.clicked.connect(self._save_schedule)
        btn_row.addWidget(self.btn_auto)
        btn_row.addWidget(btn)
        lay.addLayout(btn_row)
        return box

    def _monitor_group(self) -> QGroupBox:
        box = QGroupBox("Monitorización en segundo plano")
        lay = QHBoxLayout(box)
        lay.addWidget(QLabel("Intervalo (segundos):"))
        self.sp_interval = QSpinBox(); self.sp_interval.setRange(5, 3600)
        self.sp_interval.setFixedHeight(30)
        lay.addWidget(self.sp_interval)
        btn = QPushButton("Guardar intervalo")
        btn.setFixedHeight(34)
        btn.clicked.connect(self._save_interval)
        lay.addWidget(btn)
        lay.addStretch()
        return box

    def _totp_group(self) -> QGroupBox:
        box = QGroupBox("Segundo factor (TOTP)")
        lay = QVBoxLayout(box)
        self.totp_status = QLabel("")
        lay.addWidget(self.totp_status)

        # Bloque de configuracion (QR + enlace + verificacion). Se oculta
        # una vez el TOTP queda verificado.
        self.qr_label = QLabel()
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setFixedHeight(220)
        lay.addWidget(self.qr_label)

        self.uri_box = QPlainTextEdit(); self.uri_box.setReadOnly(True)
        self.uri_box.setFixedHeight(56)
        self.uri_box.setPlaceholderText(
            "Aquí aparecerá el enlace otpauth:// (alternativa al QR).")
        lay.addWidget(self.uri_box)

        verify_row = QHBoxLayout()
        verify_row.addWidget(QLabel("Código de verificación:"))
        self.code_input = QLineEdit()
        self.code_input.setMaxLength(6)
        self.code_input.setFixedWidth(110)
        self.code_input.setPlaceholderText("6 dígitos")
        self.code_input.returnPressed.connect(self._verify_totp)
        verify_row.addWidget(self.code_input)
        self.btn_verify = QPushButton("Verificar")
        self.btn_verify.setFixedHeight(30)
        self.btn_verify.clicked.connect(self._verify_totp)
        verify_row.addWidget(self.btn_verify)
        verify_row.addStretch()
        self.verify_row_widget = QWidget()
        self.verify_row_widget.setLayout(verify_row)
        lay.addWidget(self.verify_row_widget)

        self.btn_gen = QPushButton("Generar nuevo secreto TOTP")
        self.btn_gen.setObjectName("primaryButton")
        self.btn_gen.setFixedHeight(34)
        self.btn_gen.clicked.connect(self._gen_totp)
        lay.addWidget(self.btn_gen)
        return box

    def _load(self) -> None:
        sch = get_schedule()
        sh, sm = (sch["start"] or "08:00").split(":")
        eh, em = (sch["end"] or "22:00").split(":")
        self.t_start.setTime(QTime(int(sh), int(sm)))
        self.t_end.setTime(QTime(int(eh), int(em)))
        for i, c in enumerate(self.day_checks):
            c.setChecked(i in sch["days"])
        self.sp_margin.setValue(float(sch["margin_h"]))
        self.sp_interval.setValue(
            int(get_config("monitor.interval_s", "30") or "30"))
        self._refresh_totp()

    def _is_verified(self) -> bool:
        return (get_config("totp.verified", "false") or "").lower() == "true"

    def _set_config_block_visible(self, visible: bool) -> None:
        """Muestra u oculta el QR, el enlace y el campo de verificacion."""
        self.qr_label.setVisible(visible)
        self.uri_box.setVisible(visible)
        self.verify_row_widget.setVisible(visible)

    def _refresh_totp(self) -> None:
        # Estado 1: no hay secreto -> invitar a generarlo
        if not totp.is_configured():
            self.totp_status.setText("✗ TOTP no configurado.")
            self._set_config_block_visible(False)
            self.btn_gen.setText("Generar nuevo secreto TOTP")
            return
        # Estado 2: secreto verificado -> ocultar QR y mostrar solo el check
        if self._is_verified():
            self.totp_status.setText("✓ TOTP configurado y verificado.")
            self._set_config_block_visible(False)
            self.btn_gen.setText("Regenerar secreto TOTP")
            return
        # Estado 3: secreto generado pero pendiente de verificar -> mostrar QR
        self.totp_status.setText(
            "⚠ Escanee el QR e introduzca el código para verificar:")
        self._set_config_block_visible(True)
        self.btn_gen.setText("Regenerar secreto TOTP")
        uri = totp.get_provisioning_uri()
        self.uri_box.setPlainText(uri)
        png = totp.qr_png_bytes(uri)
        if png:
            pix = QPixmap(); pix.loadFromData(png, "PNG")
            self.qr_label.setPixmap(pix.scaled(
                200, 200, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        else:
            self.qr_label.setText("No se pudo generar el QR "
                                  "(instale 'qrcode'). Use el enlace de abajo.")

    def _save_schedule(self) -> None:
        days = [i for i, c in enumerate(self.day_checks) if c.isChecked()]
        set_schedule(
            self.t_start.time().toString("HH:mm"),
            self.t_end.time().toString("HH:mm"),
            days, margin_h=self.sp_margin.value())
        QMessageBox.information(self, "Ajustes", "Horario guardado.")

    def _auto_schedule(self) -> None:
        """Rellena la franja horaria a partir de la actividad observada."""
        from analytics.stats import compute_usual_schedule
        sch = compute_usual_schedule()
        if not sch["start"]:
            QMessageBox.warning(
                self, "Sin datos",
                "Todavía no hay suficiente actividad registrada. Inicie la "
                "monitorización y úsela un tiempo antes de calcular el horario.")
            return
        sh, sm = sch["start"].split(":")
        eh, em = sch["end"].split(":")
        self.t_start.setTime(QTime(int(sh), int(sm)))
        self.t_end.setTime(QTime(int(eh), int(em)))
        QMessageBox.information(
            self, "Horario calculado",
            f"Según su actividad, su franja "
            f"habitual es {sch['start']}–{sch['end']}.\n\n"
            "Revísela y pulse «Guardar horario» para aplicarla.")

    def _save_interval(self) -> None:
        set_config("monitor.interval_s", str(self.sp_interval.value()))
        QMessageBox.information(self, "Ajustes", "Intervalo guardado.")

    def _gen_totp(self) -> None:
        try:
            totp.generate_secret()
        except ImportError:
            QMessageBox.critical(
                self, "Falta dependencia",
                "El módulo 'pyotp' no está instalado en este intérprete de "
                "Python.\n\nInstálelo con:\n    pip install pyotp\n\n"
                "y vuelva a abrir la aplicación.")
            return
        # Un secreto nuevo siempre queda pendiente de verificar
        set_config("totp.verified", "false")
        self.code_input.clear()
        self._refresh_totp()
        QMessageBox.information(
            self, "TOTP",
            "Secreto generado. Escanee el QR en su app autenticadora "
            "(Google Authenticator, Authy...) e introduzca el código de "
            "6 dígitos para confirmar la configuración.")

    def _verify_totp(self) -> None:
        code = self.code_input.text().strip()
        if totp.verify(code):
            set_config("totp.verified", "true")
            self.code_input.clear()
            self._refresh_totp()
            QMessageBox.information(
                self, "TOTP",
                "Código correcto. El segundo factor ha quedado configurado.")
        else:
            QMessageBox.warning(
                self, "TOTP",
                "Código incorrecto. Compruebe que ha escaneado el QR y que la "
                "hora del dispositivo es correcta. Inténtelo de nuevo.")
            self.code_input.clear()
            self.code_input.setFocus()
