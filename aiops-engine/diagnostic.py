import json
import os
import subprocess

from dotenv import load_dotenv
from groq import Groq

from knowledge import context_for_prompt

load_dotenv()
MODELE = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def commande(args):
    """Lance une commande et renvoie sa sortie (texte)."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).strip()
    except Exception as e:
        return f"[erreur] {e}"


def dernier_incident():
    with open("incidents.json", encoding="utf-8") as f:
        incidents = json.load(f)
    return incidents[-1] if incidents else None


def collecter_contexte():
    return {
        "logs_backend": commande(
            ["docker", "logs", "aiops-platform-backend-1", "--tail", "40"]
        )[-2500:],
        "conteneurs": commande(["docker", "ps", "--format", "{{.Names}} {{.Status}}"]),
        "pods_kubernetes": commande(["kubectl", "get", "pods", "-n", "aiops"]),
        "evenements_kubernetes": commande(
            ["kubectl", "get", "events", "-n", "aiops", "--sort-by=.lastTimestamp"]
        )[-1500:],
    }


def rechercher_connaissances(incident, contexte):
    """RAG : runbooks + incidents passés similaires (jamais bloquant)."""
    requete = (
        f"Incident sur la métrique {incident.get('metrique')} "
        f"valeur {incident.get('valeur')} (normale {incident.get('normale')}). "
        f"Logs : {contexte.get('logs_backend', '')[-600:]}"
    )
    try:
        return context_for_prompt(requete, exclude_id=incident.get("id"))
    except Exception as e:
        return f"[base de connaissances indisponible : {e}]"


def diagnostiquer(incident, contexte):
    cle = os.getenv("GROQ_API_KEY")
    if not cle:
        return "Erreur : GROQ_API_KEY est absente du fichier .env"

    connaissances = rechercher_connaissances(incident, contexte)

    prompt = f"""Tu es un ingénieur SRE expert. Analyse cet incident et réponds en français.

INCIDENT :
{json.dumps(incident, ensure_ascii=False, indent=2)}

CONTEXTE :
{json.dumps(contexte, ensure_ascii=False, indent=2)}

CONNAISSANCES (runbooks et incidents passés similaires) :
{connaissances}

Si le contexte montre que Docker ou Kubernetes est inaccessible, ou ne contient aucune erreur liée à l'incident, réponds "Contexte insuffisant" au lieu de deviner.
Appuie-toi sur les connaissances ci-dessus quand elles sont pertinentes, et cite le runbook ou l'incident passé utilisé.
Réponds avec exactement ces sections :
1. Cause probable
2. Preuves (cite les lignes de logs ou métriques)
3. Incident similaire / runbook utilisé (ou "aucun")
4. Action recommandée (une seule : redémarrer, augmenter les replicas, rollback, ou aucune)
5. Confiance (en %)
Si le contexte ne suffit pas pour conclure, dis-le clairement."""

    client = Groq(api_key=cle)
    reponse = client.chat.completions.create(
        model=MODELE,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return reponse.choices[0].message.content


if __name__ == "__main__":
    incident = dernier_incident()
    if incident is None:
        print("Aucun incident dans incidents.json")
    else:
        print(f"Analyse de {incident['id']} (modèle : {MODELE})...\n")
        print(diagnostiquer(incident, collecter_contexte()))