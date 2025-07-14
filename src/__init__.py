import os
import logging
import threading
import argparse
import time
import asyncio
import sys
import signal
from dotenv import load_dotenv

def setup_logging(debug=False):
    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    if debug:
        logging.getLogger('minecraft_checker').setLevel(logging.DEBUG)
        logging.getLogger('minecraft_scanner').setLevel(logging.DEBUG)
        logging.getLogger('main').setLevel(logging.DEBUG)
    return logging.getLogger("main")

logger = setup_logging()

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.scanner import MinecraftScanner
from src.discord_notifier import DiscordNotifier, DISCORD_AVAILABLE

shutdown_requested = False

def handle_shutdown_signal(sig, frame):
    global shutdown_requested
    logger.info("Shutdown requested. Finishing current scans...")
    shutdown_requested = True

signal.signal(signal.SIGINT, handle_shutdown_signal)
signal.signal(signal.SIGTERM, handle_shutdown_signal)

def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Minecraft Server Scanner")
    parser.add_argument("--cidr", help="CIDR notation IP range to scan (e.g., 192.168.1.0/24)")
    parser.add_argument("--port", type=int, default=25565, help="Port to scan (default: 25565)")
    parser.add_argument("--workers", type=int, default=50, help="Maximum number of concurrent threads")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between scans in seconds")
    parser.add_argument("--file", help="File containing list of IPs to scan (one per line)")
    parser.add_argument("--random", action="store_true", help="Scan random IPs indefinitely")
    parser.add_argument("--count", type=int, help="Number of random IPs to scan (requires --random)")
    parser.add_argument("--console-only", action="store_true", help="Only output to console, don't use Discord")
    parser.add_argument("--progress", type=int, default=100, help="Show progress every N scans")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--realtime", action="store_true", help="Send Discord notifications in real-time as servers are found")
    args = parser.parse_args()

    global logger
    logger = setup_logging(debug=args.debug)
    if args.debug:
        logger.debug("Debug logging enabled")

    checkpoints_dir = os.path.join(os.path.dirname(current_dir), "checkpoints")
    os.makedirs(checkpoints_dir, exist_ok=True)

    scanner = MinecraftScanner(
        max_workers=args.workers, 
        scan_delay=args.delay,
        progress_interval=args.progress,
        realtime_notifications=args.realtime
    )

    discord_notifier = None
    discord_enabled = not args.console_only and DISCORD_AVAILABLE
    if discord_enabled:
        discord_token = os.getenv("DISCORD_TOKEN")
        discord_channel_id = os.getenv("DISCORD_CHANNEL_ID")

        if not discord_token or not discord_channel_id:
            logger.error("Discord token or channel ID not configured. Set DISCORD_TOKEN and DISCORD_CHANNEL_ID in .env file.")
        else:
            try:
                discord_channel_id = int(discord_channel_id)
                discord_notifier = DiscordNotifier(discord_token, discord_channel_id)
                discord_notifier.start_in_thread()
                logger.info("Waiting for Discord bot to connect...")
                if not discord_notifier.ready.wait(timeout=10):
                    logger.warning("Discord bot connection timed out. Will still try to send messages.")
            except ValueError:
                logger.error(f"Invalid Discord channel ID: {discord_channel_id}")
            except Exception as e:
                logger.error(f"Error initializing Discord: {str(e)}")

    result_queue = []
    results_sent = threading.Event()
    realtime_enabled = args.realtime and discord_enabled and discord_notifier

    if realtime_enabled:
        logger.info("Real-time notifications enabled - servers will be reported as they are found")

    def send_results_thread():
        while True:
            if realtime_enabled and args.realtime:
                if shutdown_requested and not result_queue:
                    results_sent.set()
                    break
                time.sleep(0.5)
                continue

            if not result_queue:
                if shutdown_requested:
                    results_sent.set()
                    break
                time.sleep(0.5)
                continue

            server_info = result_queue.pop(0)
            print_server_info_to_console(server_info)

            if discord_notifier and not args.console_only:
                try:
                    discord_sent = discord_notifier.send_server_info(server_info)
                    if discord_sent:
                        logger.info(f"Sent server info for {server_info['ip']} to Discord")
                    else:
                        logger.warning(f"Failed to send server info for {server_info['ip']} to Discord")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"Error sending to Discord: {str(e)}")

    sender_thread = threading.Thread(target=send_results_thread, daemon=True)
    sender_thread.start()

    try:
        if args.realtime:
            def realtime_callback(server_info):
                print_server_info_to_console(server_info)
                if discord_notifier and discord_enabled:
                    try:
                        discord_sent = discord_notifier.send_server_info(server_info)
                        if discord_sent:
                            logger.info(f"Sent real-time server info for {server_info['ip']} to Discord")
                        else:
                            logger.warning(f"Failed to send real-time server info for {server_info['ip']} to Discord")
                    except Exception as e:
                        logger.error(f"Error sending real-time notification to Discord: {str(e)}")

            scanner.set_realtime_callback(realtime_callback)

        if args.random:
            logger.info(f"Starting random IP scan{' for ' + str(args.count) + ' IPs' if args.count else ' indefinitely'}")
            results = scanner.scan_random_ips(count=args.count, port=args.port)
            if not args.realtime:
                for server_info in results:
                    result_queue.append(server_info)

        elif args.cidr:
            results = scanner.scan_range(args.cidr, args.port)
            if not args.realtime:
                for server_info in results:
                    result_queue.append(server_info)

        elif args.file:
            with open(args.file, 'r') as f:
                ip_list = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
            results = scanner.scan_ip_list(ip_list, args.port)
            if not args.realtime:
                for server_info in results:
                    result_queue.append(server_info)

        else:
            logger.error("No scan target specified. Use --cidr, --file, or --random.")

    except KeyboardInterrupt:
        logger.info("Scan interrupted by user. Waiting for result processing...")
    finally:
        if args.realtime and discord_notifier and not args.console_only:
            time.sleep(1)
        logger.info("Scan complete. Results processed.")

def print_server_info_to_console(server_info):
    print("\n" + "="*60)
    print(f"MINECRAFT SERVER FOUND: {server_info['ip']}:{server_info['port']}")
    print("="*60)
    print(f"Version: {server_info['version']}")
    print(f"Players: {server_info['players_online']}/{server_info['players_max']}")
    print(f"Latency: {server_info['latency_ms']}ms")
    print(f"Possible Whitelist: {'Yes' if server_info['possible_whitelist'] else 'No/Unknown'}")
    print(f"Description: {server_info['description']}")

    if 'player_samples' in server_info and server_info['player_samples']:
        player_names = ', '.join([player['name'] for player in server_info['player_samples']])
        print(f"Online Players: {player_names}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
