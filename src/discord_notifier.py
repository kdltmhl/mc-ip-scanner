import asyncio
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    print("ERROR: discord.py package is not installed.")
    print("Please install it using: pip install discord.py")
    DISCORD_AVAILABLE = False

class DiscordNotifier:
    _last_message_time = 0
    _rate_limit_lock = threading.Lock()

    def __init__(self, token, channel_id):
        self.token = token
        self.channel_id = channel_id
        self.logger = logging.getLogger("discord_notifier")
        self.loop = None
        self.ready = threading.Event()
        self.executor = ThreadPoolExecutor(max_workers=2)

        if not DISCORD_AVAILABLE:
            self.logger.error("Discord functionality is disabled because discord.py is not installed")
            return

        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents)

        @self.bot.event
        async def on_ready():
            self.logger.info(f"Discord bot logged in as {self.bot.user}")
            self.ready.set()

        @self.bot.event
        async def on_message(message):
            if message.author != self.bot.user:
                await self.bot.process_commands(message)

        @self.bot.command(name="ping")
        async def ping(ctx):
            await ctx.send("Pong! Bot is alive.")

    async def _start(self):
        if not DISCORD_AVAILABLE:
            self.ready.set()
            return

        try:
            await self.bot.login(self.token)
            await self.bot.connect()
        except Exception as e:
            self.logger.error(f"Failed to start Discord bot: {str(e)}")
            self.ready.set()

    def start_in_thread(self):
        if not DISCORD_AVAILABLE:
            self.ready.set()
            return

        def run_bot():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_until_complete(self._start())
            except Exception as e:
                self.logger.error(f"Error in Discord bot thread: {str(e)}")
                self.ready.set()
            finally:
                self.loop.close()

        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()

    def send_server_info(self, server_info):
        with self._rate_limit_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_message_time
            if time_since_last < 0.75:
                time.sleep(0.75 - time_since_last)
            self._last_message_time = time.time()

        if not DISCORD_AVAILABLE or not self.ready.wait(timeout=10) or not self.loop or self.loop.is_closed():
            self._print_server_info_to_console(server_info)
            return False

        self.logger.info(f"Attempting to send Discord notification for {server_info['ip']}")
        self.logger.info(f"Using channel ID: {self.channel_id}")

        async def send_embed_async():
            available_channels = list(self.bot.get_all_channels())
            channel_info = [f"{c.name} ({c.id})" for c in available_channels]
            self.logger.info(f"Available channels: {', '.join(channel_info) if channel_info else 'None'}")

            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(self.channel_id)
                except Exception:
                    return False

            if not channel:
                return False

            try:
                embed = discord.Embed(
                    title=f"🎮 Minecraft Server Found: {server_info['ip']}:{server_info['port']}",
                    description=f"Found an open Minecraft server at {server_info['ip']}:{server_info['port']}",
                    color=discord.Color.green()
                )
                embed.add_field(name="Version", value=server_info['version'], inline=True)
                embed.add_field(name="Players", value=f"{server_info['players_online']}/{server_info['players_max']}", inline=True)
                embed.add_field(name="Latency", value=f"{server_info['latency_ms']}ms", inline=True)
                embed.add_field(name="Possible Whitelist", value="Yes" if server_info['possible_whitelist'] else "No/Unknown", inline=True)

                description = str(server_info['description'])
                if len(description) > 1024:
                    description = description[:1021] + "..."
                embed.add_field(name="Description", value=description, inline=False)

                if 'player_samples' in server_info and server_info['player_samples']:
                    player_names = ', '.join([player['name'] for player in server_info['player_samples']])
                    if len(player_names) > 1024:
                        player_names = player_names[:1021] + "..."
                    embed.add_field(name="Online Players", value=player_names, inline=False)

                self.logger.info(f"Sending embed message to channel {channel.name}")
                await channel.send(embed=embed)
                self.logger.info("Discord message sent successfully")
                return True
            except Exception:
                return False

        future = asyncio.run_coroutine_threadsafe(send_embed_async(), self.loop)
        try:
            result = future.result(timeout=10)
            if not result:
                self._print_server_info_to_console(server_info)
            return result
        except Exception:
            self._print_server_info_to_console(server_info)
            return False

    def _print_server_info_to_console(self, server_info):
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
