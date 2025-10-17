from __future__ import annotations

import os
import socket
from datetime import datetime

from typing import Dict, List
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi import Query, Path
from typing import Optional

from models.health import Health
from models.connection import ConnectionBase, ConnectionCreate, ConnectionRead, ConnectionUpdate


port = int(os.environ.get("FASTAPIPORT", 8000))


app = FastAPI(
    title="Integrations Microservice",
    description="FastAPI microservice handling external resource integration, ingest, and management.",
    version="0.1.0",
)

# -----------------------------------------------------------------------------
# Health endpoints
# -----------------------------------------------------------------------------

def make_health(echo: Optional[str], path_echo: Optional[str]=None) -> Health:
    return Health(
        status=200,
        status_message="OK",
        timestamp=datetime.utcnow().isoformat() + "Z",
        ip_address=socket.gethostbyname(socket.gethostname()),
        echo=echo,
        path_echo=path_echo
    )

@app.get("/health", response_model=Health)
def get_health_no_path(echo: str | None = Query(None, description="Optional echo string")):
    # Works because path_echo is optional in the model
    return make_health(echo=echo, path_echo=None)

@app.get("/health/{path_echo}", response_model=Health)
def get_health_with_path(
    path_echo: str = Path(..., description="Required echo in the URL path"),
    echo: str | None = Query(None, description="Optional echo string"),
):
    return make_health(echo=echo, path_echo=path_echo)

# -----------------------------------------------------------------------------
# Connection Endpoints
# -----------------------------------------------------------------------------

# GET Connections (list)
@app.get("/connections", response_model=List[ConnectionRead], status_code=200)
async def list_connections():
    """Get list of connections, can be filtered (to be implemented)"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# GET Connection specific
@app.get("/connections/{connection_id}", response_model=ConnectionRead, status_code=200)
async def get_connection(connection_id: UUID):
    """Get information about a specific connection"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# POST new Connection
@app.post("/connections", response_model=ConnectionRead, status_code=201)
async def create_connection(connection: ConnectionCreate):
    """Creates a new connection"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# PUT/PATCH Connection update
@app.patch("/connections/{connection_id}", response_model=ConnectionRead, status_code=200)
async def update_connection(connection_id: UUID, connection: ConnectionUpdate):
    """Updates the details of a connection"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# DELETE Connection Specific
@app.delete("/connections/{connection_id}", status_code=204)
async def delete_connection(connection_id: UUID):
    """Deletes a specific connection if it exists"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# Test Connection
@app.post("/connections/{connection_id}/test", status_code=200)
async def test_connection(connection_id: UUID):
    """Test if the connection is valid and working"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# Refresh/reconnect
@app.post("/connections/{connection_id}/refresh", response_model=ConnectionRead, status_code=200)
async def refresh_connection(connection_id: UUID):
    """Refresh authentication tokens for the connection"""
    raise HTTPException(status_code=501, detail="NOT IMPLEMENTED")

# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the Product/Company API. See /docs for OpenAPI UI."}

# -----------------------------------------------------------------------------
# Entrypoint for `python main.py`
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
