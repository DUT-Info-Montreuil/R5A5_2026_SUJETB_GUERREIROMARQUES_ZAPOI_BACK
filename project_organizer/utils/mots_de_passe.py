"""
Hachage des mots de passe avec argon2 (cours, « Hacher, pas chiffrer »).

La bibliothèque tire un sel aléatoire à chaque hachage et le range dans
l'empreinte, avec ses paramètres de coût : rien d'autre à stocker.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hacheur = PasswordHasher()

# Empreinte d'un mot de passe que personne ne connaît. Vérifiée quand l'e-mail
# est inconnu, pour que la réponse prenne le même temps que pour un compte
# existant : sinon la durée trahirait les adresses inscrites.
_EMPREINTE_LEURRE = _hacheur.hash("aucun-compte-ne-porte-ce-mot-de-passe")


def hacher(mot_de_passe: str) -> str:
    return _hacheur.hash(mot_de_passe)


def verifier(mot_de_passe: str, empreinte: str | None) -> bool:
    """Vrai si le mot de passe correspond. Sans empreinte (compte inconnu),
    vérifie le leurre puis répond faux."""
    if empreinte is None:
        _comparer(_EMPREINTE_LEURRE, mot_de_passe)
        return False
    return _comparer(empreinte, mot_de_passe)


def _comparer(empreinte: str, mot_de_passe: str) -> bool:
    try:
        return _hacheur.verify(empreinte, mot_de_passe)
    except (VerificationError, InvalidHashError):
        return False
