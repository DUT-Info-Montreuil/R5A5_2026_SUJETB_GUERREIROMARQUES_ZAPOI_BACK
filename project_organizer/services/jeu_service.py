"""Jeux : les postes proposés à la création d'une équipe."""

from ..models import RoleJeu
from ..repository import jeu_repository, role_repository
from ..utils import database
from ..utils.erreurs import NotFound


def postes_du_jeu(id_jeu: int) -> list[RoleJeu]:
    """Les postes d'un jeu ; 404 si le jeu n'existe pas."""
    with database.session() as session:
        if jeu_repository.par_id(session, id_jeu) is None:
            raise NotFound("Jeu introuvable.")
        return role_repository.du_jeu(session, id_jeu)
