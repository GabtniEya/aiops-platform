import os
import time

import psycopg
import redis
from fastapi import FastAPI, HTTPException

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aiops:aiops@localhost:5432/aiops")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

app = FastAPI()
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)

# Cette liste sert à "remplir" la mémoire volontairement
memoire_occupee = []


@app.get("/")
def accueil():
    return {"message": "Bonjour, mon application AIOps fonctionne !"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------- PANNES VOLONTAIRES ----------

@app.get("/chaos/cpu")
def chaos_cpu(secondes: int = 10):
    """Fait travailler le processeur à fond pendant X secondes."""
    fin = time.time() + secondes
    while time.time() < fin:
        _ = sum(i * i for i in range(10000))
    return {"chaos": "cpu", "duree": secondes}


@app.get("/chaos/memory")
def chaos_memory(mo: int = 100):
    """Consomme X Mo de mémoire (reste occupée jusqu'au reset)."""
    memoire_occupee.append(bytearray(mo * 1024 * 1024))
    return {"chaos": "memory", "ajoute_mo": mo, "blocs": len(memoire_occupee)}


@app.get("/chaos/memory/reset")
def chaos_memory_reset():
    """Libère la mémoire."""
    memoire_occupee.clear()
    return {"chaos": "memory", "etat": "libere"}


@app.get("/chaos/error500")
def chaos_error500():
    """Renvoie une erreur HTTP 500."""
    raise HTTPException(status_code=500, detail="Erreur simulée")


@app.get("/chaos/slow")
def chaos_slow(secondes: int = 5):
    """Simule une base de données très lente."""
    time.sleep(secondes)
    return {"chaos": "slow", "attente": secondes}
# ---------- BASE DE DONNÉES ET REDIS ----------

@app.get("/db")
def test_db():
    """Vérifie que PostgreSQL répond."""
    with (
        psycopg.connect(DATABASE_URL, connect_timeout=3) as conn,
        conn.cursor() as cur,
    ):
        cur.execute("SELECT now()")
        heure = cur.fetchone()[0]
    return {"db": "ok", "heure": str(heure)}


@app.get("/redis")
def test_redis():
    """Vérifie que Redis répond (et compte les appels)."""
    r = redis.Redis(host=REDIS_HOST, port=6379, socket_connect_timeout=3)
    compteur = r.incr("compteur")
    return {"redis": "ok", "compteur": compteur}