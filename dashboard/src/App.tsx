import { useCallback, useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

const API = 'http://127.0.0.1:8100'

type Approbation = {
  etat: 'en_attente' | 'approuve' | 'refuse' | 'expire'
  action?: string
  commande?: string
  diagnostic?: string
  raison?: string
}

type Incident = {
  id: string
  date: string
  metrique: string
  valeur: number
  normale: number
  z: number
  statut: string
  diagnostic?: string | null
  action_proposee?: string | null
  raison_action?: string | null
  approuve?: boolean
  validation?: unknown
  resolu_a?: string | null
  detecteur?: string | null
  approbation?: Approbation | null
}

function App() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [erreur, setErreur] = useState<string | null>(null)
  const [envoi, setEnvoi] = useState<string | null>(null)

  const charger = useCallback(async () => {
    try {
      const rep = await fetch(`${API}/incidents`)
      if (!rep.ok) throw new Error(`Erreur HTTP ${rep.status}`)
      const donnees: Incident[] = await rep.json()
      donnees.sort((a, b) => b.date.localeCompare(a.date))
      setIncidents(donnees)
      setErreur(null)
    } catch (e) {
      setErreur(
        `Impossible de joindre l'API (${API}). Est-elle lancée ? ` +
          (e instanceof Error ? e.message : ''),
      )
    }
  }, [])

  useEffect(() => {
    charger()
    const minuteur = setInterval(charger, 3000)
    return () => clearInterval(minuteur)
  }, [charger])

  async function decider(id: string, approuve: boolean) {
    setEnvoi(id)
    try {
      const rep = await fetch(`${API}/incidents/${id}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approuve }),
      })
      if (!rep.ok) throw new Error(`Erreur HTTP ${rep.status}`)
      await charger()
    } catch (e) {
      setErreur(
        "La décision n'a pas pu être envoyée. " +
          (e instanceof Error ? e.message : ''),
      )
    } finally {
      setEnvoi(null)
    }
  }

  return (
    <div className="page">
      <h1>Plateforme AIOps</h1>
      <p className="sous-titre">
        Incidents détectés, du plus récent au plus ancien (mise à jour toutes
        les 3 secondes)
      </p>

      {erreur && <div className="erreur">{erreur}</div>}

      {incidents.length === 0 && !erreur && (
        <p className="vide">Aucun incident pour le moment.</p>
      )}

      {incidents.map((inc) => {
        const enAttente = inc.approbation?.etat === 'en_attente'
        const diag = inc.diagnostic || inc.approbation?.diagnostic
        const action = inc.action_proposee || inc.approbation?.action
        const raison = inc.raison_action || inc.approbation?.raison
        const resolu =
          inc.statut.toUpperCase() === 'RÉSOLU' ||
          inc.statut.toUpperCase() === 'RESOLU'
        return (
          <div className="carte" key={inc.id}>
            <div className="entete">
              <span className="id">{inc.id}</span>
              <span className={`badge ${resolu ? 'resolu' : 'ouvert'}`}>
                {resolu ? 'RÉSOLU' : 'OUVERT'}
              </span>
              <span className="date">{inc.date.replace('T', ' ')}</span>
            </div>

            <p className="chiffres">
              <strong>{inc.metrique}</strong> : {inc.valeur} (normale :{' '}
              {inc.normale}, z = {inc.z})
            </p>

            {diag ? (
              <details open={enAttente}>
                <summary>Diagnostic</summary>
                <div className="markdown">
                  <ReactMarkdown>{diag}</ReactMarkdown>
                </div>
              </details>
            ) : (
              <p className="vide">Pas de diagnostic pour cet incident.</p>
            )}

            {action && (
              <div className="action">
                <div>
                  Action proposée : <code>{action}</code>
                </div>
                {raison && <div>{raison}</div>}

                {inc.approbation && !enAttente && (
                  <div>État de l'approbation : {inc.approbation.etat}</div>
                )}

                {enAttente && (
                  <div className="boutons">
                    <button
                      className="approuver"
                      disabled={envoi === inc.id}
                      onClick={() => decider(inc.id, true)}
                    >
                      Approuver
                    </button>
                    <button
                      className="refuser"
                      disabled={envoi === inc.id}
                      onClick={() => decider(inc.id, false)}
                    >
                      Refuser
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

export default App