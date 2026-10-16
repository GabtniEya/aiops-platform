"""Détection multi-métriques avec Isolation Forest.

Complète detector.py : le z-score juge chaque métrique seule, Isolation Forest
juge leur COMBINAISON (ex : latence un peu haute + erreurs + mémoire qui monte).
"""
import time

import numpy as np
import requests
from sklearn.ensemble import IsolationForest

from detector import METRIQUES, PROMETHEUS

PAS = 15            # secondes entre deux points
MIN_POINTS = 60     # minimum de points (15 min) pour entraîner le modèle
Z_MIN = 2.0         # au moins une métrique doit être nettement au-dessus de sa normale


def lire_matrice(minutes=60):
    """Lit toutes les métriques sur les MÊMES instants -> matrice (n_points, n_metriques)."""
    fin = int(time.time() // PAS * PAS)
    debut = fin - minutes * 60
    series = {}
    for nom, (requete, _) in METRIQUES.items():
        r = requests.get(
            f"{PROMETHEUS}/api/v1/query_range",
            params={"query": requete, "start": debut, "end": fin, "step": PAS},
            timeout=10,
        )
        r.raise_for_status()
        res = r.json()["data"]["result"]
        valeurs = {}
        if res:
            for t, v in res[0]["values"]:
                v = float(v)
                if not np.isnan(v):
                    valeurs[float(t)] = v
        series[nom] = valeurs

    instants = sorted(set.intersection(*(set(s) for s in series.values())))
    noms = list(METRIQUES)
    X = np.array([[series[n][t] for n in noms] for t in instants], dtype=float)
    return noms, X


def _echelle(historique):
    """Médiane et écart robuste (MAD) par métrique, avec le plancher de detector.py."""
    med = np.median(historique, axis=0)
    mad = np.median(np.abs(historique - med), axis=0)
    planchers = np.array([p for (_, p) in METRIQUES.values()])
    ecart = np.where(mad > 1e-9, 1.4826 * mad, planchers / 3)
    return med, ecart


def detecter_ml(contamination=0.02):
    """Retourne None (pas assez de données) ou un dict décrivant l'état actuel."""
    noms, X = lire_matrice()
    if len(X) < MIN_POINTS:
        return None

    historique, courant = X[:-1], X[-1]
    med, ecart = _echelle(historique)
    Z = (historique - med) / ecart
    z_courant = (courant - med) / ecart

    modele = IsolationForest(
        n_estimators=100, contamination=contamination, random_state=42
    ).fit(Z)
    score = float(modele.decision_function([z_courant])[0])  # < 0 : inhabituel
    inhabituel = modele.predict([z_courant])[0] == -1

    i = int(np.argmax(z_courant))  # métrique la plus déviante (à la hausse)
    anomalie = bool(inhabituel and z_courant[i] > Z_MIN)
    return {
        "anomalie": anomalie,
        "score": score,
        "metrique": noms[i],
        "valeur": float(courant[i]),
        "mediane": float(med[i]),
        "z": float(z_courant[i]),
        "z_par_metrique": {n: round(float(z), 1) for n, z in zip(noms, z_courant)},
    }


if __name__ == "__main__":
    res = detecter_ml()
    if res is None:
        print("Pas assez de données (il faut environ 15 minutes d'historique).")
    else:
        etat = "ANOMALIE" if res["anomalie"] else "normal"
        print(f"Isolation Forest : {etat} (score={res['score']:.3f})")
        print("z par métrique :", res["z_par_metrique"])