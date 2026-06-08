"""
Dialogo de desbloqueo por segundo factor (TOTP).
Aparece cuando se inserta un USB fuera del horario habitual.
Solo se cierra con un codigo TOTP valido o cancelando (deja bloqueado).
"""

import logging
from typing import List, Dict, Any, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout,
)
from PyQt6.QtCore import Qt

from security.totp import verify, is_configured
from analytics.prevention import unlock_device

logger = logging.getLogger(__name__)


class UnlockDialog(QDialog):
    """Pide un codigo TOTP para reactivar dispositivos bloqueados."""

    def __init__(self, blocks: List[Dict[str, Any]],
                 parent: Optional[object] = None) -> None:
        super().__init__(parent)
        self._blocks = blocks
        self.setWindowTitle("Dispositivo bloqueado — Segundo factor requerido")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        nombres = ", ".join(
            b.get("friendly_name") or b.get("serial", "?")
            for b in self._blocks)
        head = QLabel(
            "<b>Inserción de USB fuera del horario habitual</b>")
        head.setObjectName("alertTitle")
        layout.addWidget(head)

        info = QLabel(
            f"Se ha bloqueado: <b>{nombres}</b><br>"
            "Introduzca el código de su aplicación autenticadora "
            "para reactivar el dispositivo.")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Si ningun bloqueo se pudo aplicar fisicamente, avisar de que es logico
        if self._blocks and not any(b.get("physical") for b in self._blocks):
            logico = QLabel(
                "⚠ El bloqueo se ha registrado de forma lógica pero NO se ha "
                "deshabilitado el dispositivo en el sistema (se requieren "
                "privilegios de administrador).")
            logico.setObjectName("warnLabel")
            logico.setWordWrap(True)
            layout.addWidget(logico)

        if not is_configured():
            warn = QLabel("⚠ No hay TOTP configurado. Configúrelo en Ajustes.")
            warn.setObjectName("warnLabel")
            layout.addWidget(warn)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Código de 6 dígitos")
        self.code_input.setMaxLength(6)
        self.code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_input.returnPressed.connect(self._try_unlock)
        layout.addWidget(self.code_input)

        self.msg = QLabel("")
        self.msg.setObjectName("warnLabel")
        layout.addWidget(self.msg)

        btn_row = QHBoxLayout()
        self.btn_unlock = QPushButton("Desbloquear")
        self.btn_unlock.setObjectName("primaryButton")
        self.btn_unlock.clicked.connect(self._try_unlock)
        btn_cancel = QPushButton("Mantener bloqueado")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_unlock)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _try_unlock(self) -> None:
        code = self.code_input.text().strip()
        if not verify(code):
            self.msg.setText("Código incorrecto. Inténtelo de nuevo.")
            self.code_input.clear()
            self.code_input.setFocus()
            return
        from analytics.prevention import mark_unlocked
        for b in self._blocks:
            instance = b.get("instance")
            if instance:
                unlock_device(instance)
            # Recordar el desbloqueo para que el monitor no lo vuelva a bloquear
            mark_unlocked(b.get("serial"))
        logger.info("Dispositivos desbloqueados con TOTP: %d", len(self._blocks))
        self.accept()
