# Integrations Microservice API

Handles integrating external services with our application framework. Manages the connections to these external services such as Gmail, Slack, etc., pipes messages to and from these external services, and handles sync jobs. All data persisted in database.

Project for COMS4153, Fall 2025 Cloud Team

## Live Link Hosted on Google Cloud Platform VM 

http://35.188.76.100:8000/docs

## Get Started

### Prerequisites
- Python 3.12+

1. Clone microservice
```bash
    $ git clone git@github.com:cloudteam4153/integrations-svc-ms2.git
    $ cd integrations-svc-ms2
```

2. Virtual environment
```bash
    $ python3.13 -m venv .venv
    $ source .venv/bin/activate
```

3. Install dependencies
```bash
    (.venv) $ pip install -r requirements.txt
```

4. Run service
``` bash
    (.venv) $ uvicorn main:app
```

## Docker

Build image (from repo root):
```bash
docker build -t integrations-svc .
```

Run container (reads env vars such as `DATABASE_URL` and `TOKEN_ENCRYPTION_KEY`):
```bash
docker run --env-file .env \
  -p 8000:8000 \
  -v $(pwd)/config/client_secret_google.json:/app/config/client_secret_google.json:ro \
  integrations-svc
```

Notes:
- `FASTAPIPORT` controls the internal uvicorn port (defaults to 8000); adjust `-p` mapping as needed.
- The Google OAuth client secret file is not baked into the image; mount it in if you need Google flows.
- Make sure `DATABASE_URL` points to a reachable Postgres instance from inside the container.

## Resource Details
