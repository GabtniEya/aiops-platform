"""Pipeline multi-agents (LangGraph) :
Diagnosis -> Knowledge -> Remediation -> Approbation humaine -> Exécution -> Validation
"""
import json
import os
import re
import subprocess
import time
from typing import Optional, TypedDict

from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import END, START, StateGraph

from detector import METRIQUES, detecter, lire_serie
from diagnostic import MODELE, collecter_contexte
from knowledge import context_for_prompt

load_dotenv()

CONTENEUR_BACKEND = "aiops-platform-backend-1"
ATTENTE_VALIDATION = 30  # secondes d'attente avant de re-mesurer la métrique

# Liste blanche : l'IA ne peut proposer QUE ces actions.
ACTIONS = {
    "redemarrer_backend": ["docker", "restart", CONTENEUR_BACKEND],
    "aucune": None,
}


class Etat(TypedDict, total=False):
    incident: dict
    contexte: dict
    diagnostic: str
    connaissances: str
    action: str
    raison: str
    approuve: bool
    resultat_action: str
    validation: str


def llm(prompt: str) -> str:
    cle = os.getenv("GROQ_API_KEY")
    if not cle:
        raise RuntimeError("GROQ_API_KEY est absente du fichier .env")
    rep = Groq(api_key=cle).chat.completions.create(
        model=MODELE,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return rep.choices[0].message.content


# ---------- Agent 1 : Diagnosis ----------
def agent_diagnosis(etat: Etat) -> Etat:
    print("\n[Agent Diagnosis] collecte du contexte et analyse...")
    contexte = collecter_contexte()
    prompt = f"""Tu es un ingénieur SRE. Réponds en français, de façon concise.

INCIDENT :
{json.dumps(etat['incident'], ensure_ascii=False, indent=2)}

CONTEXTE :
{json.dumps(contexte, ensure_ascii=False, indent=2)}

Donne : 1. Cause probable  2. Preuves (cite logs/métriques)  3. Confiance (%).
Si le contexte ne suffit pas, dis "Contexte insuffisant"."""
    diag = llm(prompt)
    print(diag)
    return {"contexte": contexte, "diagnostic": diag}


# ---------- Agent 2 : Knowledge (RAG) ----------
def agent_knowledge(etat: Etat) -> Etat:
    print("\n[Agent Knowledge] recherche de runbooks / incidents similaires...")
    inc = etat["incident"]
    requete = f"{inc.get('metrique')} {etat['diagnostic'][:600]}"
    try:
        connaissances = context_for_prompt(requete, exclude_id=inc.get("id"))
    except Exception as e:
        connaissances = f"[base de connaissances indisponible : {e}]"
    return {"connaissances": connaissances}


# ---------- Agent 3 : Remediation (propose, n'exécute pas) ----------
def agent_remediation(etat: Etat) -> Etat:
    print("\n[Agent Remediation] choix d'une action...")
    prompt = f"""Tu es un SRE prudent. À partir du diagnostic et des runbooks, choisis UNE action.

DIAGNOSTIC :
{etat['diagnostic']}

CONNAISSANCES :
{etat['connaissances']}

Actions autorisées (et seulement celles-ci) :
- "redemarrer_backend" : redémarre le conteneur backend (utile si le service est bloqué ou en fuite mémoire)
- "aucune" : ne rien faire (utile si la cause est un bug de code, un endpoint volontairement en erreur, ou si le contexte est insuffisant)

Réponds UNIQUEMENT avec un JSON : {{"action": "...", "raison": "..."}}"""
    brut = llm(prompt)
    action, raison = "aucune", "Réponse de l'IA illisible : par prudence, aucune action."
    m = re.search(r"\{.*\}", brut, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if data.get("action") in ACTIONS:
                action = data["action"]
                raison = str(data.get("raison", ""))
        except json.JSONDecodeError:
            pass
    print(f"Action proposée : {action}\nRaison : {raison}")
    return {"action": action, "raison": raison}


# ---------- Validation humaine ----------
def approbation_humaine(etat: Etat) -> Etat:
    if etat["action"] == "aucune":
        return {"approuve": False}
    print(f"\n⚠️  L'IA propose : {' '.join(ACTIONS[etat['action']])}")
    try:
        rep = input("Approuver cette action ? (o/n) : ").strip().lower()
    except EOFError:
        rep = "n"
    return {"approuve": rep in ("o", "oui", "y", "yes")}


def apres_approbation(etat: Etat) -> str:
    return "executer" if etat.get("approuve") else "fin"


# ---------- Exécution ----------
def executer(etat: Etat) -> Etat:
    args = ACTIONS[etat["action"]]
    print(f"\n[Exécution] {' '.join(args)}")
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=90)
        sortie = (r.stdout or r.stderr).strip()
    except Exception as e:
        sortie = f"[erreur] {e}"
    print(sortie)
    return {"resultat_action": sortie}


# ---------- Agent 5 : Validation ----------
def agent_validation(etat: Etat) -> Etat:
    nom = etat["incident"]["metrique"]
    print(f"\n[Agent Validation] attente de {ATTENTE_VALIDATION}s puis nouvelle mesure...")
    time.sleep(ATTENTE_VALIDATION)
    requete, plancher = METRIQUES[nom]
    try:
        res = detecter(lire_serie(requete), plancher)
    except Exception as e:
        return {"validation": f"Indéterminé (erreur de mesure : {e})"}
    if res is None:
        verdict = "Indéterminé (pas assez de données)"
    elif res["anomalie"]:
        verdict = f"❌ NON résolu : {nom} = {res['valeur']:.3f} (normale {res['mediane']:.3f})"
    else:
        verdict = f"✅ Résolu : {nom} = {res['valeur']:.3f}, retour à la normale"
    print(verdict)
    return {"validation": verdict}


def construire_graphe():
    g = StateGraph(Etat)
    g.add_node("diagnosis", agent_diagnosis)
    g.add_node("knowledge", agent_knowledge)
    g.add_node("remediation", agent_remediation)
    g.add_node("approbation", approbation_humaine)
    g.add_node("executer", executer)
    g.add_node("validation", agent_validation)

    g.add_edge(START, "diagnosis")
    g.add_edge("diagnosis", "knowledge")
    g.add_edge("knowledge", "remediation")
    g.add_edge("remediation", "approbation")
    g.add_conditional_edges("approbation", apres_approbation,
                            {"executer": "executer", "fin": END})
    g.add_edge("executer", "validation")
    g.add_edge("validation", END)
    return g.compile()


def traiter_incident(incident: dict) -> Etat:
    """Lance le pipeline et écrit les résultats dans le dict de l'incident."""
    final = construire_graphe().invoke({"incident": incident})
    incident["diagnostic"] = final.get("diagnostic", "")
    incident["action_proposee"] = final.get("action", "aucune")
    incident["raison_action"] = final.get("raison", "")
    incident["approuve"] = final.get("approuve", False)
    if final.get("validation"):
        incident["validation"] = final["validation"]
    return final


if __name__ == "__main__":
    # Test manuel sur le dernier incident enregistré
    with open("incidents.json", encoding="utf-8") as f:
        incidents = json.load(f)
    if not incidents:
        print("Aucun incident dans incidents.json")
    else:
        inc = incidents[-1]
        print(f"Traitement de {inc['id']} ({inc['metrique']})")
        traiter_incident(inc)
        with open("incidents.json", "w", encoding="utf-8") as f:
            json.dump(incidents, f, indent=2, ensure_ascii=False)