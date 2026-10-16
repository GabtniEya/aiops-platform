import os
import time

import numpy as np
import requests

# Adresse de Prometheus : variable d'environnement PROMETHEUS_URL,
# sinon celui de Docker Compose (port 9090)
PROMETHEUS = os.getenv("PROMETHEUS_URL", "http://127.0.0.1:9090")

# nom: (requête, plancher)
# plancher = en dessous, une variation n'est jamais une anomalie
METRIQUES = {
    "taux_erreur_pct": (
        '100 * (sum(rate(http_requests_total{status="5xx"}[1m])) or vector(0))'
        " / sum(rate(http_requests_total[1m]))",
        1.0,
    ),
    "latence_s": (
        "sum(rate(http_request_duration_seconds_sum[1m]))"
        " / sum(rate(http_request_duration_seconds_count[1m]))",
        0.2,
    ),
    "memoire_mo": ("max(process_resident_memory_bytes) / 1024 / 1024", 10.0),
}


def lire_serie(requete, minutes=60):
    """Lit l'historique d'une métrique dans Prometheus."""
    fin = time.time()
    debut = fin - minutes * 60
    r = requests.get(
        f"{PROMETHEUS}/api/v1/query_range",
        params={"query": requete, "start": debut, "end": fin, "step": 15},
        timeout=10,
    )
    r.raise_for_status()
    resultats = r.json()["data"]["result"]
    if not resultats:
        return []
    valeurs = [float(v[1]) for v in resultats[0]["values"]]
    return [v for v in valeurs if not np.isnan(v)]


def detecter(valeurs, plancher, seuil=3.0):
    """Z-score robuste (médiane + MAD) : insensible aux anciens pics."""
    if len(valeurs) < 10:
        return None
    historique = np.array(valeurs[:-1])
    derniere = valeurs[-1]
    mediane = float(np.median(historique))
    mad = float(np.median(np.abs(historique - mediane)))
    ecart = 1.4826 * mad if mad > 1e-9 else plancher / 3
    z = (derniere - mediane) / ecart
    anomalie = z > seuil and derniere > plancher
    return {"valeur": derniere, "mediane": mediane, "z": z, "anomalie": anomalie}


if __name__ == "__main__":
    for nom, (requete, plancher) in METRIQUES.items():
        valeurs = lire_serie(requete)
        resultat = detecter(valeurs, plancher)
        if resultat is None:
            print(f"{nom}: pas assez de données")
            continue
        etat = "ANOMALIE" if resultat["anomalie"] else "normal"
        print(
            f"{nom}: valeur={resultat['valeur']:.3f} "
            f"mediane={resultat['mediane']:.3f} z={resultat['z']:.1f} -> {etat}"
        )