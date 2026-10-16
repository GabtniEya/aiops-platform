import json
import time
from datetime import datetime

from agents import traiter_incident
from detector import METRIQUES, detecter, lire_serie

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
        time.sleep(INTERVALLE)


if __name__ == "__main__":
    boucle()