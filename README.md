# Integrations Microservice API

Handles integrating external services with our application framework. Manages the connections to these external services such as Gmail, Slack, etc., pipes messages to and from these external services, and handles sync jobs. All data persisted in database.

Project for COMS4153, Fall 2025 Cloud Team

## Get Started

### Prerequisites
- Python 3.13+

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

## Resource Details