from mcstatus import JavaServer
import socket
import time

class MinecraftChecker:
    def __init__(self, timeout=10.0):
        """Simple Minecraft server checker."""
        self.timeout = timeout

    def check_server(self, ip, port=25565):
        """
        Check if a Minecraft server is online and if it might have a whitelist.

        Args:
            ip (str): The server IP/hostname
            port (int): The server port (default: 25565)

        Returns:
            dict: Server info if online, None if offline
        """
        try:
            # Set socket timeout for fast scanning
            socket.setdefaulttimeout(self.timeout)

            # Connect to server and measure latency
            server = JavaServer.lookup(f"{ip}:{port}")

            # Measure ping latency
            start_time = time.time()
            try:
                latency = server.ping()
                latency_ms = round(latency, 1)
            except:
                # If ping fails, measure status call latency instead
                start_time = time.time()
                latency_ms = 0

            # Get server status
            if latency_ms == 0:
                start_time = time.time()
            status = server.status()
            if latency_ms == 0:
                latency_ms = round((time.time() - start_time) * 1000, 1)

            # Extract version information
            version = "Unknown"
            if hasattr(status, 'version') and status.version:
                if hasattr(status.version, 'name') and status.version.name:
                    version = status.version.name
                elif hasattr(status.version, 'protocol') and status.version.protocol:
                    version = f"Protocol {status.version.protocol}"

            # Check for whitelist hints in description
            description = str(status.description).lower()
            whitelist_hints = ["whitelist", "private", "invite only", "application"]
            has_whitelist = any(hint in description for hint in whitelist_hints)

            return {
                "ip": ip,
                "port": port,
                "online": True,
                "has_whitelist": has_whitelist,
                "players_online": status.players.online,
                "players_max": status.players.max,
                "description": str(status.description),
                "version": version,
                "latency_ms": latency_ms,
                "possible_whitelist": has_whitelist
            }
        except:
            return None

    def ping_server(self, ip, port=25565):
        """
        Simple ping test for a Minecraft server.

        Args:
            ip (str): The server IP/hostname
            port (int): The server port (default: 25565)

        Returns:
            bool: True if server responds to ping, False otherwise
        """
        try:
            # Set socket timeout for fast scanning
            socket.setdefaulttimeout(self.timeout)

            server = JavaServer.lookup(f"{ip}:{port}")
            server.ping()
            return True
        except:
            return False
