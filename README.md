# Suivi et prévision des prix agricoles

Outil de suivi et de prévision des prix mensuels du maïs-grain en Ontario et du canola en Saskatchewan, à partir du tableau 32-10-0077-01 de Statistique Canada.
Il compare trois méthodes de prévision (naïf, ETS, SARIMA) et signale les prix observés qui sortent des intervalles de prévision.
Projet de session du cours INF-5103 (UQO) ; le protocole complet se trouve dans [docs/protocole.md](docs/protocole.md).

**Vidéo de démonstration (3 min) :** https://www.youtube.com/watch?v=Nvmkv8XyUXA


## Séries et découpage

Deux séries, de 1985-01 à 2026-08 (500 mois chacune, aucune valeur manquante) :

| Code | Produit | Province |
| :--- | :--- | :--- |
| `mais_ON` | Maïs-grain | Ontario |
| `canola_SK` | Canola (y compris le colza) | Saskatchewan |

Ce sont les principales provinces productrices ; les provinces voisines (Québec, Alberta) ont des marchés pratiquement jumeaux et ne sont pas retenues.

Découpage chronologique, défini par mois cibles (origine glissante, modèle réestimé à chaque origine) :

| Période | Mois cibles | Rôle |
| :--- | :--- | :--- |
| Entraînement | depuis 1985-01, fenêtre croissante jusqu'à chaque origine | estimation des modèles |
| `validation` | 6 blocs de 12 mois, de 2014-09 à 2020-08 | choix du modèle final |
| `test_1` | 2020-09 à 2022-08 | performances rapportées |
| `test_2` | 2022-09 à 2024-08 | performances rapportées |
| `test_3` | 2024-09 à 2026-08 | performances rapportées |
| `test_global` | 2020-09 à 2026-08 (72 mois, les trois tests réunis) | bilan, dans `metriques.csv` seulement |

Métriques par série, modèle, horizon et période : MAE, RMSE, MAPE, couverture des intervalles à 80 % et 95 %. Modèle final : plus faible MAE moyenne sur les horizons, calculée sur la validation uniquement (le naïf est retenu s'il est le meilleur). Détails et formules : [docs/protocole.md](docs/protocole.md).

## Fonctionnalités

L'application Streamlit est entièrement en français. Elle ne calcule aucun modèle : elle lit uniquement `data/series.csv` et les fichiers de `resultats/`.

- **Tableau de bord** (accueil) : date de la dernière donnée disponible et rappel du délai de publication ; une carte par série (dernier prix, variations sur 1 et 12 mois, indicateur d'alerte) ; résumé chiffré des alertes.
- **Historique** : prix depuis 1985, comparaison entre les deux séries, périodes de validation et de test ombrées, décomposition STL (tendance, saisonnalité, résidu) avec la série désaisonnalisée, profil saisonnier moyen, statistiques descriptives.
- **Prévision** : 5 dernières années prolongées par la prévision du modèle choisi et son intervalle (80 % ou 95 %), tableau des prévisions à 1, 3 et 6 mois, probabilité de dépasser le dernier prix observé, export CSV.
- **Alertes** : prix observés hors de l'intervalle à 95 % de la prévision à l'horizon 1, sur graphique et dans un tableau filtrable par série.
- **Comparaison des modèles** : MAE, RMSE et MAPE par horizon, couverture réelle des intervalles contre la couverture visée, MAE de chaque modèle par période de test (tableau et graphique), prévisions contre valeurs réelles sur la période choisie.
- **Méthodologie et limites** : source et licence des données, définition des séries et choix des provinces, prétraitement (contrôles, statistiques descriptives), découpage, métriques et leurs formules, règle du modèle final.

Un panneau latéral commun (produit, modèle, niveau d'intervalle ; la province de la série est affichée) conserve les choix d'une page à l'autre. Le modèle proposé par défaut est le modèle final de la série, selon la règle du protocole. Un bandeau d'avertissement s'affiche tant que les résultats sont factices (présence de `resultats/FACTICE.txt`) ; sinon, un bandeau d'information indique les modèles évalués et ceux qui ne sont pas encore disponibles. Les pages Alertes et Comparaison des modèles proposent les périodes test global (par défaut), test 1, test 2, test 3 et validation.

## Prérequis

- Windows
- **Python 3.12** (requis)

## Installation

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

Commande unique :

```bat
streamlit run app.py
```

## Chaîne complète

Depuis la racine du dépôt, avec l'environnement virtuel activé :

```bat
python scripts\preparer_donnees.py
python scripts\executer_evaluation.py
streamlit run app.py
```

1. `preparer_donnees.py` : `data/mais.csv` et `data/canola.csv` → `data/series.csv` (détails ci-dessous).
2. `executer_evaluation.py` : `data/series.csv` → les trois fichiers de `resultats/` (`previsions.csv`, `previsions_futures.csv`, `metriques.csv`).
3. `streamlit run app.py` : l'application lit `data/series.csv` et `resultats/`.

## Tests

```bat
python -m pytest
```

Les tests (`tests/`) vérifient le modèle naïf (ordre des bornes, élargissement avec le pas, absence de fuite d'information, entrées invalides), les deux séries, le découpage (périodes contiguës et disjointes, aucune prévision de validation dans un test, chaque prévision dans une seule période, `test_global` = union des trois tests), la conformité des fichiers de `resultats/` au contrat, les métriques par période et le choix du modèle final sur la validation. Ils n'écrivent aucun fichier.

## Ajouter un modèle

1. Dans `src/modeles/<modele>.py` (`ets.py` ou `sarima.py`), écrire la fonction `prevoir(historique, pas)` selon l'interface commune de `docs/protocole.md` :
   - `historique` : log des prix d'une série (`pd.Series`, index mensuel), connu jusqu'à l'origine seulement ;
   - `pas` : liste des nombres de pas après la dernière donnée (3, 5, 8) ;
   - retour : un `pd.DataFrame`, une ligne par pas, colonnes `pas, prevision, inf80, sup80, inf95, sup95`, en log.
   `src/modeles/naif.py` sert d'exemple.
2. Relancer l'évaluation : `python scripts\executer_evaluation.py` (ou `--modeles naif ets` pour choisir).
3. Relancer `python -m pytest`, puis `streamlit run app.py` : le nouveau modèle apparaît dans le panneau latéral et dans les comparaisons, et la règle du modèle final en tient compte.

## Régénérer les données et les résultats

Toutes les commandes se lancent depuis la racine du dépôt, avec l'environnement virtuel activé.

### 1. Données : `data/series.csv`

Chaîne de prétraitement :

```
data/mais.csv, data/canola.csv     fichiers sources extraits du tableau 32-10-0077-01 (versionnés)
        │
        ▼
notebooks/01_pretraitement.ipynb   prétraitement de référence : contrôles (calendrier, doublons,
        │                          valeurs manquantes), statistiques descriptives, graphiques ;
        │                          n'écrit aucun fichier
        ▼
scripts/preparer_donnees.py        garde mais_ON et canola_SK, vérifie et écrit le fichier commun
        │
        ▼
data/series.csv                    format long du contrat (docs/protocole.md)
        │
        ▼
scripts/executer_evaluation.py     validation, test_1, test_2, test_3 (origine glissante)
        │
        ▼
resultats/                         previsions.csv, previsions_futures.csv, metriques.csv
        │
        ▼
application Streamlit              lit uniquement data/series.csv et resultats/
```

Pour régénérer `data/series.csv`, exécuter :

```bat
python scripts\preparer_donnees.py
```

Le script garde les 2 séries (`mais_ON`, `canola_SK`) à partir de 1985-01 et affiche les vérifications : nombre de mois par série, valeurs manquantes, unité ($/tonne métrique), dates consécutives. Les deux séries retenues n'ont aucune valeur manquante : aucune valeur n'est estimée et la colonne `prix_impute` vaut False partout. Si une vérification échoue, `data/series.csv` n'est pas écrit. Le découpage chronologique utilisé par l'outil est celui de `src/config.py`.

### 2. Résultats : `resultats/`

Évaluation réelle des modèles, sur les six blocs de validation et les trois périodes de test (origine glissante, modèle réestimé à chaque origine) :

```bat
python scripts\executer_evaluation.py
python scripts\executer_evaluation.py --modeles naif
```

Le script exécute chaque modèle de `src/modeles/` dont la fonction `prevoir()` est écrite (interface commune de `docs/protocole.md`) et ignore les autres avec un message. Il écrit les trois fichiers de `resultats/` (colonne `periode` : validation, test_1, test_2 ou test_3 dans `previsions.csv`, plus test_global dans `metriques.csv`) et supprime `resultats/FACTICE.txt` si l'exécution réussit. Pour ajouter un modèle, il suffit d'écrire sa fonction `prevoir()` et de relancer le script.

**Outil de développement** : `scripts\generer_resultats_factices.py` génère des résultats aléatoires au format du contrat (validation, trois périodes de test et test_global, trois modèles), pour tester l'interface sans modèles réels. Il crée `resultats/FACTICE.txt`, qui déclenche le bandeau d'avertissement. Ces résultats n'ont aucune valeur d'analyse.

```bat
python scripts\generer_resultats_factices.py
```

Ce script refuse d'écraser des résultats réels (dossier sans `FACTICE.txt`), sauf avec l'option `--forcer`. Après l'avoir utilisé, relancer `executer_evaluation.py` pour revenir aux résultats réels.

## Structure du dépôt

```
app.py                          page d'accueil (tableau de bord)
pages/
  1_Historique.py
  2_Prevision.py
  3_Alertes.py
  4_Comparaison_modeles.py
  5_Methodologie_et_limites.py
src/
  config.py                     constantes du protocole (séries, horizons, dates, libellés)
  chargement.py                 lecture et validation de data/series.csv et de resultats/
  evaluation.py                 paires origine-cible, métriques par période, choix du modèle final
  interface_commune.py          panneau latéral, cache, graphiques, alertes
  modeles/                      naif.py, ets.py, sarima.py
scripts/
  preparer_donnees.py           data/mais.csv + data/canola.csv -> data/series.csv (reproduit le notebook)
  executer_evaluation.py        évaluation sur le découpage commun -> resultats/
  generer_resultats_factices.py résultats factices (outil de développement)
tests/                          test_naif.py, test_evaluation.py (pytest)
data/
  mais.csv, canola.csv          fichiers sources extraits de Statistique Canada
  series.csv                    séries au format long (généré)
resultats/                      previsions.csv, previsions_futures.csv, metriques.csv
docs/protocole.md               protocole et contrat des fichiers
notebooks/                      01_pretraitement.ipynb (prétraitement de référence)
rapport/figures/                figures du rapport
requirements.txt                dépendances (versions figées)
pytest.ini                      configuration des tests
.streamlit/config.toml          configuration de Streamlit (statistiques d'usage désactivées)
```

## Données

Statistique Canada, tableau 32-10-0077-01, *Prix des produits agricoles, mensuel*, diffusé sous la Licence du gouvernement ouvert – Canada.
