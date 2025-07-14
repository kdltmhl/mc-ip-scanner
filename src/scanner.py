import ipaddress
import concurrent.futures
import logging
import random
import time
import os
import json
import threading
import queue
from datetime import datetime

from src.minecraft_checker import MinecraftChecker


class MinecraftScanner:
    def __init__(self, max_workers=50, scan_delay=0.5, progress_interval=100, realtime_notifications=False):
        """Initialize scanner with worker threads and scan parameters"""
        self.max_workers = max_workers
        self.scan_delay = scan_delay
        self.progress_interval = progress_interval
        self.realtime_notifications = realtime_notifications
        self.realtime_callback = None
        self.checker = MinecraftChecker()
        self.logger = logging.getLogger("minecraft_scanner")
        self.stats = {
            "start_time": time.time(),
            "ips_scanned": 0,
            "servers_found": 0,
            "errors": 0,
            "last_ip": None,
        }

    def set_realtime_callback(self, callback):
        """Set callback for real-time server notifications"""
        self.realtime_callback = callback
        self.logger.info("Real-time callback set - servers will be reported immediately as they are found")

    def scan_ip(self, ip, port=25565):
        """Scan single IP for Minecraft server"""
        time.sleep(random.uniform(0, self.scan_delay))
        self.stats["last_ip"] = str(ip)
        max_scan_time = 20
        start_time = time.time()

        try:
            is_sample_ip = any(test_ip in str(ip) for test_ip in [
                "mc.rubincraft.org", "rubincraft.dat.gg", "openmc.net",
                "play.hypixel.net", "mc.hypixel.net", "gommehd.net",
                "mc.cubecraft.net", "aternos.me"
            ])

            if is_sample_ip:
                self.logger.info(f"Scanning known server IP: {ip}:{port}")
                ping_timeout = threading.Event()
                ping_result = [False]

                def do_ping():
                    try:
                        result = self.checker.ping_server(str(ip), port)
                        ping_result[0] = result
                    except Exception as e:
                        self.logger.error(f"Error in ping thread: {str(e)}")
                    finally:
                        ping_timeout.set()

                ping_thread = threading.Thread(target=do_ping, name=f"ping-{ip}")
                ping_thread.daemon = True
                ping_thread.start()

                if ping_timeout.wait(timeout=5):
                    self.logger.info(f"Ping test for {ip}:{port}: {'Successful' if ping_result[0] else 'Failed'}")
                else:
                    self.logger.warning(f"Ping test for {ip}:{port} timed out after 5 seconds")

            if time.time() - start_time > max_scan_time / 2:
                self.stats["ips_scanned"] += 1
                return None

            check_timeout = threading.Event()
            server_result = [None]

            def do_check():
                try:
                    result = self.checker.check_server(str(ip), port)
                    server_result[0] = result
                except Exception as e:
                    self.logger.error(f"Error in server check thread: {type(e).__name__}: {str(e)}")
                finally:
                    check_timeout.set()

            check_thread = threading.Thread(target=do_check, name=f"check-{ip}")
            check_thread.daemon = True
            check_thread.start()

            remaining_time = max(1, max_scan_time - (time.time() - start_time))

            if check_timeout.wait(timeout=remaining_time):
                result = server_result[0]
            else:
                self.logger.warning(f"Server check for {ip}:{port} timed out after {remaining_time:.1f} seconds")
                result = None

            self.stats["ips_scanned"] += 1

            if result:
                self.stats["servers_found"] += 1
                version = result.get('version', 'Unknown')
                players = f"{result.get('players_online', '?')}/{result.get('players_max', '?')}"
                self.logger.info(f"Found Minecraft server at {ip}:{port} (Version: {version}, Players: {players})")

                if self.realtime_callback and callable(self.realtime_callback):
                    try:
                        self.realtime_callback(result)
                    except Exception as e:
                        self.logger.error(f"Error in real-time callback for {ip}:{port}: {str(e)}")

            elif is_sample_ip:
                self.logger.warning(f"Failed to detect known server at {ip}:{port}")

            if self.stats["ips_scanned"] % self.progress_interval == 0:
                self._print_progress()

            return result
        except Exception as e:
            self.stats["ips_scanned"] += 1
            self.stats["errors"] += 1
            self.logger.error(f"Error scanning {ip}: {str(e)}")
            return None

    def _send_discord_notification(self, server_info):
        """Send Discord notification for found server"""
        try:
            from src.discord_notifier import DiscordNotifier
            from src import discord_notifier

            if not hasattr(discord_notifier, 'notifier') or not discord_notifier.notifier:
                return

            notifier = discord_notifier.notifier
            if not notifier.is_configured():
                return

            self.logger.info(
                f"Sending real-time Discord notification for server {server_info['ip']}:{server_info['port']}")
            notifier.send_server_notification(server_info)
        except ImportError:
            self.logger.warning("Discord notifier module not available")
        except Exception as e:
            self.logger.error(f"Error in Discord notification: {str(e)}")

    def _print_progress(self):
        """Print scan progress stats"""
        elapsed = time.time() - self.stats["start_time"]
        ips_per_second = self.stats["ips_scanned"] / elapsed if elapsed > 0 else 0

        print(f"\n--- SCAN PROGRESS ---")
        print(f"IPs scanned: {self.stats['ips_scanned']}")
        print(f"Servers found: {self.stats['servers_found']}")
        print(f"Errors: {self.stats['errors']}")
        print(f"Scan rate: {ips_per_second:.2f} IPs/second")
        print(f"Last IP: {self.stats['last_ip']}")
        print(f"Elapsed time: {int(elapsed)} seconds")
        print(f"----------------------\n")

        self._save_checkpoint()

    def _save_checkpoint(self):
        """Save scan checkpoint"""
        try:
            checkpoint_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)

            checkpoint = {
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "last_ip": self.stats["last_ip"]
            }

            checkpoint_file = os.path.join(checkpoint_dir, "scan_checkpoint.json")
            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving checkpoint: {str(e)}")

    def get_random_ip(self):
        """Generate random valid public IPv4"""
        while True:
            ip_int = random.randint(0, (2 ** 32) - 1)
            ip = ipaddress.IPv4Address(ip_int)
            if not (ip.is_private or ip.is_loopback or ip.is_link_local or
                    ip.is_multicast or ip.is_reserved):
                return str(ip)

    def scan_range(self, ip_range, port=25565, nearby_count=100):
        """Scan IP range in CIDR notation or IP with nearby addresses"""
        if "/" in ip_range:
            try:
                network = ipaddress.ip_network(ip_range)
                ip_list = list(network)
                self.logger.info(f"Starting scan of CIDR range {ip_range} ({len(ip_list)} IPs)")
            except ValueError as e:
                self.logger.warning(f"Invalid CIDR notation: {e}. Treating as a regular IP address.")
                return self._scan_ip_with_nearby(ip_range.split('/')[0], port, nearby_count)
        else:
            return self._scan_ip_with_nearby(ip_range, port, nearby_count)

        results = []
        self.stats = {
            "start_time": time.time(),
            "ips_scanned": 0,
            "servers_found": 0,
            "errors": 0,
            "last_ip": None,
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ip = {executor.submit(self.scan_ip, ip, port): ip for ip in ip_list}
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    self.logger.error(f"Error scanning {ip}: {str(e)}")

        self._print_progress()
        self.logger.info(f"Scan complete. Found {len(results)} servers.")
        return results

    def _scan_ip_with_nearby(self, ip_address, port=25565, nearby_count=100):
        """Scan specific IP with surrounding IPs"""
        try:
            ip_obj = ipaddress.IPv4Address(ip_address)
            ip_list = []

            before_count = nearby_count // 2
            after_count = nearby_count - before_count

            start_before = max(0, int(ip_obj) - before_count)
            for i in range(start_before, int(ip_obj)):
                ip_list.append(ipaddress.IPv4Address(i))

            ip_list.append(ip_obj)

            end_after = min(2 ** 32 - 1, int(ip_obj) + after_count)
            for i in range(int(ip_obj) + 1, end_after + 1):
                ip_list.append(ipaddress.IPv4Address(i))

            self.logger.info(f"Starting scan of IP {ip_address} and {len(ip_list) - 1} nearby IPs")
            self.logger.info(f"IP range: from {ip_list[0]} to {ip_list[-1]}")

            return self.scan_ip_list([str(ip) for ip in ip_list], port)
        except Exception as e:
            self.logger.error(f"Error processing IP address {ip_address}: {str(e)}")
            return []

    def scan_ip_list(self, ip_list, port=25565):
        """Scan list of specific IPs"""
        results = []
        self.logger.info(f"Starting scan of {len(ip_list)} specific IPs")

        self.stats = {
            "start_time": time.time(),
            "ips_scanned": 0,
            "servers_found": 0,
            "errors": 0,
            "last_ip": None,
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_ip = {executor.submit(self.scan_ip, ip, port): ip for ip in ip_list}
            for future in concurrent.futures.as_completed(future_to_ip):
                ip = future_to_ip[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    self.logger.error(f"Error scanning {ip}: {str(e)}")

        self._print_progress()
        self.logger.info(f"Scan complete. Found {len(results)} servers.")
        return results

    def scan_random_ips(self, count=None, port=25565):
        """Scan random IPs until count is reached or indefinitely"""
        results = []
        ips_to_scan = count if count is not None else float('inf')
        self.logger.info(
            f"Starting random IP scan for {ips_to_scan if ips_to_scan != float('inf') else 'unlimited'} IPs")

        self.stats = {
            "start_time": time.time(),
            "ips_scanned": 0,
            "servers_found": 0,
            "errors": 0,
            "last_ip": None,
        }

        last_ip = self._load_last_ip()
        if last_ip:
            self.logger.info(f"Resuming scan from previous checkpoint: {last_ip}")
            try:
                current_ip = ipaddress.IPv4Address(last_ip) + 1
            except:
                current_ip = ipaddress.IPv4Address(self.get_random_ip())
        else:
            current_ip = ipaddress.IPv4Address(self.get_random_ip())

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            workers_to_use = self.max_workers if ips_to_scan == float('inf') else min(self.max_workers,
                                                                                      int(ips_to_scan))

            for _ in range(workers_to_use):
                ip = str(current_ip)
                futures[executor.submit(self.scan_ip, ip, port)] = ip
                current_ip += 1
                if current_ip == ipaddress.IPv4Address("255.255.255.255"):
                    current_ip = ipaddress.IPv4Address("0.0.0.0")

            scanned_count = 0
            while futures and (count is None or scanned_count < count):
                done, not_done = concurrent.futures.wait(
                    futures,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                for future in done:
                    ip = futures.pop(future)
                    scanned_count += 1

                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        self.logger.error(f"Error processing result for {ip}: {str(e)}")

                    if count is None or scanned_count + len(futures) < count:
                        ip = str(current_ip)
                        futures[executor.submit(self.scan_ip, ip, port)] = ip
                        current_ip += 1
                        if current_ip == ipaddress.IPv4Address("255.255.255.255"):
                            current_ip = ipaddress.IPv4Address("0.0.0.0")

        self._print_progress()
        self.logger.info(f"Scan complete. Found {len(results)} servers.")
        return results

    def _load_last_ip(self):
        """Load last scanned IP from checkpoint"""
        try:
            checkpoint_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "checkpoints")
            checkpoint_file = os.path.join(checkpoint_dir, "scan_checkpoint.json")

            if os.path.exists(checkpoint_file):
                with open(checkpoint_file, "r") as f:
                    checkpoint = json.load(f)
                return checkpoint.get("last_ip")
        except Exception as e:
            self.logger.error(f"Error loading checkpoint: {str(e)}")
        return None