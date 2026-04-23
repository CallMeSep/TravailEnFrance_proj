# Micro Jobs App

Python microservice app with Docker and Postgres:

- `job-ingestion-service`: fetches jobs daily and upserts into Postgres.
- `job-api-service`: exposes jobs over REST API.
- `web-ui`: simple UI showing `intitule` and `description`.

## Configure

Edit `.env` and set:

- `EXTERNAL_JOBS_API_URL` to your real jobs API endpoint.

## Run

```bash
docker compose up --build
```

## Run with Minikube (Kubernetes)

Use your Docker Hub images:
- `hoanghai4804/job-api-service:latest`
- `hoanghai4804/job-ingestion-service:latest`
- `hoanghai4804/web-ui:latest`

```bash
minikube start
minikube addons enable ingress

kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/config/
kubectl apply -f k8s/postgres/
kubectl apply -f k8s/job-api-service/
kubectl apply -f k8s/job-ingestion-service/
kubectl apply -f k8s/web-ui/
kubectl apply -f k8s/ingress.yaml
```

Check rollout:

```bash
kubectl get pods -n travail-en-france
kubectl get svc -n travail-en-france
kubectl get ingress -n travail-en-france
```

Access UI:

```bash
minikube tunnel
```

Then open `http://travail.local` (map it in your hosts file to `127.0.0.1` if needed).

## URLs

- UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Ingestion health: `http://localhost:8080/health` (inside container)

## Notes

- Configure the external API URL in `docker-compose.yml` with `EXTERNAL_JOBS_API_URL`.
- The ingestion service runs on startup and then daily using `CRON_SCHEDULE`.
# TravailEnFrance_proj
# TravailEnFrance_proj
