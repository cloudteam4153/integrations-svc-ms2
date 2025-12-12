import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text
from services.database import AsyncSessionLocal
from services.sync.gmail import gmail_sync_messages, connection_to_creds

from google.oauth2.credentials import Credentials

from models.sync import (
    Sync,
    SyncStatus,
    SyncType
)
from models.connection import (
    Connection,
    ConnectionStatus
)
from models.message import Message


# Background task for async sync processing
async def process_sync_job(
        sync_id: UUID,
        conn: Connection
):
    """Background task to process sync job"""
    
    async with AsyncSessionLocal() as db:  
        
        result = await db.execute(
            select(Sync).where(Sync.id == sync_id)
        )
        sync_job = result.scalar_one()

        try:
            
            sync_job.status = SyncStatus.RUNNING
            sync_job.time_start = datetime.now(timezone.utc)
            sync_job.progress_percentage = 0
            sync_job.current_operation = "Starting sync"
            await db.commit()
            
            # Todo later: add something to check which connection (gmail, slack, etc)
            # and call the correct API function

            creds = connection_to_creds(conn)

            result = await asyncio.to_thread(
                gmail_sync_messages,
                creds,
                sync_job.sync_type,
                conn.last_history_id
            )

            messages = result["messages"]
            total = result["messages_synced"]

            processed = 0
            new_count = 0
            updated_count = 0

            for msg in messages:
                stmt = insert(Message).values(
                    external_id=msg.get("id"),
                    user_id=sync_job.user_id,

                    thread_id=msg.get("threadId"),
                    label_ids=msg.get("labelIds"),
                    snippet=msg.get("snippet"),
                    history_id=int(msg.get("historyId")) if msg.get("historyId") else None,
                    internal_date=int(msg.get("internalDate")) if msg.get("internalDate") else None,
                    size_estimate=msg.get("sizeEstimate"),

                    from_address=msg.get("from"),
                    to_address=msg.get("to"),
                    cc_address=msg.get("cc"),
                    subject=msg.get("subject"),
                    body=msg.get("body"),
                ).on_conflict_do_update(
                    index_elements=["user_id", "external_id"],
                    set_={
                        "thread_id": msg.get("threadId"),
                        "label_ids": msg.get("labelIds"),
                        "snippet": msg.get("snippet"),
                        "history_id": int(msg.get("historyId")) if msg.get("historyId") else None,
                        "internal_date": int(msg.get("internalDate")) if msg.get("internalDate") else None,
                        "size_estimate": msg.get("sizeEstimate"),

                        "from_address": msg.get("from"),
                        "to_address": msg.get("to"),
                        "cc_address": msg.get("cc"),
                        "subject": msg.get("subject"),
                        "body": msg.get("body"),

                        "updated_at": datetime.now(timezone.utc),
                    },
                ).returning(text("xmax = 0 AS inserted"))

                result_row = await db.execute(stmt)
                was_inserted = result_row.scalar_one()

                if was_inserted:
                    new_count += 1
                else:
                    updated_count += 1

                processed += 1

                sync_job.progress_percentage = int((processed / total) * 100)
                sync_job.current_operation = f"Ingested {processed}/{total} messages"

                if processed % 25 == 0:
                    await db.commit()

            await db.commit()

            sync_job.messages_synced = total
            sync_job.messages_new = new_count
            sync_job.messages_updated = updated_count
            sync_job.last_history_id = result["last_history_id"]

            conn_db = await db.get(Connection, conn.id)
            if not conn_db:
                raise RuntimeError("Connection no longer exists for this sync job")
            conn_db.last_history_id = result["last_history_id"]

            sync_job.progress_percentage = 100
            sync_job.current_operation = "Completed"
            sync_job.status = SyncStatus.COMPLETED
            sync_job.time_end = datetime.now(timezone.utc)

            await db.commit()

        except Exception as e:
            sync_job.status = SyncStatus.FAILED
            sync_job.time_end = datetime.now(timezone.utc)
            sync_job.error_message = str(e)
            sync_job.retry_count += 1
            sync_job.current_operation = "Failed"

            await db.commit()
