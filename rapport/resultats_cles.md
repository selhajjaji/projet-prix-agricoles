# Résultats clés

Chiffres produits par `scripts/generer_figures_rapport.py` à partir de `resultats/metriques.csv` et `resultats/previsions.csv`. MAE moyenne = moyenne non pondérée des MAE des horizons 1 mois, 3 mois, 6 mois.

## Modèle final (plus faible MAE moyenne de validation)

- Maïs-grain – Ontario : ETS / Holt-Winters
- Canola – Saskatchewan : ETS / Holt-Winters

## MAE moyenne – Validation (6 blocs, septembre 2014 à août 2020) ($/tonne)

| Série | Naïf (référence) | ETS / Holt-Winters | SARIMA |
| :--- | ---: | ---: | ---: |
| Maïs-grain – Ontario | 9,05 | 6,10 | 6,55 |
| Canola – Saskatchewan | 20,42 | 13,96 | 14,33 |

## MAE moyenne – Test global (septembre 2020 à août 2026) ($/tonne)

| Série | Naïf (référence) | ETS / Holt-Winters | SARIMA |
| :--- | ---: | ---: | ---: |
| Maïs-grain – Ontario | 23,99 | 21,77 | 21,17 |
| Canola – Saskatchewan | 86,76 | 82,34 | 83,15 |

## Alertes du modèle final – Test global (septembre 2020 à août 2026)

Prix observé hors de l'intervalle à 95 % de la prévision à 1 mois.

| Série | Modèle | Alertes | Au-dessus | En dessous | Test 1 | Test 2 | Test 3 |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Maïs-grain – Ontario | ETS / Holt-Winters | 2 | 1 | 1 | 1 | 1 | 0 |
| Canola – Saskatchewan | ETS / Holt-Winters | 26 | 16 | 10 | 17 | 8 | 1 |
