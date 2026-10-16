"""API du dashboard AIOps : lit incidents.json et enregistre les décisions.
Elle n'exécute aucune commande : l'exécution reste dans agents.py."""
import json
import os
import time
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DOSSIER = Path(__file__).parent
FICHIER_INCIDENTS = DOSSIER / "incidents.json"
FICHIER_APPROBATIONS = DOSSIER / "approbations.json"

app = FastAPI(title="AIOps API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def lire_json(chemin, defaut):
    """Lit un fichier JSON (réessaie si le moniteur est en train de l'écrire)."""
    for _ in range(3):
        try:
            with open(chemin, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return defaut
        except json.JSONDecodeError:
            time.sleep(0.2)
    raise HTTPException(503, f"{chemin.name} est en cours d'écriture, réessaie")


def ecrire_json(chemin, donnees):
    """Écrit dans un fichier temporaire puis le remplace (évite un fichier à moitié écrit)."""
    tmp = chemin.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(donnees, f, indent=2, ensure_ascii=False)
    os.replace(tmp, chemin)


@app.get("/sante")
def sante():
    return {"ok": True}


@app.get("/incidents")
def liste_incidents():
    """Tous les incidents, du plus récent au plus ancien, avec leur approbation."""
    incidents = lire_json(FICHIER_INCIDENTS, [])
    approbations = lire_json(FICHIER_APPROBATIONS, {})
    for inc in incidents:
        inc["approbation"] = approbations.get(inc.get("id"))
    return list(reversed(incidents))


class Decision(BaseModel):
    approuve: bool


@app.post("/incidents/{incident_id}/decision")
def decider(incident_id: str, decision: Decision):
    """Enregistre approuver/refuser, seulement si une action est en attente."""
    approbations = lire_json(FICHIER_APPROBATIONS, {})
    entree = approbations.get(incident_id)
    if entree is None or entree.get("etat") != "en_attente":
        raise HTTPException(409, "Aucune action en attente pour cet incident")
    entree["etat"] = "approuve" if decision.approuve else "refuse"
    entree["decide_a"] = datetime.now().isoformat(timespec="seconds")
    approbations[incident_id] = entree
    ecrire_json(FICHIER_APPROBATIONS, approbations)
    return entree