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

## URLs

- UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`
- Ingestion health: `http://localhost:8080/health` (inside container)

## Notes

- Configure the external API URL in `docker-compose.yml` with `EXTERNAL_JOBS_API_URL`.
- The ingestion service runs on startup and then daily using `CRON_SCHEDULE`.
# TravailEnFrance_proj
