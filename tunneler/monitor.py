import psutil


def get_listening_ports(pid: int) -> set[int]:
    try:
        proc = psutil.Process(pid)
        connections = proc.net_connections(kind="tcp")
        children = proc.children(recursive=True)
        for child in children:
            try:
                connections.extend(child.net_connections(kind="tcp"))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {
            conn.laddr.port
            for conn in connections
            if conn.status == "LISTEN"
        }
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return set()
