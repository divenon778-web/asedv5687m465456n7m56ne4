import json
import os
import random
import string
import time
import re

import aiohttp
import cloudscraper
import discord
from discord import app_commands
from discord.ext import commands
import redis

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

DATA_FILE = "vain_data.json"
KEYS_FILE = "keys.json"
COOKIES_FILE = "cookies.json"
ALGO_FILE = "algorithm.json"
CONFIG_FILE = "config.json"

FOUNDER_ROLE_ID = 1492642549058371684

REDIS_URL = os.environ.get("REDIS_URL", None)

redis_client = None
if REDIS_URL:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.6",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://bloxflip.com",
    "Referer": "https://bloxflip.com/mines",
    "sec-ch-ua": '"Chromium";v="148", "Brave";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "sec-gpc": "1",
}


def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)


def load_json(file_path, default=None):
    if default is None:
        default = {}
    if redis_client:
        try:
            data = redis_client.get(f"vainbot:{file_path}")
            if data:
                return json.loads(data)
        except:
            pass
    if not os.path.exists(file_path):
        return default
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except:
        return default


def save_json_remote(file_path, data):
    save_json(file_path, data)
    if redis_client:
        try:
            redis_client.set(f"vainbot:{file_path}", json.dumps(data), ex=86400)
        except:
            pass


async def fetch_history(user_id):
    cookies = load_json(COOKIES_FILE)
    user_cookies = cookies.get(str(user_id), {})

    app_at = user_cookies.get("app_at")
    if not app_at:
        return None

    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )

    headers = HEADERS.copy()
    headers["Cookie"] = f"app.at={app_at}"
    headers["x-currency"] = "FLIPCOINS"

    all_games = []
    seen_uuids = set()
    games_per_page = 100
    max_pages = 5

    for page in range(max_pages):
        url = f"https://bloxflip.com/api/games/mines/history?size={games_per_page}&page={page}&_t={int(time.time())}"

        try:
            response = scraper.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                games = data.get("data", [])

                if not games:
                    break

                for game in games:
                    uuid = game.get("uuid")
                    if uuid and uuid not in seen_uuids:
                        seen_uuids.add(uuid)
                        all_games.append(game)

                if len(games) < games_per_page:
                    break
            else:
                break
        except Exception as e:
            print(f"Error fetching page {page + 1}: {e}")
            break

    if all_games:
        random.shuffle(all_games)
        return all_games
    return None


def is_connected(user_id):
    cookies = load_json(COOKIES_FILE)
    return str(user_id) in cookies and cookies[str(user_id)].get("app_at")


def algorithm_coxymines(history, num_tiles=5):
    board = [0] * 25
    tiles_filled = 0

    for game in history:
        if tiles_filled >= num_tiles:
            break
        uncovered = game.get("uncoveredLocations", [])
        mines = game.get("mineLocations", [])

        for pos in uncovered[:5]:
            if tiles_filled >= num_tiles:
                break
            if 0 <= pos < 25 and board[pos] == 0:
                board[pos] = 1
                tiles_filled += 1

    results = sorted(
        [(i, board[i]) for i in range(25)], key=lambda x: x[1], reverse=True
    )
    return [x[0] for x in results[:num_tiles]]


def algorithm_gridguardian(history, num_tiles=5):
    board = [0] * 25
    n = 0

    def difference(x, y):
        row1, col1 = divmod(x, 5)
        row2, col2 = divmod(y, 5)
        return int(((row1 - row2) ** 2 + (col1 - col2) ** 2) ** 0.5)

    for game in history:
        if n >= num_tiles:
            break
        uncovered = game.get("uncoveredLocations", [])
        mines = game.get("mineLocations", [])

        for i in range(min(len(uncovered), len(mines))):
            if n >= num_tiles:
                break
            val = abs((uncovered[i] - mines[i]) + difference(uncovered[i], mines[i]))
            if 0 <= val < 25 and board[val] == 0:
                board[val] = 1
                n += 1

    results = sorted(
        [(i, board[i]) for i in range(25)], key=lambda x: x[1], reverse=True
    )
    return [x[0] for x in results[:num_tiles]]


def algorithm_patternshift(history, num_tiles=5):
    board = [0] * 25
    n = 0

    def difference(x, y):
        row1, col1 = divmod(x, 5)
        row2, col2 = divmod(y, 5)
        return int(((row1 - row2) ** 2 + (col1 - col2) ** 2) ** 0.5)

    for game in history:
        if n >= num_tiles:
            break
        uncovered = game.get("uncoveredLocations", [])
        mines = game.get("mineLocations", [])

        for i in range(min(len(uncovered), len(mines))):
            if n >= num_tiles:
                break
            val = min(
                abs(uncovered[i] - mines[i] - difference(uncovered[i], mines[i])), 24
            )
            if board[val] == 0:
                board[val] = 1
                n += 1

    results = sorted(
        [(i, board[i]) for i in range(25)], key=lambda x: x[1], reverse=True
    )
    return [x[0] for x in results[:num_tiles]]


def algorithm_logarithm(history, num_tiles=5):
    board = [0] * 25
    n = 0

    for game in history:
        if n >= num_tiles:
            break
        uncovered = game.get("uncoveredLocations", [])
        mines = game.get("mineLocations", [])

        for i in range(min(len(uncovered), len(mines))):
            if n >= num_tiles:
                break
            val = abs(uncovered[i] - mines[i])
            if board[min(val + 1, 24)] == 0:
                board[min(val + 1, 24)] = 1
                n += 1

    results = sorted(
        [(i, board[i]) for i in range(25)], key=lambda x: x[1], reverse=True
    )
    return [x[0] for x in results[:num_tiles]]


def algorithm_nearestneighbors(history, num_tiles=5):
    board = [0] * 25
    n = 0

    all_mines = []
    for game in history:
        all_mines.extend(game.get("mineLocations", []))

    for i in range(len(all_mines) - 1):
        if n >= num_tiles:
            break
        diff = abs(all_mines[i] - all_mines[i + 1])
        spot = min(diff, 24)
        if board[spot] == 0:
            board[spot] = 1
            n += 1

    results = sorted(
        [(i, board[i]) for i in range(25)], key=lambda x: x[1], reverse=True
    )
    return [x[0] for x in results[:num_tiles]]


async def on_ready():
    await tree.sync()
    print(f"Vain is ready! Logged in as {bot.user}")


@tree.command(name="createkey", description="Create a new key")
@app_commands.describe(days="Number of days until expiration")
async def createkey(interaction: discord.Interaction, days: int):
    if not interaction.guild:
        embed = discord.Embed(
            title="GUILD ONLY",
            description="This command can only be used in a server.",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    role = discord.utils.get(interaction.guild.roles, id=FOUNDER_ROLE_ID)

    if role not in interaction.user.roles:
        embed = discord.Embed(
            title="ACCESS DENIED",
            description="You need the **Founder** role to use this command.",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if days < 1:
        embed = discord.Embed(
            title="INVALID DAYS",
            description="Please specify at least 1 day.",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    key = "".join(random.choices(string.ascii_uppercase + string.digits, k=16))
    keys = load_json(KEYS_FILE)
    keys[key] = {
        "created_at": int(time.time()),
        "expires": int(time.time()) + (days * 86400),
        "created_by": str(interaction.user.id),
    }
    save_json_remote(KEYS_FILE, keys)

    embed = discord.Embed(
        title="KEY CREATED",
        description=f"Key: **{key}**\nExpires in **{days}** days",
        color=discord.Color(value=0xFFFFFF),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="claim", description="Claim your key")
@app_commands.describe(key="Your key")
async def claim(interaction: discord.Interaction, key: str):
    keys = load_json(KEYS_FILE)
    key_data = keys.get(key)

    if not key_data:
        embed = discord.Embed(
            title="INVALID KEY",
            description="The key you provided does not exist.",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if key_data.get("claimed_by"):
        embed = discord.Embed(
            title="KEY ALREADY CLAIMED",
            description="This key has already been claimed.",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if time.time() > key_data.get("expires", 0):
        embed = discord.Embed(
            title="KEY EXPIRED",
            description="This key has expired.",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    key_data["claimed_by"] = str(interaction.user.id)
    key_data["claimed_at"] = int(time.time())
    save_json_remote(KEYS_FILE, keys)

    embed = discord.Embed(
        title="KEY CLAIMED",
        description=f"Key claimed successfully! You can now use /connect",
        color=discord.Color(value=0xFFFFFF),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@tree.command(name="connect", description="Connect your Bloxflip account")
@app_commands.describe(app_at="Your app.at cookie from bloxflip.com")
async def connect(interaction: discord.Interaction, app_at: str):
    keys = load_json(KEYS_FILE)
    has_valid_key = False

    for key, data in keys.items():
        if data.get("claimed_by") == str(interaction.user.id):
            if data.get("claimed_at") and time.time() <= data["expires"]:
                has_valid_key = True
                break

    if not has_valid_key:
        embed = discord.Embed(
            title="KEY REQUIRED",
            description="You need to claim a valid key first using /claim",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    cookie_data = load_json(COOKIES_FILE)
    cookie_data[str(interaction.user.id)] = {
        "app_at": app_at,
        "connected_at": int(time.time()),
    }
    save_json_remote(COOKIES_FILE, cookie_data)

    embed = discord.Embed(
        title="CONNECTED SUCCESSFULLY",
        description=f"**{interaction.user.name}** is now connected to Bloxflip!",
        color=discord.Color(value=0xFFFFFF),
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


class AlgorithmSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="CoxyMines"),
            discord.SelectOption(label="GridGuardian"),
            discord.SelectOption(label="PatternShift"),
            discord.SelectOption(label="Logarithm"),
            discord.SelectOption(label="NearestNeighbors"),
        ]
        super().__init__(
            placeholder="Select an algorithm",
            options=options,
            custom_id="algorithm_select",
        )

    async def callback(self, interaction: discord.Interaction):
        algo_choice = self.values[0].lower()

        algo_data = load_json(ALGO_FILE)
        algo_data[str(interaction.user.id)] = algo_choice
        save_json_remote(ALGO_FILE, algo_data)

        embed = discord.Embed(
            title="ALGORITHM SELECTED",
            description=f"Algorithm set to: **{self.values[0]}**",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.edit_message(embed=embed, view=None)


class AlgorithmView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(AlgorithmSelect())


class ConfigSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=str(i), description=f"{i} safe spots")
            for i in range(1, 25)
        ]
        super().__init__(
            placeholder="Select number of safe spots",
            options=options,
            custom_id="config_select",
        )

    async def callback(self, interaction: discord.Interaction):
        safe_spots = int(self.values[0])

        config_data = load_json(CONFIG_FILE)
        if str(interaction.user.id) not in config_data:
            config_data[str(interaction.user.id)] = {}
        config_data[str(interaction.user.id)]["safe_spots"] = safe_spots
        save_json_remote(CONFIG_FILE, config_data)

        embed = discord.Embed(
            title="CONFIG UPDATED",
            description=f"Safe spots set to **{safe_spots}**",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.edit_message(embed=embed, view=None)


class ConfigView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(ConfigSelect())


@tree.command(name="config", description="Configure your settings")
async def config(interaction: discord.Interaction):
    if not is_connected(interaction.user.id):
        embed = discord.Embed(
            title="NOT CONNECTED",
            description="Please connect your account first using /connect",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    config_data = load_json(CONFIG_FILE)
    user_config = config_data.get(str(interaction.user.id), {})
    current_safe_spots = user_config.get("safe_spots", 5)
    algo_data = load_json(ALGO_FILE)
    current_algo = algo_data.get(str(interaction.user.id), "coxymines")

    embed = discord.Embed(
        title="BOT CONFIG",
        description=f"**Current Algorithm:** {current_algo.upper()}\n**Current Safe Spots:** {current_safe_spots}",
        color=discord.Color(value=0xFFFFFF),
    )
    embed.add_field(name="Safe Spots", value="Select below to change", inline=False)
    await interaction.response.send_message(
        embed=embed, view=ConfigView(), ephemeral=True
    )


@tree.command(name="algorithms", description="Select your prediction algorithm")
async def algorithms(interaction: discord.Interaction):
    if not is_connected(interaction.user.id):
        embed = discord.Embed(
            title="NOT CONNECTED",
            description="Please connect your account first using /connect",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="SELECT ALGORITHM",
        description="Choose your prediction method",
        color=discord.Color(value=0xFFFFFF),
    )
    await interaction.response.send_message(
        embed=embed, view=AlgorithmView(), ephemeral=True
    )


@tree.command(name="mines", description="Predict mines")
async def mines(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not is_connected(interaction.user.id):
        embed = discord.Embed(
            title="NOT CONNECTED",
            description="Please connect your account first using /connect",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    algo_data = load_json(ALGO_FILE)
    algo_choice = algo_data.get(str(interaction.user.id), "coxymines")

    config_data = load_json(CONFIG_FILE)
    user_config = config_data.get(str(interaction.user.id), {})
    safe_spots = user_config.get("safe_spots", 5)

    history = await fetch_history(interaction.user.id)

    if not history:
        embed = discord.Embed(
            title="HISTORY ERROR",
            description="Could not fetch game history. Make sure your connection is valid.",
            color=discord.Color(value=0xFFFFFF),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return

    if algo_choice == "coxymines":
        predictions = algorithm_coxymines(history, safe_spots)
    elif algo_choice == "gridguardian":
        predictions = algorithm_gridguardian(history, safe_spots)
    elif algo_choice == "patternshift":
        predictions = algorithm_patternshift(history, safe_spots)
    elif algo_choice == "logarithm":
        predictions = algorithm_logarithm(history, safe_spots)
    elif algo_choice == "nearestneighbors":
        predictions = algorithm_nearestneighbors(history, safe_spots)
    else:
        predictions = algorithm_coxymines(history, safe_spots)

    grid_desc = ""
    for row in range(5):
        row_tiles = []
        for col in range(5):
            tile_num = row * 5 + col
            if tile_num in predictions:
                row_tiles.append("    ✅    ")
            else:
                row_tiles.append("    ❌    ")
        grid_desc += "".join(row_tiles) + "\n"

    embed = discord.Embed(
        title="MINES PREDICTION",
        description=f"**Algorithm:** {algo_choice.upper()}\n**Safe Spots:** {safe_spots}\n\n{grid_desc}",
        color=discord.Color(value=0xFFFFFF),
    )
    embed.add_field(
        name="Legend",
        value="✅ = Safe\n❌ = Danger",
        inline=False,
    )
    await interaction.followup.send(embed=embed, ephemeral=True)


@tree.command(name="disconnect", description="Disconnect your Bloxflip account")
async def disconnect(interaction: discord.Interaction):
    cookies = load_json(COOKIES_FILE)

    if str(interaction.user.id) in cookies:
        del cookies[str(interaction.user.id)]
        save_json_remote(COOKIES_FILE, cookies)

        algo_data = load_json(ALGO_FILE)
        if str(interaction.user.id) in algo_data:
            del algo_data[str(interaction.user.id)]
            save_json_remote(ALGO_FILE, algo_data)

        config_data = load_json(CONFIG_FILE)
        if str(interaction.user.id) in config_data:
            del config_data[str(interaction.user.id)]
            save_json_remote(CONFIG_FILE, config_data)

        embed = discord.Embed(
            title="DISCONNECTED",
            description="Your Bloxflip account has been disconnected.",
            color=discord.Color(value=0xFFFFFF),
        )
    else:
        embed = discord.Embed(
            title="NOT CONNECTED",
            description="You are not connected to any account.",
            color=discord.Color(value=0xFFFFFF),
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.event(on_ready)

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN environment variable not set!")
else:
    bot.run(DISCORD_TOKEN)
