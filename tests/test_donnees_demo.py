"""Le script de démonstration crée des comptes aux mots de passe connus de tous : il ne doit jamais tourner en production."""

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import text

from project_organizer.config import Config
from project_organizer.utils import database

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "donnees_demo.py"


def _charger_le_script():
    specification = importlib.util.spec_from_file_location("donnees_demo_sous_test", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_le_script_refuse_de_tourner_quand_le_cookie_est_securise(monkeypatch):
    """COOKIE_SECURE=true est le signe d'un déploiement HTTPS."""
    module = _charger_le_script()
    monkeypatch.setattr(Config, "COOKIE_SECURE", True)
    monkeypatch.setattr(sys, "argv", ["donnees_demo.py"])
    with database.session() as session:
        avant = session.execute(text("SELECT count(*) FROM utilisateur")).scalar_one()

    with pytest.raises(SystemExit) as sortie:
        module.main()

    assert "COOKIE_SECURE" in str(sortie.value)
    with database.session() as session:
        assert session.execute(text("SELECT count(*) FROM utilisateur")).scalar_one() == avant


def test_les_mots_de_passe_de_demonstration_respectent_la_politique_de_l_api():
    """Un compte de démonstration doit pouvoir se connecter : 12 caractères minimum (contrat §2)."""
    module = _charger_le_script()

    assert len(module.ADMIN["mot_de_passe"]) >= 12
    assert len(module.MOT_DE_PASSE_JOUEURS) >= 12
