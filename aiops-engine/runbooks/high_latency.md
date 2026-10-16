# Runbook : latence élevée

## Symptômes
- Le temps de réponse p95 dépasse le seuil
- Peu ou pas d'erreurs 5xx

## Causes fréquentes
1. Saturation CPU / mémoire du pod
2. Trop de trafic pour le nombre de réplicas
3. Requêtes lentes vers la base de données

## Vérifications
- `kubectl top pods`
- Comparer le trafic actuel avec la normale

## Remédiation
- Augmenter les réplicas : `kubectl scale deployment/demo-app --replicas=3`
- À terme : configurer un HPA (autoscaling)
- Si CPU saturé en continu : revoir les limites de ressources
