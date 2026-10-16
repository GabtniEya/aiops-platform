"""Base de connaissances (RAG) : runbooks + incidents passés dans Chroma."""
import json
from pathlib import Path

import chromadb

BASE_DIR = Path(__file__).parent
RUNBOOKS_DIR = BASE_DIR / "runbooks"
INCIDENTS_FILE = BASE_DIR / "incidents.json"
DB_DIR = BASE_DIR / "chroma_db"

_client = chromadb.PersistentClient(path=str(DB_DIR))
_collection = _client.get_or_create_collection("aiops_knowledge")


def index_runbooks() -> int:
    """Indexe chaque fichier .md du dossier runbooks/."""
    count = 0
    for path in RUNBOOKS_DIR.glob("*.md"):
        _collection.upsert(
            ids=[f"runbook:{path.stem}"],
            documents=[path.read_text(encoding="utf-8")],
            metadatas=[{"type": "runbook", "source": path.name, "incident_id": ""}],
        )
        count += 1
    return count


def index_incidents(exclude_id: str | None = None) -> int:
    """Indexe les incidents passés ayant déjà un diagnostic."""
    if not INCIDENTS_FILE.exists():
        return 0
    try:
        data = json.loads(INCIDENTS_FILE.read_text(encoding="utf-8") or "[]")
    except json.JSONDecodeError:
        return 0
    count = 0
    for inc in data:
        if inc.get("id") == exclude_id or not inc.get("diagnostic"):
            continue
        _collection.upsert(
            ids=[f"incident:{inc['id']}"],
            documents=[json.dumps(inc, ensure_ascii=False)],
            metadatas=[{"type": "incident", "source": "incidents.json",
                        "incident_id": inc["id"]}],
        )
        count += 1
    return count


def index_all(exclude_id: str | None = None) -> dict:
    return {"runbooks": index_runbooks(), "incidents": index_incidents(exclude_id)}


def search(query: str, n_results: int = 3, exclude_id: str | None = None) -> list[dict]:
    """Retourne les documents les plus proches de la requête."""
    total = _collection.count()
    if total == 0:
        return []
    res = _collection.query(query_texts=[query], n_results=min(n_results + 1, total))
    hits = [
        {"text": doc, "meta": meta, "distance": dist}
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
        if not (exclude_id and meta.get("incident_id") == exclude_id)
    ]
    return hits[:n_results]


def context_for_prompt(query: str, exclude_id: str | None = None, n_results: int = 3) -> str:
    """Texte prêt à être injecté dans le prompt du diagnostic."""
    index_all(exclude_id)  # garde la base à jour (rapide : upsert)
    hits = search(query, n_results, exclude_id)
    if not hits:
        return "Aucune connaissance similaire trouvée."
    blocs = [
        f"[{h['meta']['type']} - {h['meta']['source']}]\n{h['text'][:1500]}"
        for h in hits
    ]
    return "\n\n---\n\n".join(blocs)


if __name__ == "__main__":
    print("Indexation :", index_all())
    for hit in search("taux d'erreurs 500 élevé sur l'application"):
        print(round(hit["distance"], 3), hit["meta"]["source"])