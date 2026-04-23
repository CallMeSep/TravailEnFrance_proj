# Micro Jobs App

Python microservice app with Docker and Postgres:

- `job-ingestion-service`: fetches jobs daily and upserts into Postgres.
- `job-api-service`: exposes jobs over REST API.
- `web-ui`: simple UI showing `intitule` and `description`.

## Quick Start (Minikube)

Run this full block from repository root:

```bash
minikube start --driver=docker
minikube addons enable ingress

eval "$(minikube -p minikube docker-env)"
docker build -t job-api-service:local ./services/job-api-service
docker build -t job-ingestion-service:local ./services/job-ingestion-service
docker build -t web-ui:local ./services/web-ui

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config/configmap.yaml
./scripts/apply-k8s-secret.sh
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/job-api-service/
kubectl apply -f k8s/job-ingestion-service/
kubectl apply -f k8s/web-ui/
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/security/

kubectl get pods -n travail-en-france
```

## Configure

Edit `.env` and set:

- `EXTERNAL_JOBS_API_URL` to your real jobs API endpoint.

## Run

```bash
docker compose up --build
```

## Run with Minikube (Kubernetes)

Start Minikube and enable ingress:

```bash
minikube start --driver=docker
minikube addons enable ingress
```

Build local images inside Minikube Docker daemon:

```bash
eval "$(minikube -p minikube docker-env)"
docker build -t job-api-service:local ./services/job-api-service
docker build -t job-ingestion-service:local ./services/job-ingestion-service
docker build -t web-ui:local ./services/web-ui
```

Apply manifests:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config/configmap.yaml
./scripts/apply-k8s-secret.sh
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/job-api-service/
kubectl apply -f k8s/job-ingestion-service/
kubectl apply -f k8s/web-ui/
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/security/
```

Check rollout:

```bash
kubectl get pods -n travail-en-france
kubectl get svc -n travail-en-france
kubectl get ingress -n travail-en-france
```

Check security resources (RBAC + NetworkPolicy):

```bash
kubectl get sa,role,rolebinding -n travail-en-france
kubectl get networkpolicy -n travail-en-france
```

Access UI:

```bash
minikube tunnel
```

Then open `http://travail.local` (map it in your hosts file to `127.0.0.1` if needed).

## Verification Checklist

Run these checks after deploy:

```bash
# App health
kubectl get pods -n travail-en-france
kubectl get deploy -n travail-en-france

# Data loaded
kubectl exec -n travail-en-france deploy/postgres -- \
psql -U jobsuser -d jobsdb -c "select count(*) as jobs_count from jobs;"

# Ingestion status
kubectl exec -n travail-en-france deploy/job-ingestion-service -- \
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"

# RBAC checks (expected: yes then no)
kubectl auth can-i get secrets/app-secret --as=system:serviceaccount:travail-en-france:web-ui-sa -n travail-en-france
kubectl auth can-i list pods --as=system:serviceaccount:travail-en-france:web-ui-sa -n travail-en-france
```

## URLs

### Docker Compose
- UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Ingestion health: `http://localhost:8080/health`

### Minikube
- UI via ingress: `http://travail.local`
- API quick test (port-forward): `kubectl port-forward -n travail-en-france svc/job-api-service 8000:8000`
- UI quick test (port-forward): `kubectl port-forward -n travail-en-france svc/web-ui 3000:3000`

## Notes

- Do not apply `k8s/config/secret.yaml` directly for real runs; use `./scripts/apply-k8s-secret.sh` so FT credentials are read from `.env`.
- Configure the external API URL in `.env` / `docker-compose.yml` with `EXTERNAL_JOBS_API_URL`.
- The ingestion service runs on startup and then daily using `CRON_SCHEDULE`.

## Troubleshooting

- `ImagePullBackOff` after Minikube restart:
  - Re-run local image build commands under `eval "$(minikube -p minikube docker-env)"`.
- UI shows `No jobs found yet...`:
  - Run `./scripts/apply-k8s-secret.sh`, restart ingestion deployment, and trigger `/run-now`.
- Ingress not reachable:
  - Verify `kubectl get pods -n ingress-nginx`, `kubectl get ingress -n travail-en-france`, and host mapping for `travail.local`.
