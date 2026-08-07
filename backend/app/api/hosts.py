import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from jose import JWTError

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.schemas.host import HostCreate, HostUpdate, HostResponse, HostImportRequest
from app.services import host_service, ssh_service
from app.services.auth_service import decode_token
from app.services.aws_service import AwsError
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hosts", tags=["hosts"])


async def _audit_terminal(user_id: int, username: str, host_id: int, hostname: str, detail: str):
    try:
        from app.services.audit_service import create_log_async
        await create_log_async(
            user_id=user_id,
            username=username,
            action="SSH",
            resource=f"/api/v1/hosts/{host_id}",
            resource_type="主机运维",
            detail=f"{detail}: {hostname}",
        )
    except Exception:
        pass


@router.get("", response_model=list[HostResponse])
def list_hosts(
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return host_service.list_hosts(db)


@router.get("/{host_id}", response_model=HostResponse)
def get_host(
    host_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    host = host_service.get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主机不存在")
    return host


@router.post("", response_model=HostResponse, status_code=status.HTTP_201_CREATED)
def create_host(
    data: HostCreate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    return host_service.create_host(db, data)


@router.put("/{host_id}", response_model=HostResponse)
def update_host(
    host_id: int,
    data: HostUpdate,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    host = host_service.get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主机不存在")
    return host_service.update_host(db, host, data)


@router.delete("/{host_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_host(
    host_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    host = host_service.get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主机不存在")
    host_service.delete_host(db, host)


@router.get("/{host_id}/agent-token")
def get_agent_token(
    host_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    host = host_service.get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主机不存在")
    if not host.agent_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该主机未激活 Agent")
    return {"agent_token": host.agent_token}


@router.post("/{host_id}/regenerate-token")
def regenerate_agent_token(
    host_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    try:
        token = host_service.regenerate_agent_token(db, host_id)
    except host_service.HostNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"agent_token": token}


@router.get("/{host_id}/metrics")
def get_host_metrics(
    host_id: int,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    host = host_service.get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主机不存在")
    items = host_service.get_host_metrics(db, host_id, hours)
    return {"items": items}


@router.get("/{host_id}/metrics/latest")
def get_latest_metric(
    host_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    host = host_service.get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="主机不存在")
    metric = host_service.get_latest_metric(db, host_id)
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无监控数据")
    return metric


@router.post("/import", response_model=HostResponse, status_code=status.HTTP_201_CREATED)
def import_ec2_host(
    data: HostImportRequest,
    db: Session = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    """Import an EC2 instance as a managed host.

    Fetches the EC2 instance details (IP, name, type) via boto3 and creates a
    Host record pre-filled with the instance metadata.
    """
    try:
        return host_service.import_from_ec2(db, data)
    except AwsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.websocket("/{host_id}/terminal")
async def terminal(host_id: int, websocket: WebSocket, token: str = ""):
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        payload = decode_token(token)
        if not payload.get("sub"):
            await websocket.close(code=4001, reason="Invalid token")
            return
    except JWTError:
        await websocket.close(code=4001, reason="Invalid token")
        return

    db = next(get_db())
    try:
        try:
            conn_info = host_service.get_ssh_connection_info(db, host_id)
        except host_service.HostNotFoundError as e:
            await websocket.close(code=4004, reason=str(e))
            return
        except host_service.MissingCredentialError as e:
            await websocket.close(code=4000, reason=str(e))
            return

        ssh_client = None
        channel = None
        audit_user_id = int(payload["sub"])
        audit_user = payload.get("username", "")
        audit_host = conn_info["name"]

        try:
            ssh_client = ssh_service.create_ssh_client(
                hostname=conn_info["hostname"],
                port=conn_info["port"],
                username=conn_info["username"],
                auth_type=conn_info["auth_type"],
                auth_value=conn_info["auth_value"],
            )
            channel = ssh_service.open_shell(ssh_client)
            await websocket.accept()

            # Audit: terminal connected
            await _audit_terminal(audit_user_id, audit_user, host_id, audit_host, "SSH 登录主机")
        except Exception as e:
            logger.warning("SSH connection failed for host %s: %s", host_id, e)
            await websocket.close(code=4000, reason=f"SSH: {e}")
            return

        loop = asyncio.get_event_loop()

        async def ssh_to_ws():
            try:
                while True:
                    data = await loop.run_in_executor(None, channel.recv, 4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except Exception:
                logger.debug("ssh_to_ws closed", exc_info=True)

        async def ws_to_ssh():
            try:
                while True:
                    raw = await websocket.receive()
                    if raw["type"] != "websocket.receive":
                        continue
                    if "text" in raw:
                        txt = raw["text"]
                        if txt.startswith("{") and txt.endswith("}"):
                            try:
                                msg = json.loads(txt)
                                if msg.get("type") == "resize":
                                    ssh_service.resize_pty(
                                        channel,
                                        msg.get("cols", 80),
                                        msg.get("rows", 24),
                                    )
                                    continue
                            except (json.JSONDecodeError, ValueError):
                                pass
                        channel.send(txt.encode())
                    elif "bytes" in raw:
                        channel.send(raw["bytes"])
            except WebSocketDisconnect:
                pass
            except Exception:
                logger.debug("ws_to_ssh closed", exc_info=True)

        try:
            task_a = asyncio.create_task(ssh_to_ws())
            task_b = asyncio.create_task(ws_to_ssh())
            await asyncio.wait(
                [task_a, task_b],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=settings.ssh_terminal_idle_timeout,
            )
            for t in (task_a, task_b):
                if not t.done():
                    t.cancel()
            await asyncio.gather(task_a, task_b, return_exceptions=True)
        except Exception:
            logger.debug("terminal session ended", exc_info=True)
        finally:
            if channel:
                try:
                    channel.close()
                except Exception:
                    pass
            if ssh_client:
                try:
                    ssh_client.close()
                except Exception:
                    pass
            # Audit: terminal disconnected
            await _audit_terminal(audit_user_id, audit_user, host_id, audit_host, "退出主机")
            # Explicitly close the WebSocket so the client gets onclose
            try:
                await websocket.close(code=1000)
            except Exception:
                pass
    finally:
        db.close()
