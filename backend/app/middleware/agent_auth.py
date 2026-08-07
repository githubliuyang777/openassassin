from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.host import Host

bearer_scheme = HTTPBearer()


def get_current_agent(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> int:
    """Agent token authentication — look up host by agent_token, return host_id.

    Not a JWT. The agent passes the raw token string as a Bearer token, and
    we match it against the hosts table. Returns the host_id (int) so route
    handlers know which host is reporting.
    """
    host = db.query(Host).filter(Host.agent_token == credentials.credentials).first()
    if not host:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent token")
    return host.id
