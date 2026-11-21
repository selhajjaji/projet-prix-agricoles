"""Test de scripts/generer_figures_rapport.py : exécution dans un dossier temporaire et
présence de toutes les figures et de tous les tableaux."""

import re
import subprocess
import sys

import pandas as pd
import pytest

from src import config

SCRIPT = config.RACINE / "scripts" / "generer_figures_rapport.py"

FIGURES = [
    "series_prix.png", "mae_periodes.png", "couverture.png",
    *[f"{prefixe}_{serie}.png" for serie in config.LISTE_SERIES for prefixe in ("stl", "profil", "alertes")],
]
TABLEAUX = [
    "comparaison.tex", "rmse_mape.tex", "modele_final.tex", "alertes.tex",
    *[f"detail_{serie}.tex" for serie in config.LISTE_SERIES],
]
TABLEAUX_VALIDATION = {
    "candidats_sarima.tex": [config.DOSSIER_RESULTATS / f"validation_sarima_{s}.csv" for s in config.LISTE_SERIES],
    "variantes_ets.tex": [config.DOSSIER_RESULTATS / "ets_selection_revisee" / "classement_validation.csv"],
}

pytestmark = pytest.mark.skipif(
    not (config.FICHIER_SERIES.exists() and config.FICHIER_METRIQUES.exists()
         and config.FICHIER_PREVISIONS.exists())
    or (config.DOSSIER_RESULTATS / "FACTICE.txt").exists(),
    reason="data/series.csv ou les résultats réels sont absents",
)


@pytest.fixture(scope="module")
def sortie(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("rapport")
    subprocess.run([sys.executable, str(SCRIPT), "--sortie", str(dossier)], check=True,
                   cwd=config.RACINE, capture_output=True, text=True)
    return dossier


def test_figures_produites(sortie):
    for nom in FIGURES:
        chemin = sortie / "figures" / nom
        assert chemin.exists() and chemin.stat().st_size > 0, nom
        assert chemin.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", nom


def test_tableaux_produits(sortie):
    attendus = TABLEAUX + [nom for nom, sources in TABLEAUX_VALIDATION.items()
                           if all(s.exists() for s in sources)]
    for nom in attendus:
        texte = (sortie / "tableaux" / nom).read_text(encoding="utf-8")
        # Contenu d'un tabular seulement : ni environnement table ni légende
        assert texte.startswith(r"\begin{tabular}") and texte.rstrip().endswith(r"\end{tabular}"), nom
        assert r"\toprule" in texte and r"\bottomrule" in texte, nom
        assert r"\begin{table}" not in texte and r"\caption" not in texte, nom
    assert (sortie / "resultats_cles.md").exists()


def test_comparaison_conforme_aux_metriques(sortie):
    """Les MAE moyennes de comparaison.tex correspondent à metriques.csv (arrondies à 2 décimales)."""
    metriques = pd.read_csv(config.FICHIER_METRIQUES)
    lignes = [ligne for ligne in (sortie / "tableaux" / "comparaison.tex").read_text(encoding="utf-8")
              .splitlines() if ligne.count("&") == 3 and re.search(r"\d,\d", ligne)]
    lus = [[float(c.strip(" \\").replace(r"\,", "").replace(",", ".")) for c in ligne.split("&")[2:]]
           for ligne in lignes]
    attendus = []
    for serie in config.LISTE_SERIES:
        m = metriques[metriques["serie"] == serie]
        moyennes = {p: m[m["periode"] == p].groupby("modele")["mae"].mean()
                    for p in (config.PERIODE_VALIDATION, config.PERIODE_TEST_GLOBAL)}
        attendus += [[moyennes[p][modele] for p in moyennes]
                     for modele in config.MODELES if modele in moyennes[config.PERIODE_VALIDATION]]
    assert len(lus) == len(attendus)
    for lu, attendu in zip(lus, attendus):
        assert lu == pytest.approx(attendu, abs=0.005 + 1e-9)
