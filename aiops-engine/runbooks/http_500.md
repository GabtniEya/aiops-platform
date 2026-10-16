# Runbook : taux d'erreurs HTTP 500 élevé

## Symptômes
- Le taux de réponses 5xx dépasse le seuil normal
- Latence stable, mais requêtes en échec

## Causes fréquentes
1. Déploiement récent défectueux (bug applicatif)
2. Dépendance indisponible (base de données, API externe)
3. Variable d'environnement ou secret manquant

## Vérifications
- `kubectl logs deployment/demo-app --tail=100`
- `kubectl rollout history deployment/demo-app`
- Vérifier les variables d'environnement du pod

## Remédiation
- Si lié à un déploiement récent : `kubectl rollout undo deployment/demo-app`
- Si pod bloqué : `kubectl rollout restart deployment/demo-app`
- Si dépendance en panne : escalader à l'équipe concernée
