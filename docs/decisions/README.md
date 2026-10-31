# Fiches de décision et rapport sur l'usage de l'IA

Tout est dans un seul document :
**[`dossier-decisions-et-rapport-ia.pdf`](dossier-decisions-et-rapport-ia.pdf)**

| # | Contenu | Page |
|---|---|---|
| 01 | Fiche de décision — Base de données | 2 |
| 02 | Fiche de décision — Mécanisme de temps réel | 3 |
| 03 | Fiche de décision — Format et destination de la journalisation | 5 |
| — | Rapport sur l'usage de l'IA | 6 |

Chaque fiche suit le même plan : **le problème, les options, ce qu'on a
choisi, ce que ça coûte.**

## Recompiler le PDF

La source est [`dossier-decisions-et-rapport-ia.tex`](dossier-decisions-et-rapport-ia.tex).
Il faut une distribution LaTeX avec le français (TeX Live ou MiKTeX) :

```bash
pdflatex dossier-decisions-et-rapport-ia.tex
pdflatex dossier-decisions-et-rapport-ia.tex   # une seconde fois pour le sommaire
```
