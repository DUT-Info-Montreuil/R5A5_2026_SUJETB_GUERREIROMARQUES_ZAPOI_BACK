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


def test_le_script_refuse_de_tourner_sur_une_base_avec_de_vrais_comptes(monkeypatch, inscrire):
    """Audit V-02 : dans Docker, le conteneur du script ne voit pas COOKIE_SECURE ; la base, elle, ne ment pas."""
    module = _charger_le_script()
    inscrire("vrai_joueur")
    monkeypatch.setattr(sys, "argv", ["donnees_demo.py"])
    with database.session() as session:
        avant = session.execute(text("SELECT count(*) FROM utilisateur")).scalar_one()

    with pytest.raises(SystemExit) as sortie:
        module.main()

    assert "--forcer" in str(sortie.value)
    with database.session() as session:
        assert session.execute(text("SELECT count(*) FROM utilisateur")).scalar_one() == avant


def test_les_comptes_de_demonstration_ne_comptent_pas_comme_de_vrais_comptes(inscrire):
    module = _charger_le_script()
    avant = module.comptes_hors_demonstration()

    inscrire("vrai_joueur")

    assert module.comptes_hors_demonstration() == avant + 1


def test_les_mots_de_passe_de_demonstration_respectent_la_politique_de_l_api():
    """Un compte de démonstration doit pouvoir se connecter : 12 caractères minimum (contrat §2)."""
    module = _charger_le_script()

    assert len(module.ADMIN["mot_de_passe"]) >= 12
    assert len(module.MOT_DE_PASSE_JOUEURS) >= 12


def test_les_postes_de_la_demonstration_sont_ceux_du_catalogue_de_jeux():
    """Le script et le catalogue SQL nomment les postes pareil : sinon une équipe aurait plus de postes que de joueurs."""
    module = _charger_le_script()

    with database.session() as session:
        lignes = session.execute(text(
            "SELECT j.nom_jeu, j.joueurs_par_equipe, r.libelle_role FROM jeu j JOIN role_jeu r USING (id_jeu)"
        )).all()
    en_base: dict[str, list[str]] = {}
    for nom, _, role in lignes:
        en_base.setdefault(nom, []).append(role)
    taille = {nom: k for nom, k, _ in lignes}

    presents = [nom for nom in module.JEUX if nom in en_base]
    if len(presents) < len(module.JEUX):
        pytest.skip(
            "Base créée avant le catalogue de douze jeux : la recréer avec « docker compose down -v && docker compose up -d »."
        )
    for nom, postes in module.JEUX.items():
        assert sorted(en_base[nom]) == sorted(postes), nom
        assert taille[nom] == len(postes), nom


def test_chaque_jeu_du_catalogue_a_autant_de_postes_que_de_joueurs_par_equipe():
    with database.session() as session:
        ecarts = session.execute(text(
            "SELECT j.nom_jeu FROM jeu j LEFT JOIN role_jeu r USING (id_jeu) "
            "GROUP BY j.id_jeu, j.joueurs_par_equipe HAVING count(r.id_role) <> j.joueurs_par_equipe AND j.nom_jeu NOT LIKE 'test\\_%'"
        )).scalars().all()

    assert ecarts == []
