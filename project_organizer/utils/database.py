"""
Accès à la base de données.

Choix d'architecture : approche MIXTE.

  - L'ORM SQLAlchemy sert au CRUD courant (créer une équipe, renommer, lister).
    On y gagne en concision et en lisibilité.
  - Le SQL écrit à la main sert aux requêtes où l'ORM dessert la lisibilité :
    l'arbre du tournoi (jointures multiples sur la même table) et les
    vérifications de droits d'accès, qu'on veut pouvoir relire telles quelles.

La règle pour trancher : si la requête tient en une ligne d'ORM lisible, ORM.
Dès qu'il y a trois jointures ou une condition fine, SQL explicite dans
repository/.

Dans les deux cas, la session SQLAlchemy est le point d'entrée unique — on ne
mélange jamais deux mécanismes de connexion.
"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Classe mère de tous les modèles ORM.

    Les modèles (Utilisateur, Equipe, Rencontre...) viendront dans un module
    dédié. Ils décrivent des tables qui EXISTENT DÉJÀ : le script SQL reste la
    source de vérité du schéma, l'ORM ne le crée jamais.
    """


_engine: Engine | None = None
_FabriqueSession: sessionmaker[Session] | None = None


def initialiser(database_url: str) -> Engine:
    """Crée le moteur de connexion. Appelé une seule fois au démarrage."""
    global _engine, _FabriqueSession

    _engine = create_engine(
        database_url,
        # Vérifie que la connexion est vivante avant de la réutiliser.
        # Évite les erreurs après une coupure réseau ou un redémarrage du
        # conteneur PostgreSQL pendant le développement.
        pool_pre_ping=True,
        future=True,
    )
    _FabriqueSession = sessionmaker(
        bind=_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    return _engine


def moteur() -> Engine:
    if _engine is None:
        raise RuntimeError(
            "La base n'est pas initialisée. "
            "database.initialiser(...) doit être appelé au démarrage."
        )
    return _engine


@contextmanager
def session() -> Iterator[Session]:
    """Ouvre une session, valide à la sortie, annule en cas d'erreur.

    Toute écriture passe par ici. La transaction couvre l'intégralité du bloc :
    c'est indispensable pour les opérations en plusieurs étapes, comme la saisie
    d'un résultat (B-14), où l'on écrit le vainqueur, on élimine le perdant et
    on propage le gagnant dans l'arbre. Ces trois écritures réussissent ou
    échouent ensemble, jamais à moitié.
    """
    if _FabriqueSession is None:
        raise RuntimeError(
            "La base n'est pas initialisée. "
            "database.initialiser(...) doit être appelé au démarrage."
        )

    session_courante = _FabriqueSession()
    try:
        yield session_courante
        session_courante.commit()
    except Exception:
        session_courante.rollback()
        raise
    finally:
        session_courante.close()
