# infrastructure/kubernetes

**What this is:** Deployment + Service manifests for all 6 services, each
with `/health` readiness and liveness probes (§5.5 Deployment readiness:
"Every service must have health checks... rollback, and runbooks").

## Files
One `<service>-deployment.yaml` per service in `services/`, each defining:
- a `Deployment` (2 replicas, resource requests/limits, `/health` probes)
- a matching `Service`

Secrets (DB credentials, model API keys) are injected via `memory-system-secrets`
— create it from `.env` using your platform's secret manager (§6.4 step 5),
never commit real values.

## Apply
```bash
kubectl create secret generic memory-system-secrets --from-env-file=.env
kubectl apply -f infrastructure/kubernetes/
```

## Rollback
```bash
kubectl rollout undo deployment/<service-name>
```
