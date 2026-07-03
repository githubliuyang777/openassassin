import socket
import time


def test_tcp(host: str, port: int, timeout: float = 5.0) -> dict:
    result = {"host": host, "port": port, "success": False, "latency_ms": None, "error": None}
    try:
        start = time.perf_counter()
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = time.perf_counter() - start
            result["success"] = True
            result["latency_ms"] = round(elapsed * 1000, 2)
    except socket.timeout:
        result["error"] = f"连接超时（{timeout}秒）"
    except socket.gaierror:
        result["error"] = "无法解析主机名"
    except ConnectionRefusedError:
        result["error"] = "连接被拒绝"
    except OSError as e:
        result["error"] = f"网络错误: {e.strerror if hasattr(e, 'strerror') else str(e)}"
    return result
