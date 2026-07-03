from io import StringIO

import paramiko
from paramiko import RSAKey, Ed25519Key, ECDSAKey

from app.config import settings


def create_ssh_client(hostname: str, port: int, username: str,
                      auth_type: str, auth_value: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs = {
        "hostname": hostname,
        "port": port,
        "username": username,
        "timeout": settings.ssh_connect_timeout,
        "banner_timeout": settings.ssh_connect_timeout,
    }

    if auth_type in ("ssh_key",):
        pkey = _load_private_key(auth_value)
        connect_kwargs["pkey"] = pkey
    else:
        connect_kwargs["password"] = auth_value

    client.connect(**connect_kwargs)
    return client


def open_shell(client: paramiko.SSHClient, term: str = "xterm-256color",
               cols: int = 80, rows: int = 24) -> paramiko.Channel:
    channel = client.invoke_shell(term=term, width=cols, height=rows)
    return channel


def resize_pty(channel: paramiko.Channel, cols: int, rows: int) -> None:
    channel.resize_pty(width=cols, height=rows)


def _load_private_key(key_str: str) -> paramiko.PKey:
    key_file = StringIO(key_str)
    for key_cls in (RSAKey, Ed25519Key, ECDSAKey):
        try:
            key_file.seek(0)
            return key_cls.from_private_key(key_file)
        except paramiko.SSHException:
            continue
    raise ValueError("无法识别的私钥格式")
