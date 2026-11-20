"""Figures et tableaux du rapport, produits directement à partir de data/series.csv
et des fichiers de resultats/.

Le script lit seulement ; il écrit dans <sortie>/figures, <sortie>/tableaux et
<sortie>/resultats_cles.md (sortie = rapport/ par défaut).

- Figures PNG (300 dpi), sans titre : mêmes couleurs et tracés par modèle que
  l'application (src/interface_commune.py), complétés par des hachures et des
  marqueurs pour rester lisibles en noir et blanc.
- Tableaux LaTeX : contenu d'un environnement tabular (booktabs) seulement, sans
  environnement table ni légende ; nombres au format français.
- resultats_cles.md : chiffres clés, sans interprétation.

Utilisation :
    python scripts/generer_figures_rapport.py [--sortie DOSSIER]
"""

import argparse
from decimal import ROUND_HALF_UP, Decimal
import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402
from statsmodels.tsa.seasonal import STL  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Le module de l'interface déclare des fonctions mises en cache par Streamlit :
# hors de l'application, Streamlit signale l'absence de serveur, sans conséquence ici.
import streamlit  # noqa: E402, F401  (crée le journal de Streamlit avant d'en régler le niveau)

logging.getLogger("streamlit.runtime.caching.cache_data_api").setLevel(logging.ERROR)

from src import config  # noqa: E402
from src import interface_commune as ic  # noqa: E402
from src.chargement import charger_resultat, charger_series  # noqa: E402
from src.evaluation import choisir_modele_final, mae_moyenne  # noqa: E402

DPI = 300
FICHIER_FACTICE = config.DOSSIER_RESULTATS / "FACTICE.txt"
FICHIERS_VALIDATION_SARIMA = {
    serie: config.DOSSIER_RESULTATS / f"validation_sarima_{serie}.csv" for serie in config.LISTE_SERIES
}
FICHIER_VARIANTES_ETS = config.DOSSIER_RESULTATS / "ets_selection_revisee" / "classement_validation.csv"

# ---------------------------------------------------------------------------
# Style (couleurs et tracés de l'application, plus hachures et marqueurs)
# ---------------------------------------------------------------------------
TRACES_MPL = {"solid": "-", "dot": ":", "dash": "--", "dashdot": "-."}
STYLE_LIGNE_MODELES = {m: TRACES_MPL[t] for m, t in ic.TRACES_MODELES.items()}
MARQUEURS_MODELES = {"naif": "o", "ets": "s", "sarima": "^"}
HACHURES_MODELES = {"naif": "", "ets": "///", "sarima": "..."}

plt.rcParams.update({
    "font.size": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": "#E5E5E5",
    "grid.linewidth": 0.6,
    "legend.frameon": False,
    "hatch.linewidth": 0.6,
    "savefig.dpi": DPI,
    "savefig.bbox": "tight",
})

LIBELLES_VARIANTES_ETS = {
    "log_additif": "log, additif",
    "brut_additif": "brut, additif",
    "brut_multiplicatif": "brut, multiplicatif",
}
LIBELLES_CONFIGURATIONS_ETS = {
    "sans_tendance": "sans tendance",
    "tendance": "tendance",
    "tendance_amortie": "tendance amortie",
    "saisonnalite": "saisonnalité",
    "tendance_saisonnalite": "tendance + saisonnalité",
    "tendance_amortie_saisonnalite": "tendance amortie + saisonnalité",
}


# ---------------------------------------------------------------------------
# Mise en forme des nombres
# ---------------------------------------------------------------------------
def nombre_fr(valeur, decimales=2, milliers=" "):
    """1234.567 -> « 1 234,57 » (séparateur des milliers au choix).

    Arrondi au plus proche, les cas à égale distance vers le haut (41,955 -> 41,96),
    après élimination du bruit de la représentation binaire (arrondi à 9 décimales).
    """
    if pd.isna(valeur):
        return "--"
    arrondi = Decimal(repr(round(float(valeur), 9))).quantize(Decimal(1).scaleb(-decimales), ROUND_HALF_UP)
    texte = f"{arrondi:,.{decimales}f}"
    return texte.replace(",", "\x00").replace(".", ",").replace("\x00", milliers)


def nombre_tex(valeur, decimales=2):
    """Nombre au format français pour LaTeX (espace fine pour les milliers)."""
    return nombre_fr(valeur, decimales, milliers=r"\,")


def formateur_axe(decimales=0):
    """Formateur matplotlib à virgule décimale."""
    return FuncFormatter(lambda v, _: nombre_fr(v, decimales).replace("-", "−"))


def echapper_tex(texte):
    """Échappe les caractères spéciaux de LaTeX utilisés dans les libellés."""
    for caractere, remplacement in (("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                                    ("$", r"\$"), ("#", r"\#"), ("_", r"\_")):
        texte = texte.replace(caractere, remplacement)
    return texte.replace("–", "--")


def libelle_serie_tex(serie):
    return echapper_tex(ic.libelle_serie(serie))


def libelle_modele_tex(modele):
    return echapper_tex(ic.libelle_modele(modele))


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------
def enregistrer_figure(figure, dossier, nom, produits):
    chemin = dossier / nom
    figure.savefig(chemin, dpi=DPI, metadata={"Software": None})
    plt.close(figure)
    produits.append(chemin)


def ecrire_tabular(dossier, nom, colonnes, entete, lignes, produits):
    """Écrit le contenu d'un environnement tabular (booktabs).

    colonnes : spécification des colonnes (ex. « llrr ») ;
    entete : lignes d'en-tête déjà mises en forme (sans \\\\ final) ;
    lignes : listes de cellules, ou la chaîne « midrule » pour un filet.
    """
    contenu = [f"\\begin{{tabular}}{{{colonnes}}}", r"\toprule"]
    contenu += [f"{ligne} \\\\" if not ligne.startswith("\\cmidrule") else ligne for ligne in entete]
    contenu.append(r"\midrule")
    for ligne in lignes:
        contenu.append(r"\midrule" if ligne == "midrule" else " & ".join(ligne) + r" \\")
    contenu += [r"\bottomrule", r"\end{tabular}", ""]
    chemin = dossier / nom
    chemin.write_text("\n".join(contenu), encoding="utf-8")
    produits.append(chemin)


def grouper_par_serie(blocs):
    """Concatène des blocs de lignes en les séparant par un filet."""
    lignes = []
    for bloc in blocs:
        if lignes and bloc:
            lignes.append("midrule")
        lignes.extend(bloc)
    return lignes


# ---------------------------------------------------------------------------
# Données
# ---------------------------------------------------------------------------
def modeles_presents(metriques):
    presents = set(metriques["modele"])
    return [m for m in config.MODELES if m in presents]


def tableau_mae(metriques, serie, periode):
    """MAE par modèle (lignes) et horizon (colonnes) pour une série et une période."""
    choisies = metriques[(metriques["serie"] == serie) & (metriques["periode"] == periode)]
    return choisies.pivot(index="modele", columns="horizon", values="mae")


def decomposer(serie_prix):
    """Décomposition STL robuste, période de 12 mois (mêmes paramètres que
    pages/1_Historique.py), appliquée aux prix en dollars."""
    resultat = STL(serie_prix, period=12, robust=True).fit()
    return pd.DataFrame({
        "observe": serie_prix,
        "desaisonnalise": serie_prix - resultat.seasonal,
        "tendance": resultat.trend,
        "saisonnier": resultat.seasonal,
        "residu": resultat.resid,
    })


def serie_prix(series, serie):
    s = series[series["serie"] == serie]
    return pd.Series(s["prix"].to_numpy(), index=pd.DatetimeIndex(s["date"], freq="MS"))


# ---------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------
def ombrer_periodes(ax):
    """Blocs de validation (gris) et périodes de test (orange), comme dans l'application."""
    for numero, (debut, fin) in enumerate(config.PERIODES_VALIDATION):
        ax.axvspan(pd.Timestamp(debut), pd.Timestamp(fin) + pd.DateOffset(months=1), lw=0,
                   color=ic.COULEUR_VALIDATION, alpha=ic.OPACITES_VALIDATION[numero % 2], zorder=0)
    for numero, (debut, fin) in enumerate(config.PERIODES_TEST.values()):
        ax.axvspan(pd.Timestamp(debut), pd.Timestamp(fin) + pd.DateOffset(months=1), lw=0,
                   color=ic.COULEUR_TEST, alpha=ic.OPACITES_TEST[numero % 2], zorder=0)


def figure_series_prix(series, dossier, produits):
    figure, axes = plt.subplots(len(config.LISTE_SERIES), 1, figsize=(7.5, 5.2), sharex=True)
    for ax, serie in zip(axes, config.LISTE_SERIES):
        prix = serie_prix(series, serie)
        ombrer_periodes(ax)
        ax.plot(prix.index, prix.to_numpy(), color=ic.COULEUR_OBSERVE, lw=0.9, label="Prix observé")
        ax.set_ylabel(f"{ic.libelle_serie(serie)}\n({config.UNITE_PRIX})")
        ax.yaxis.set_major_formatter(formateur_axe())
        ax.set_xlim(prix.index.min(), prix.index.max() + pd.DateOffset(months=1))
    axes[-1].xaxis.set_major_locator(mdates.YearLocator(5))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[-1].set_xlabel("Mois")
    poignees = [
        plt.Line2D([], [], color=ic.COULEUR_OBSERVE, lw=0.9, label="Prix observé"),
        Patch(color=ic.COULEUR_VALIDATION, alpha=ic.OPACITES_VALIDATION[1],
              label=ic.libelle_periode(config.PERIODE_VALIDATION)),
        Patch(color=ic.COULEUR_TEST, alpha=ic.OPACITES_TEST[1],
              label=f"Test ({len(config.PERIODES_TEST)} périodes, "
                    f"{ic.formater_mois(config.DATE_DEBUT_TEST)} à {ic.formater_mois(config.DATE_FIN_TEST)})"),
    ]
    axes[0].legend(handles=poignees, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=7.5)
    figure.align_ylabels(axes)
    enregistrer_figure(figure, dossier, "series_prix.png", produits)


def figure_stl(series, serie, dossier, produits):
    d = decomposer(serie_prix(series, serie))
    panneaux = [("observe", "Observé et\ndésaisonnalisée"), ("tendance", "Tendance"),
                ("saisonnier", "Saisonnalité"), ("residu", "Résidu")]
    figure, axes = plt.subplots(len(panneaux), 1, figsize=(7.5, 7.0), sharex=True,
                                gridspec_kw={"height_ratios": [2, 1.2, 1, 1]})
    for ax, (colonne, nom) in zip(axes, panneaux):
        if colonne == "observe":
            ax.plot(d.index, d["observe"], color=ic.COULEUR_OBSERVE, lw=0.9, label="Observé")
            ax.plot(d.index, d["desaisonnalise"], color=ic.COULEUR_DESAISONNALISEE, lw=0.9, ls="--",
                    label="Désaisonnalisée (observé − saisonnalité)")
            ax.legend(loc="upper left", fontsize=7.5)
        else:
            ax.plot(d.index, d[colonne], color="#0072B2", lw=0.9)
            if colonne in ("saisonnier", "residu"):
                ax.axhline(0, color="#999999", lw=0.6)
        ax.set_ylabel(f"{nom}\n({config.UNITE_PRIX})")
        ax.yaxis.set_major_formatter(formateur_axe())
    axes[-1].xaxis.set_major_locator(mdates.YearLocator(5))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[-1].set_xlim(d.index.min(), d.index.max())
    axes[-1].set_xlabel("Mois")
    figure.align_ylabels(axes)
    enregistrer_figure(figure, dossier, f"stl_{serie}.png", produits)


def figure_profil(series, serie, dossier, produits):
    """Profil saisonnier moyen sur toute la période : prix moyen et écart moyen à la
    moyenne de l'année, par mois de l'année (les deux mesures de l'application)."""
    s = series[series["serie"] == serie].copy()
    s["mois"] = s["date"].dt.month
    s["ecart"] = s["prix"] / s.groupby(s["date"].dt.year)["prix"].transform("mean") * 100 - 100
    profil = s.groupby("mois")[["prix", "ecart"]].mean().reindex(range(1, 13))
    figure, axes = plt.subplots(1, 2, figsize=(7.5, 2.8))
    x = np.arange(12)
    mesures = [("prix", f"Prix moyen ({config.UNITE_PRIX})", 0),
               ("ecart", "Écart moyen à la moyenne\nde l'année (%)", 1)]
    for ax, (colonne, libelle, decimales) in zip(axes, mesures):
        ax.bar(x, profil[colonne].to_numpy(), color="#999999", edgecolor="#000000", lw=0.5)
        ax.set_xticks(x, ic.MOIS_COURTS_FR, rotation=90)
        ax.set_ylabel(libelle)
        ax.yaxis.set_major_formatter(formateur_axe(decimales))
        if colonne == "ecart":
            ax.axhline(0, color="#000000", lw=0.6)
    axes[0].set_ylim(bottom=0)
    figure.tight_layout()
    enregistrer_figure(figure, dossier, f"profil_{serie}.png", produits)


def barres_groupees(ax, categories, valeurs_par_modele, modeles):
    """Barres groupées par catégorie, une couleur et une hachure par modèle."""
    x = np.arange(len(categories))
    largeur = 0.8 / len(modeles)
    for rang, modele in enumerate(modeles):
        ax.bar(x + (rang - (len(modeles) - 1) / 2) * largeur, valeurs_par_modele[modele], largeur,
               color=ic.COULEURS_MODELES[modele], hatch=HACHURES_MODELES[modele],
               edgecolor="#000000", lw=0.5, label=ic.libelle_modele(modele))
    ax.set_xticks(x, categories)


def figure_mae_periodes(metriques, dossier, produits):
    modeles = modeles_presents(metriques)
    periodes = list(config.PERIODES_TEST) + [config.PERIODE_TEST_GLOBAL]
    figure, axes = plt.subplots(1, len(config.LISTE_SERIES), figsize=(7.5, 3.2))
    for ax, serie in zip(axes, config.LISTE_SERIES):
        valeurs = {m: [mae_moyenne(metriques, serie, p).get(m, np.nan) for p in periodes] for m in modeles}
        barres_groupees(ax, [ic.libelle_periode(p, avec_dates=False) for p in periodes], valeurs, modeles)
        ax.set_xlabel(ic.libelle_serie(serie))
        ax.set_ylabel(f"MAE moyenne sur les horizons ({config.UNITE_PRIX})")
        ax.yaxis.set_major_formatter(formateur_axe())
    poignees, libelles = axes[0].get_legend_handles_labels()
    figure.legend(poignees, libelles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(modeles))
    figure.tight_layout()
    enregistrer_figure(figure, dossier, "mae_periodes.png", produits)


def figure_couverture(metriques, dossier, produits):
    modeles = modeles_presents(metriques)
    niveaux = [int(round(n * 100)) for n in config.NIVEAUX_INTERVALLE]
    test = metriques[metriques["periode"] == config.PERIODE_TEST_GLOBAL]
    figure, axes = plt.subplots(len(config.LISTE_SERIES), len(niveaux), figsize=(7.5, 5.4),
                                sharey=True)
    for i, serie in enumerate(config.LISTE_SERIES):
        for j, niveau in enumerate(niveaux):
            ax = axes[i, j]
            t = test[test["serie"] == serie].pivot(index="modele", columns="horizon",
                                                   values=f"couverture{niveau}")
            valeurs = {m: [t.loc[m, h] * 100 for h in config.HORIZONS] for m in modeles}
            barres_groupees(ax, [config.LIBELLES_HORIZONS[h] for h in config.HORIZONS], valeurs, modeles)
            ax.axhline(niveau, color="#000000", lw=1.0, ls="--")
            ax.set_ylim(0, 100)
            ax.yaxis.set_major_formatter(PercentFormatter(decimals=0, symbol=" %"))
            ax.set_xlabel(f"{ic.libelle_serie(serie)} – intervalle à {niveau} % (horizon)")
            if j == 0:
                ax.set_ylabel("Couverture observée")
    poignees, libelles = axes[0, 0].get_legend_handles_labels()
    poignees.append(plt.Line2D([], [], color="#000000", lw=1.0, ls="--"))
    libelles.append("Niveau visé")
    figure.legend(poignees, libelles, loc="lower center", bbox_to_anchor=(0.5, 1.0),
                  ncol=len(poignees))
    figure.tight_layout()
    enregistrer_figure(figure, dossier, "couverture.png", produits)


def figure_alertes(previsions, alertes, serie, modele, dossier, produits):
    p = previsions[(previsions["serie"] == serie) & (previsions["modele"] == modele)
                   & (previsions["horizon"] == config.HORIZON_ALERTE)
                   & previsions["periode"].isin(config.COMPOSITION_PERIODES[config.PERIODE_TEST_GLOBAL])]
    p = p.sort_values("date_cible")
    a = alertes[alertes["serie"] == serie]
    couleur = ic.COULEURS_MODELES[modele]
    figure, ax = plt.subplots(figsize=(7.5, 3.4))
    ax.fill_between(p["date_cible"], p[ic.INF_ALERTE], p[ic.SUP_ALERTE], color=couleur, alpha=0.2,
                    lw=0, label=f"Intervalle à {ic.NIVEAU_ALERTE_PCT} % "
                                f"({ic.libelle_modele(modele)}, horizon {config.LIBELLES_HORIZONS[config.HORIZON_ALERTE]})")
    ax.plot(p["date_cible"], p["prevision"], color=couleur, lw=0.9, ls=STYLE_LIGNE_MODELES[modele],
            label=f"Prévision ({ic.libelle_modele(modele)})")
    ax.plot(p["date_cible"], p["reel"], color=ic.COULEUR_OBSERVE, lw=1.2, label="Prix observé")
    ax.scatter(a["date_cible"], a["reel"], marker="X", s=40, color=ic.COULEUR_ALERTE,
               edgecolor="#000000", lw=0.5, zorder=3, label=f"Alerte ({len(a)})")
    for debut, _ in list(config.PERIODES_TEST.values())[1:]:
        ax.axvline(pd.Timestamp(debut), color="#999999", lw=0.6, ls=":")
    ax.set_ylabel(f"Prix ({config.UNITE_PRIX})")
    ax.set_xlabel("Mois cible")
    ax.yaxis.set_major_formatter(formateur_axe())
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, fontsize=7.5)
    enregistrer_figure(figure, dossier, f"alertes_{serie}.png", produits)


# ---------------------------------------------------------------------------
# Tableaux
# ---------------------------------------------------------------------------
def tableau_comparaison(metriques, dossier, produits):
    modeles = modeles_presents(metriques)
    blocs = []
    for serie in config.LISTE_SERIES:
        validation = mae_moyenne(metriques, serie, config.PERIODE_VALIDATION)
        test = mae_moyenne(metriques, serie, config.PERIODE_TEST_GLOBAL)
        blocs.append([[libelle_serie_tex(serie) if rang == 0 else "", libelle_modele_tex(m),
                       nombre_tex(validation.get(m)), nombre_tex(test.get(m))]
                      for rang, m in enumerate(modeles)])
    entete = [rf"Série & Modèle & \multicolumn{{2}}{{c}}{{MAE moyenne ({echapper_tex(config.UNITE_PRIX)})}}",
              r"\cmidrule(lr){3-4}",
              "& & Validation & Test global"]
    ecrire_tabular(dossier, "comparaison.tex", "llrr", entete, grouper_par_serie(blocs), produits)


def tableau_detail(metriques, serie, dossier, produits):
    modeles = modeles_presents(metriques)
    periodes = config.PERIODES_METRIQUES
    m = metriques[metriques["serie"] == serie].set_index(["modele", "periode", "horizon"])
    blocs = []
    for modele in modeles:
        bloc = []
        for rang, h in enumerate(config.HORIZONS):
            ligne = [libelle_modele_tex(modele) if rang == 0 else "", config.LIBELLES_HORIZONS[h]]
            ligne += [nombre_tex(m.loc[(modele, p, h), "mae"]) for p in periodes]
            ligne += [nombre_tex(m.loc[(modele, config.PERIODE_TEST_GLOBAL, h), f"couverture{n}"] * 100, 1)
                      for n in (80, 95)]
            bloc.append(ligne)
        blocs.append(bloc)
    n_mae = len(periodes)
    entete = [
        rf"Modèle & Horizon & \multicolumn{{{n_mae}}}{{c}}{{MAE ({echapper_tex(config.UNITE_PRIX)})}} "
        rf"& \multicolumn{{2}}{{c}}{{Couverture, test global (\%)}}",
        rf"\cmidrule(lr){{3-{2 + n_mae}}} \cmidrule(lr){{{3 + n_mae}-{4 + n_mae}}}",
        "& & " + " & ".join(ic.libelle_periode(p, avec_dates=False) for p in periodes)
        + r" & 80\,\% & 95\,\%",
    ]
    ecrire_tabular(dossier, f"detail_{serie}.tex", "ll" + "r" * (n_mae + 2), entete,
                   grouper_par_serie(blocs), produits)


def tableau_rmse_mape(metriques, dossier, produits):
    modeles = modeles_presents(metriques)
    m = metriques[metriques["periode"] == config.PERIODE_TEST_GLOBAL].set_index(["serie", "modele", "horizon"])
    blocs = []
    for serie in config.LISTE_SERIES:
        bloc = []
        for rang, modele in enumerate(modeles):
            ligne = [libelle_serie_tex(serie) if rang == 0 else "", libelle_modele_tex(modele)]
            ligne += [nombre_tex(m.loc[(serie, modele, h), "rmse"]) for h in config.HORIZONS]
            ligne += [nombre_tex(m.loc[(serie, modele, h), "mape"]) for h in config.HORIZONS]
            bloc.append(ligne)
        blocs.append(bloc)
    nh = len(config.HORIZONS)
    horizons = " & ".join(config.LIBELLES_HORIZONS[h] for h in config.HORIZONS)
    entete = [
        rf"Série & Modèle & \multicolumn{{{nh}}}{{c}}{{RMSE ({echapper_tex(config.UNITE_PRIX)})}} "
        rf"& \multicolumn{{{nh}}}{{c}}{{MAPE (\%)}}",
        rf"\cmidrule(lr){{3-{2 + nh}}} \cmidrule(lr){{{3 + nh}-{2 + 2 * nh}}}",
        f"& & {horizons} & {horizons}",
    ]
    ecrire_tabular(dossier, "rmse_mape.tex", "ll" + "r" * (2 * nh), entete, grouper_par_serie(blocs), produits)


def tableau_modele_final(metriques, finaux, dossier, produits):
    modeles = modeles_presents(metriques)
    lignes = []
    for serie in config.LISTE_SERIES:
        validation = mae_moyenne(metriques, serie, config.PERIODE_VALIDATION)
        lignes.append([libelle_serie_tex(serie)] + [nombre_tex(validation.get(m)) for m in modeles]
                      + [libelle_modele_tex(finaux[serie])])
    entete = [
        rf"Série & \multicolumn{{{len(modeles)}}}{{c}}{{MAE moyenne de validation "
        rf"({echapper_tex(config.UNITE_PRIX)})}} & Modèle retenu",
        rf"\cmidrule(lr){{2-{1 + len(modeles)}}}",
        "& " + " & ".join(libelle_modele_tex(m) for m in modeles) + " &",
    ]
    ecrire_tabular(dossier, "modele_final.tex", "l" + "r" * len(modeles) + "l", entete, lignes, produits)


def tableau_alertes(alertes, dossier, produits):
    a = alertes.sort_values(["serie", "date_cible"], key=lambda c: c.map(
        {s: i for i, s in enumerate(config.LISTE_SERIES)}) if c.name == "serie" else c)
    blocs = []
    for serie in config.LISTE_SERIES:
        bloc = []
        for rang, ligne in enumerate(a[a["serie"] == serie].itertuples()):
            borne = "supérieure" if ligne.sens == "au-dessus" else "inférieure"
            bloc.append([libelle_serie_tex(serie) if rang == 0 else "", ic.formater_mois(ligne.date_cible),
                         nombre_tex(ligne.reel), f"{borne} : {nombre_tex(ligne.borne)}",
                         nombre_tex(abs(ligne.ecart_pct) * 100, 1), ligne.sens])
        blocs.append(bloc)
    u = echapper_tex(config.UNITE_PRIX)
    entete = [f"Série & Mois & Prix observé ({u}) & Borne franchie ({u}) & Écart à la borne (\\%) & Sens"]
    ecrire_tabular(dossier, "alertes.tex", "llrrrl", entete, grouper_par_serie(blocs), produits)


def tableau_candidats_sarima(dossier, produits):
    blocs = []
    for serie, chemin in FICHIERS_VALIDATION_SARIMA.items():
        v = pd.read_csv(chemin)
        # MAE de validation par horizon = moyenne des erreurs absolues sur les 72 mois
        # (moyenne des MAE des blocs pondérée par leur nombre de mois)
        v["somme"] = v["mae"] * v["n"]
        par_horizon = v.groupby(["ordre", "horizon"], sort=False)[["somme", "n"]].sum()
        mae = (par_horizon["somme"] / par_horizon["n"]).unstack("horizon")[config.HORIZONS]
        mae["moyenne"] = mae.mean(axis=1)
        blocs.append([[libelle_serie_tex(serie) if rang == 0 else "", echapper_tex(ordre)]
                      + [nombre_tex(mae.loc[ordre, h]) for h in config.HORIZONS]
                      + [nombre_tex(mae.loc[ordre, "moyenne"])]
                      for rang, ordre in enumerate(mae.index)])
    horizons = " & ".join(config.LIBELLES_HORIZONS[h] for h in config.HORIZONS)
    nh = len(config.HORIZONS)
    entete = [rf"Série & Candidat & \multicolumn{{{nh + 1}}}{{c}}{{MAE de validation "
              rf"({echapper_tex(config.UNITE_PRIX)})}}",
              rf"\cmidrule(lr){{3-{3 + nh}}}",
              f"& & {horizons} & Moyenne"]
    ecrire_tabular(dossier, "candidats_sarima.tex", "ll" + "r" * (nh + 1), entete,
                   grouper_par_serie(blocs), produits)


def tableau_variantes_ets(dossier, produits):
    c = pd.read_csv(FICHIER_VARIANTES_ETS)
    blocs = []
    for serie in config.LISTE_SERIES:
        s = c[c["serie"] == serie].sort_values("mae_moyenne", kind="stable")
        blocs.append([[libelle_serie_tex(serie) if rang == 0 else "",
                       LIBELLES_VARIANTES_ETS.get(r["variante"], echapper_tex(r["variante"])),
                       LIBELLES_CONFIGURATIONS_ETS.get(r["configuration"], echapper_tex(r["configuration"]))]
                      + [nombre_tex(r[str(h)]) for h in config.HORIZONS]
                      + [nombre_tex(r["mae_moyenne"])]
                      for rang, (_, r) in enumerate(s.iterrows())])
    horizons = " & ".join(config.LIBELLES_HORIZONS[h] for h in config.HORIZONS)
    nh = len(config.HORIZONS)
    entete = [rf"Série & Variante & Configuration & \multicolumn{{{nh + 1}}}{{c}}{{MAE de validation "
              rf"({echapper_tex(config.UNITE_PRIX)})}}",
              rf"\cmidrule(lr){{4-{4 + nh}}}",
              f"& & & {horizons} & Moyenne"]
    ecrire_tabular(dossier, "variantes_ets.tex", "lll" + "r" * (nh + 1), entete,
                   grouper_par_serie(blocs), produits)


# ---------------------------------------------------------------------------
# Chiffres clés
# ---------------------------------------------------------------------------
def ecrire_resultats_cles(metriques, finaux, alertes, chemin, produits):
    modeles = modeles_presents(metriques)
    u = config.UNITE_PRIX
    lignes = [
        "# Résultats clés",
        "",
        "Chiffres produits par `scripts/generer_figures_rapport.py` à partir de `resultats/metriques.csv` "
        "et `resultats/previsions.csv`. MAE moyenne = moyenne non pondérée des MAE des horizons "
        f"{', '.join(config.LIBELLES_HORIZONS[h] for h in config.HORIZONS)}.",
        "",
        "## Modèle final (plus faible MAE moyenne de validation)",
        "",
    ]
    lignes += [f"- {ic.libelle_serie(s)} : {ic.libelle_modele(finaux[s])}" for s in config.LISTE_SERIES]
    for periode in (config.PERIODE_VALIDATION, config.PERIODE_TEST_GLOBAL):
        lignes += ["", f"## MAE moyenne – {ic.libelle_periode(periode)} ({u})", "",
                   "| Série | " + " | ".join(ic.libelle_modele(m) for m in modeles) + " |",
                   "| :--- |" + " ---: |" * len(modeles)]
        for serie in config.LISTE_SERIES:
            moyennes = mae_moyenne(metriques, serie, periode)
            lignes.append(f"| {ic.libelle_serie(serie)} | "
                          + " | ".join(nombre_fr(moyennes.get(m)) for m in modeles) + " |")
    lignes += ["", f"## Alertes du modèle final – {ic.libelle_periode(config.PERIODE_TEST_GLOBAL)}", "",
               f"Prix observé hors de l'intervalle à {ic.NIVEAU_ALERTE_PCT} % de la prévision à "
               f"{config.LIBELLES_HORIZONS[config.HORIZON_ALERTE]}.", "",
               "| Série | Modèle | Alertes | Au-dessus | En dessous | " + " | ".join(
                   ic.libelle_periode(p, avec_dates=False) for p in config.PERIODES_TEST) + " |",
               "| :--- | :--- |" + " ---: |" * (3 + len(config.PERIODES_TEST))]
    for serie in config.LISTE_SERIES:
        a = alertes[alertes["serie"] == serie]
        par_periode = [int((a["periode"] == p).sum()) for p in config.PERIODES_TEST]
        lignes.append(f"| {ic.libelle_serie(serie)} | {ic.libelle_modele(finaux[serie])} | {len(a)} | "
                      f"{int((a['sens'] == 'au-dessus').sum())} | {int((a['sens'] == 'en dessous').sum())} | "
                      + " | ".join(str(n) for n in par_periode) + " |")
    lignes.append("")
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    produits.append(chemin)


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------
def generer(sortie):
    """Produit toutes les figures et tous les tableaux dans sortie ; retourne les chemins."""
    if FICHIER_FACTICE.exists():
        raise SystemExit("resultats/ contient des résultats factices (FACTICE.txt) : "
                         "relancer scripts/executer_evaluation.py avant de produire le rapport.")
    sortie = Path(sortie)
    dossier_figures = sortie / "figures"
    dossier_tableaux = sortie / "tableaux"
    dossier_figures.mkdir(parents=True, exist_ok=True)
    dossier_tableaux.mkdir(parents=True, exist_ok=True)

    series = charger_series()
    metriques = charger_resultat("metriques")
    previsions = charger_resultat("previsions")
    finaux = {serie: choisir_modele_final(metriques, serie) for serie in config.LISTE_SERIES}
    alertes = ic.calculer_alertes(previsions, finaux, config.PERIODE_TEST_GLOBAL)

    produits = []
    figure_series_prix(series, dossier_figures, produits)
    for serie in config.LISTE_SERIES:
        figure_stl(series, serie, dossier_figures, produits)
        figure_profil(series, serie, dossier_figures, produits)
    figure_mae_periodes(metriques, dossier_figures, produits)
    figure_couverture(metriques, dossier_figures, produits)
    for serie in config.LISTE_SERIES:
        figure_alertes(previsions, alertes, serie, finaux[serie], dossier_figures, produits)

    tableau_comparaison(metriques, dossier_tableaux, produits)
    for serie in config.LISTE_SERIES:
        tableau_detail(metriques, serie, dossier_tableaux, produits)
    tableau_rmse_mape(metriques, dossier_tableaux, produits)
    tableau_modele_final(metriques, finaux, dossier_tableaux, produits)
    tableau_alertes(alertes, dossier_tableaux, produits)
    if all(chemin.exists() for chemin in FICHIERS_VALIDATION_SARIMA.values()):
        tableau_candidats_sarima(dossier_tableaux, produits)
    if FICHIER_VARIANTES_ETS.exists():
        tableau_variantes_ets(dossier_tableaux, produits)

    ecrire_resultats_cles(metriques, finaux, alertes, sortie / "resultats_cles.md", produits)
    return produits


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sortie", type=Path, default=config.RACINE / "rapport",
                        help="dossier de sortie (figures/, tableaux/, resultats_cles.md) ; rapport/ par défaut")
    args = parser.parse_args()
    for chemin in generer(args.sortie):
        print(chemin)


if __name__ == "__main__":
    main()
