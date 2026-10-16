import json
import os
import subprocess

from dotenv import load_dotenv
from groq import Groq

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


def diagnostiquer(incident, contexte):
    cle = os.getenv("GROQ_API_KEY")
    if not cle:
        return "Erreur : GROQ_API_KEY est absente du fichier .env"

    prompt = f"""Tu es un ingénieur SRE expert. Analyse cet incident et réponds en français.

INCIDENT :
{json.dumps(incident, ensure_ascii=False, indent=2)}

CONTEXTE :
{json.dumps(contexte, ensure_ascii=False, indent=2)}

 Si le contexte montre que Docker ou Kubernetes est inaccessible, ou ne contient aucune erreur liée à l'incident, réponds "Contexte insuffisant" au lieu de deviner.Réponds avec exactement ces sections :
1. Cause probable
2. Preuves (cite les lignes de logs ou métriques)
3. Action recommandée (une seule : redémarrer, augmenter les replicas, rollback, ou aucune)
4. Confiance (en %)
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