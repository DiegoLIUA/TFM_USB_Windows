"""
Configuracion de pytest: añade la raiz del proyecto al path y proporciona
una base de datos temporal aislada para los tests que tocan SQLite.
"""

import sys
from pathlib import Path

import pytest

# Permite importar los paquetes del proyecto (acquisition, analytics, ...)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """Apunta la BD del proyecto a un fichero temporal e inicializa el esquema."""
    import store.database as database
    db_file = tmp_path / "test_tfm_usb.db"
    monkeypatch.setattr(database, "DB_PATH", db_file)
    database.initialize_database()
    return db_file
