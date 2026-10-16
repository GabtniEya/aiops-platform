import json
import time
from datetime import datetime

from agents import traiter_incident
from detector import METRIQUES, detecter, lire_serie

try:
    from ml_detector import detecter_ml
except ImportError:  # scikit-learn absent : on garde seulement le z-score
    detecter_ml = None

INTERVALLE = 15  # secondes
FICHIER = "incidents.json"
actifs = {}  # métrique -> incident ouvert


def charger():
    try:
        with open(FICHIER, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def sauver(incidents):
    with open(FICHIER, "w", encoding="utf-8") as f:
        json.dump(incidents, f, indent=2, ensure_ascii=False)


def maintenant():
    return datetime.now().isoformat(timespec="seconds")


def verifier_ml(incidents):
    """Détection multi-métriques (Isolation Forest), en plus du z-score."""
    if detecter_ml is None:
        return
    try:
        res = detecter_ml()
    except Exception as e:
        print(f"[erreur] isolation forest: {e}")
        return
    if res is None:
        return

    if res["anomalie"] and "ml" not in actifs:
        if res["metrique"] in actifs:  # déjà couvert par le z-score
            return
        inc = {
            "id": f"INC-{len(incidents) + 1:04d}",
            "date": maintenant(),
            "metrique": res["metrique"],
            "valeur": round(res["valeur"], 3),
            "normale": round(res["mediane"], 3),
            "z": round(res["z"], 1),
            "detecteur": "isolation_forest",
            "score_ml": round(res["score"], 3),
            "z_par_metrique": res["z_par_metrique"],
            "statut": "OUVERT",
        }
        incidents.append(inc)
        actifs["ml"] = inc
        sauver(incidents)
        print(f"[{inc['date']}] 🤖 {inc['id']} anomalie multi-métriques "
              f"(Isolation Forest) : {res['z_par_metrique']}")
        try:
            traiter_incident(inc)
            sauver(incidents)
        except Exception as e:
            print(f"[pipeline indisponible] {e}")

    elif not res["anomalie"] and "ml" in actifs:
        inc = actifs.pop("ml")
        inc["statut"] = "RÉSOLU"
        inc["resolu_a"] = maintenant()
        sauver(incidents)
        print(f"[{inc['resolu_a']}] ✅ {inc['id']} résolu")


def boucle():
    incidents = charger()
    print("Surveillance démarrée (Ctrl+C pour arrêter)")
    while True:
        for nom, (requete, plancher) in METRIQUES.items():
            try:
                res = detecter(lire_serie(requete), plancher)
            except Exception as e:
                print(f"[erreur] {nom}: {e}")
                continue
            if res is None:
                continue

            if res["anomalie"] and nom not in actifs:
                inc = {
                    "id": f"INC-{len(incidents) + 1:04d}",
                    "date": maintenant(),
                    "metrique": nom,
                    "valeur": round(res["valeur"], 3),
                    "normale": round(res["mediane"], 3),
                    "z": round(res["z"], 1),
                    "statut": "OUVERT",
                }
                incidents.append(inc)
                actifs[nom] = inc
                sauver(incidents)
                print(f"[{inc['date']}] 🚨 {inc['id']} {nom} = {inc['valeur']}")

                # Pipeline multi-agents (diagnostic, connaissances, remédiation, validation)
                try:
                    traiter_incident(inc)
                    sauver(incidents)
                except Exception as e:
                    print(f"[pipeline indisponible] {e}")

            elif not res["anomalie"] and nom in actifs:
                inc = actifs.pop(nom)
                inc["statut"] = "RÉSOLU"
                inc["resolu_a"] = maintenant()
                sauver(incidents)
                print(f"[{inc['resolu_a']}] ✅ {inc['id']} résolu")

        verifier_ml(incidents)
        time.sleep(INTERVALLE)


if __name__ == "__main__":
    boucle()