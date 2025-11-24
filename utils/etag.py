import hashlib
from datetime import datetime
from typing import Any, Optional
from fastapi import Request, Response, HTTPException
from pydantic import BaseModel


def generate_etag(data: Any) -> str:
    """
    Generate an ETag based on the object's data.
    
    For database objects, we use updated_at timestamp and id to create a unique hash.
    This ensures the ETag changes whenever the object is modified.
    """
    if hasattr(data, 'updated_at') and hasattr(data, 'id'):
        # Use timestamp and id for database objects
        content = f"{data.id}:{data.updated_at.isoformat()}"
    elif isinstance(data, BaseModel):
        # For Pydantic models, use the JSON representation
        content = data.model_dump_json(sort_keys=True)
    else:
        # Fallback to string representation
        content = str(data)
    
    # Create MD5 hash of the content
    etag_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
    return f'"{etag_hash}"'


def check_etag_match(request: Request, current_etag: str) -> bool:
    """
    Check if the ETag in the If-None-Match header matches the current ETag.
    
    Returns True if they match (meaning the client has the current version).
    """
    if_none_match = request.headers.get('if-none-match')
    if not if_none_match:
        return False
    
    # Handle multiple ETags in the header (comma-separated)
    client_etags = [etag.strip() for etag in if_none_match.split(',')]
    
    # Check for wildcard or exact match
    return '*' in client_etags or current_etag in client_etags


def set_etag_headers(response: Response, etag: str) -> None:
    """
    Set ETag and Cache-Control headers on the response.
    """
    response.headers['ETag'] = etag
    response.headers['Cache-Control'] = 'private, max-age=0, must-revalidate'


def handle_conditional_request(request: Request, data: Any) -> tuple[str, bool]:
    """
    Handle conditional requests with ETag support.
    
    Returns:
        tuple: (etag, should_return_304)
            - etag: The generated ETag for the data
            - should_return_304: True if should return 304 Not Modified
    """
    current_etag = generate_etag(data)
    
    if check_etag_match(request, current_etag):
        return current_etag, True
    
    return current_etag, False