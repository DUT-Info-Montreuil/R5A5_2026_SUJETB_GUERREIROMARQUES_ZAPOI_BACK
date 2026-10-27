"""Accès à la table utilisateur (ORM : requêtes d'une ligne)."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import Utilisateur


def par_id(session: Session, id_utilisateur: int) -> Utilisateur | None:
    """Le compte d'identifiant donné, ou None."""
    return session.get(Utilisateur, id_utilisateur)


def par_email(session: Session, email: str) -> Utilisateur | None:
    """Le compte de cette adresse e-mail (déjà normalisée), ou None."""
    return session.scalars(select(Utilisateur).where(Utilisateur.email == email)).first()


def pseudo_existe(session: Session, pseudo: str) -> bool:
    """Vrai si ce pseudo est déjà pris."""
    return session.scalars(select(Utilisateur.id_utilisateur).where(Utilisateur.pseudo == pseudo)).first() is not None


def ajouter(session: Session, pseudo: str, email: str, mot_de_passe_hash: str) -> Utilisateur:
    """Crée un compte joueur avec l'empreinte de son mot de passe."""
    utilisateur = Utilisateur(pseudo=pseudo, email=email, mot_de_passe_hash=mot_de_passe_hash)
    session.add(utilisateur)
    # flush : PostgreSQL attribue l'identifiant sans attendre la fin de la transaction.
    session.flush()
    return utilisateur


def incrementer_version_jeton(session: Session, id_utilisateur: int, version_attendue: int) -> bool:
    """Passe version_jeton à la suivante, mais seulement si elle vaut encore `version_attendue`.

    La condition rend l'opération sûre quand deux déconnexions arrivent en même temps :
    une seule incrémente, l'autre voit que la version a déjà changé. Vrai si une ligne a changé.
    """
    resultat = session.execute(
        update(Utilisateur)
        .where(Utilisateur.id_utilisateur == id_utilisateur, Utilisateur.version_jeton == version_attendue)
        .values(version_jeton=Utilisateur.version_jeton + 1)
    )
    return resultat.rowcount == 1


def versions_des_jetons(session: Session, ids_utilisateurs: list[int]) -> dict[int, int]:
    """La version de jeton courante de chaque compte demandé (un compte supprimé est absent du résultat)."""
    if not ids_utilisateurs:
        return {}
    requete = select(Utilisateur.id_utilisateur, Utilisateur.version_jeton).where(
        Utilisateur.id_utilisateur.in_(ids_utilisateurs)
    )
    return {id_utilisateur: version for id_utilisateur, version in session.execute(requete)}


def sans_administrateurs(session: Session, ids_utilisateurs: list[int]) -> list[int]:
    """Ne garde que les joueurs ordinaires : un administrateur lit tous les espaces d'échange,
    la fin d'un accès de membre ne le concerne donc pas."""
    if not ids_utilisateurs:
        return []
    requete = select(Utilisateur.id_utilisateur).where(
        Utilisateur.id_utilisateur.in_(ids_utilisateurs), Utilisateur.est_administrateur.is_(False)
    )
    return list(session.scalars(requete))
