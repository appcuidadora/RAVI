import os
import glob
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from database import db

logger = logging.getLogger(__name__)

BACKUP_DIR = "/app/backups"
KEEP_LOCAL = 7


async def run_backup():
    """Dump do MongoDB (mongodump --gzip) → object storage, mantendo 7 cópias locais."""
    from storage import put_object
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    fname = f"ravi-{ts}.archive.gz"
    fpath = os.path.join(BACKUP_DIR, fname)
    try:
        proc = await asyncio.create_subprocess_exec(
            "mongodump", f"--uri={os.environ['MONGO_URL']}", f"--db={os.environ['DB_NAME']}",
            f"--archive={fpath}", "--gzip",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=900)
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode("utf-8", "replace")[:500])
        size = os.path.getsize(fpath)
        with open(fpath, "rb") as fh:
            data = fh.read()
        await asyncio.to_thread(put_object, f"backups/{fname}", data, "application/gzip")
        files = sorted(glob.glob(os.path.join(BACKUP_DIR, "ravi-*.archive.gz")))
        for old in files[:-KEEP_LOCAL]:
            os.remove(old)
        await db.admin_logs.insert_one({
            "id": uuid.uuid4().hex, "admin_email": "system", "admin_role": "SYSTEM",
            "action": "backup_completed", "office_id": None, "motivo": None,
            "details": {"arquivo": fname, "bytes": size, "storage_path": f"backups/{fname}"},
            "created_at": datetime.now(timezone.utc).isoformat()})
        logger.info("Backup concluído: %s (%d bytes)", fname, size)
    except Exception as e:
        logger.exception("Falha no backup: %s", e)
        await db.admin_logs.insert_one({
            "id": uuid.uuid4().hex, "admin_email": "system", "admin_role": "SYSTEM",
            "action": "backup_failed", "office_id": None, "motivo": None,
            "details": {"erro": str(e)[:500]},
            "created_at": datetime.now(timezone.utc).isoformat()})
