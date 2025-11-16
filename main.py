
import discord
from discord.ext import commands
import random
import sqlite3

# --- Database setup ---
conn = sqlite3.connect("rng_game.db")

c = conn.cursor()

# --- Achievements setup ---
c.execute("""
CREATE TABLE IF NOT EXISTS achievements (
    user_id INTEGER,
    achievement TEXT,
    date TEXT,
    PRIMARY KEY (user_id, achievement)
)
""")
conn.commit()

# List of achievements: (id, name, description, condition function)
ACHIEVEMENTS = [
    ("first_pull", "First Pull!", "Pull any item for the first time.", lambda stats: stats.get("pulls", 0) >= 1),
    ("ten_pulls", "Ten Pulls!", "Pull 10 items.", lambda stats: stats.get("pulls", 0) >= 10),
    ("hundred_pulls", "Hundred Pulls!", "Pull 100 items.", lambda stats: stats.get("pulls", 0) >= 100),
    ("rare_pull", "Rare Find!", "Pull a rare or higher item.", lambda stats: stats.get("rares", 0) >= 1),
    ("legendary_pull", "Legendary!", "Pull a legendary or higher item.", lambda stats: stats.get("legendaries", 0) >= 1),
]

# Helper to get user achievement ids
def get_user_achievements(user_id):
    c.execute("SELECT achievement FROM achievements WHERE user_id = ?", (user_id,))
    return set(row[0] for row in c.fetchall())



async def check_and_award_achievements(user_id, stats, interaction=None):
    awarded = []
    user_achievements = get_user_achievements(user_id)
    now = datetime.datetime.now().isoformat()
    for aid, name, desc, cond in ACHIEVEMENTS:
        if aid not in user_achievements and cond(stats):
            c.execute("INSERT OR IGNORE INTO achievements (user_id, achievement, date) VALUES (?, ?, ?)", (user_id, aid, now))
            awarded.append((name, desc))
    conn.commit()
    # Optionally notify user in Discord
    if interaction and awarded:
        for name, desc in awarded:
            embed = discord.Embed(title=f"🏅 Achievement Unlocked: {name}", description=desc, color=0xffd700)
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception:
                pass


# --- Bot setup ---
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    pulls INTEGER DEFAULT 0,
    coins INTEGER DEFAULT 0,
    last_daily TEXT,
    last_weekly TEXT
)
""")
# --- Daily/Weekly Rewards Commands ---
import datetime

@tree.command(name="daily", description="Claim your daily login reward!")
async def daily(interaction: discord.Interaction):
    user_id = interaction.user.id
    today = datetime.datetime.now().date()
    c.execute("SELECT coins, last_daily FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (user_id, username, coins, last_daily) VALUES (?, ?, ?, ?) ", (user_id, str(interaction.user), 100, str(today)))
        conn.commit()
        coins = 100
        last_daily = None
    else:
        coins, last_daily = row
        if last_daily == str(today):
            embed = discord.Embed(title="Daily Reward", description="You have already claimed your daily reward today!", color=0x00ccff)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        coins = (coins or 0) + 100
        c.execute("UPDATE users SET coins = ?, last_daily = ? WHERE user_id = ?", (coins, str(today), user_id))
        conn.commit()
    embed = discord.Embed(title="Daily Reward", description=f"You claimed 100 coins! Total coins: {coins}", color=0x00ccff)
    await interaction.response.send_message(embed=embed)

@tree.command(name="weekly", description="Claim your weekly login reward!")
async def weekly(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = datetime.datetime.now().isocalendar()
    week_str = f"{now[0]}-W{now[1]}"
    c.execute("SELECT coins, last_weekly FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (user_id, username, coins, last_weekly) VALUES (?, ?, ?, ?) ", (user_id, str(interaction.user), 500, week_str))
        conn.commit()
        coins = 500
        last_weekly = None
    else:
        coins, last_weekly = row
        if last_weekly == week_str:
            embed = discord.Embed(title="Weekly Reward", description="You have already claimed your weekly reward!", color=0x00ccff)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        coins = (coins or 0) + 500
        c.execute("UPDATE users SET coins = ?, last_weekly = ? WHERE user_id = ?", (coins, week_str, user_id))
        conn.commit()
    embed = discord.Embed(title="Weekly Reward", description=f"You claimed 500 coins! Total coins: {coins}", color=0x00ccff)
    await interaction.response.send_message(embed=embed)
c.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    item TEXT,
    rarity TEXT,
    amount INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, item)
)
""")
conn.commit()

# --- Bot setup ---
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

# --- Admin user ID ---
ADMIN_USER_ID = 953772289311248464
def is_admin(interaction):
    return interaction.user.id == ADMIN_USER_ID

# --- Items and rarities ---

# --- Item pool is now stored in the database ---
c.execute("""
CREATE TABLE IF NOT EXISTS items (
    item TEXT PRIMARY KEY,
    rarity TEXT NOT NULL,
    description TEXT,
    image TEXT
)
""")
conn.commit()

# Default items (only insert if table is empty)
c.execute("SELECT COUNT(*) FROM items")
if c.fetchone()[0] == 0:
    default_items = [
        ("laser pointer", "common"),
        ("cappy", "common"),
        ("ó", "uncommon"),
        ("gljj", "uncommon"),
        ("cheese cup", "rare"),
        ("hammer", "rare"),
        ("gumball", "epic"),
        ("confetti cannon", "epic"),
        ("toothpick", "legendary"),
        ("glimmer", "legendary"),
        ("outlet", "mythic"),
        ("button", "mythic"),
        ("floppy disc", "divine"),
        ("pocket watch", "divine"),
        ("fork", "secret"),
        ("aciddrop", "secret"),
    ]
    c.executemany("INSERT INTO items (item, rarity) VALUES (?, ?)", default_items)
    conn.commit()

RARITY_WEIGHTS = {
    "common": 40,
    "uncommon": 25,
    "rare": 15,
    "epic": 8,
    "legendary": 5,
    "mythic": 3,
    "divine": 2,
    "secret": 1,
}

def get_items():
    c.execute("SELECT item, rarity FROM items")
    return c.fetchall()

def get_weighted_item():
    pool = []
    for item, rarity in get_items():
        pool.extend([(item, rarity)] * RARITY_WEIGHTS.get(rarity, 1))
    return random.choice(pool)

# --- Admin item pool management commands ---

# --- Item info command for Discord ---
@tree.command(name="iteminfo", description="Show info about an item.")
@discord.app_commands.describe(item="Item name")
async def iteminfo(interaction: discord.Interaction, item: str):
    c.execute("SELECT rarity, description, image FROM items WHERE item = ?", (item,))
    row = c.fetchone()
    if not row:
        embed = discord.Embed(title="Item Info", description=f"Item '{item}' not found.", color=0xff5555)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    rarity, description, image = row
    embed = discord.Embed(title=f"{item} ({rarity})", description=description or "No description.", color=0x00ccff)
    if image:
        embed.set_image(url=image)
    await interaction.response.send_message(embed=embed)
@tree.command(name="add_item", description="[ADMIN] Add a new item to the item pool.")
@discord.app_commands.describe(item="Item name", rarity="Rarity")
async def add_item(interaction: discord.Interaction, item: str, rarity: str):
    if not is_admin(interaction):
        embed = discord.Embed(title="Unauthorized", description="You are not authorized to use this command.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    c.execute("SELECT 1 FROM items WHERE item = ?", (item,))
    if c.fetchone():
        embed = discord.Embed(title="Error", description="Item already exists.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    c.execute("INSERT INTO items (item, rarity) VALUES (?, ?)", (item, rarity))
    conn.commit()
    embed = discord.Embed(title="Item Added", description=f"Added {item} ({rarity}) to the item pool.", color=0x00ccff)
    await interaction.response.send_message(embed=embed)

@tree.command(name="remove_item", description="[ADMIN] Remove an item from the item pool.")
@discord.app_commands.describe(item="Item name")
async def remove_item(interaction: discord.Interaction, item: str):
    if not is_admin(interaction):
        embed = discord.Embed(title="Unauthorized", description="You are not authorized to use this command.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    c.execute("DELETE FROM items WHERE item = ?", (item,))
    conn.commit()
    embed = discord.Embed(title="Item Removed", description=f"Removed {item} from the item pool.", color=0x00ccff)
    await interaction.response.send_message(embed=embed)

@tree.command(name="edit_item_rarity", description="[ADMIN] Edit the rarity of an item.")
@discord.app_commands.describe(item="Item name", rarity="New rarity")
async def edit_item_rarity(interaction: discord.Interaction, item: str, rarity: str):
    if not is_admin(interaction):
        embed = discord.Embed(title="Unauthorized", description="You are not authorized to use this command.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    c.execute("UPDATE items SET rarity = ? WHERE item = ?", (rarity, item))
    conn.commit()
    embed = discord.Embed(title="Item Updated", description=f"Updated {item} to rarity {rarity}.", color=0x00ccff)
    await interaction.response.send_message(embed=embed)

# --- Helper functions ---


# --- Bot Events ---

# --- Bot Events ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

# DM welcome/help message
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if isinstance(message.channel, discord.DMChannel):
        help_text = (
            "👋 Hi! I'm Tactas RNG. You can use all my slash commands here in DMs, just like in a server!\n"
            "Try /pull, /inventory, /achievements, and more.\n"
            "If you need help, use /help or invite me to your server."
        )
        await message.channel.send(help_text)


@tree.command(name="pull", description="Pull a random item!")
async def pull(interaction: discord.Interaction):
    user_id = interaction.user.id
    username = str(interaction.user)
    item, rarity = get_weighted_item()
    # Add user if not exists
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    # Update pulls
    c.execute("UPDATE users SET pulls = pulls + 1 WHERE user_id = ?", (user_id,))
    # Add item to inventory
    c.execute("SELECT amount FROM inventory WHERE user_id = ? AND item = ?", (user_id, item))
    row = c.fetchone()
    if row:
        c.execute("UPDATE inventory SET amount = amount + 1 WHERE user_id = ? AND item = ?", (user_id, item))
    else:
        c.execute("INSERT INTO inventory (user_id, item, rarity, amount) VALUES (?, ?, ?, 1)", (user_id, item, rarity))
    conn.commit()
    # Fetch description and image
    c.execute("SELECT description, image FROM items WHERE item = ?", (item,))
    desc_row = c.fetchone()
    description = desc_row[0] if desc_row and desc_row[0] else None
    image = desc_row[1] if desc_row and desc_row[1] else None
    # --- Achievement tracking ---
    # Gather stats for achievement conditions
    c.execute("SELECT pulls FROM users WHERE user_id = ?", (user_id,))
    pulls_row = c.fetchone()
    pulls = pulls_row[0] if pulls_row else 0
    # Count rare and legendary pulls
    c.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND (rarity = 'rare' OR rarity = 'epic')", (user_id,))
    rares = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM inventory WHERE user_id = ? AND (rarity = 'legendary' OR rarity = 'mythic' OR rarity = 'divine' OR rarity = 'secret')", (user_id,))
    legendaries = c.fetchone()[0]
    stats = {"pulls": pulls, "rares": rares, "legendaries": legendaries}
    await interaction.response.send_message(embed=discord.Embed(title="🎲 RNG Pull!", description=f"{interaction.user.mention} pulled:", color=0x00ffcc))
    # Show item embed as followup (to allow achievement popups)
    embed = discord.Embed(title="Item", description=f"**{item}**", color=0x00ffcc)
    embed.add_field(name="Rarity", value=f"`{rarity}`", inline=True)
    if description:
        embed.add_field(name="Description", value=description, inline=False)
    if image:
        embed.set_image(url=image)
    embed.set_footer(text="Good luck on your next pull!")
    await interaction.followup.send(embed=embed)
    # Check and award achievements
    await check_and_award_achievements(user_id, stats, interaction)
    print("Logged pull: ", interaction.user, item, rarity)
# --- Achievements command ---
@tree.command(name="achievements", description="View your achievements and badges!")
async def achievements(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_achievements = get_user_achievements(user_id)
    if not user_achievements:
        embed = discord.Embed(title="Achievements", description="No achievements yet! Pull more items to unlock badges.", color=0x888888)
        await interaction.response.send_message(embed=embed)
        return
    embed = discord.Embed(title=f"{interaction.user.display_name}'s Achievements", color=0xffd700)
    for aid, name, desc, _ in ACHIEVEMENTS:
        if aid in user_achievements:
            embed.add_field(name=f"🏅 {name}", value=desc, inline=False)
    await interaction.response.send_message(embed=embed)


@tree.command(name="inventory", description="View your inventory!")
async def inventory(interaction: discord.Interaction):
    user_id = interaction.user.id
    c.execute("SELECT item, rarity, amount FROM inventory WHERE user_id = ?", (user_id,))
    items = c.fetchall()
    if not items:
        embed = discord.Embed(title="Inventory", description=f"{interaction.user.mention} has no items yet!", color=0xff5555)
        await interaction.response.send_message(embed=embed)
        return
    embed = discord.Embed(title=f"{interaction.user.display_name}'s Inventory", color=0x00ccff)
    for item, rarity, amount in items:
        # Fetch description and image for each item
        c.execute("SELECT description, image FROM items WHERE item = ?", (item,))
        desc_row = c.fetchone()
        description = desc_row[0] if desc_row and desc_row[0] else None
        image = desc_row[1] if desc_row and desc_row[1] else None
        value = f"{rarity} x{amount}"
        if description:
            value += f"\n{description}"
        embed.add_field(name=item, value=value, inline=True)
    # Show image of first item if available
    for item, _, _ in items:
        c.execute("SELECT image FROM items WHERE item = ?", (item,))
        img_row = c.fetchone()
        if img_row and img_row[0]:
            embed.set_image(url=img_row[0])
            break
    await interaction.response.send_message(embed=embed)


@tree.command(name="stats", description="View your pull stats!")
async def stats(interaction: discord.Interaction):
    user_id = interaction.user.id
    c.execute("SELECT pulls FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    pulls = row[0] if row else 0
    embed = discord.Embed(title="Pull Stats", color=0x99ff99)
    embed.add_field(name="User", value=interaction.user.mention, inline=True)
    embed.add_field(name="Total Pulls", value=str(pulls), inline=True)
    await interaction.response.send_message(embed=embed)

# To run the bot, put your token in a .env file as DISCORD_TOKEN=your_token_here
# To run the bot, put your token in a .env file as DISCORD_TOKEN=your_token_here
@tree.command(name="admin_reset_data", description="[ADMIN] Reset all user and inventory data.")
async def admin_reset_data(interaction: discord.Interaction):
    if not is_admin(interaction):
        embed = discord.Embed(title="Unauthorized", description="You are not authorized to use this command.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    c.execute("DELETE FROM users")
    c.execute("DELETE FROM inventory")
    conn.commit()
    embed = discord.Embed(title="Admin Action", description="All user and inventory data has been reset.", color=0xff8800)
    await interaction.response.send_message(embed=embed)

@tree.command(name="admin_give_item", description="[ADMIN] Give an item to a user.")
@discord.app_commands.describe(user_id="User ID to give item to", item="Item name", amount="Amount to give (default 1)")
async def admin_give_item(interaction: discord.Interaction, user_id: int, item: str, amount: int = 1):
    if not is_admin(interaction):
        embed = discord.Embed(title="Unauthorized", description="You are not authorized to use this command.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    # Find rarity from DB
    c.execute("SELECT rarity FROM items WHERE item = ?", (item,))
    row = c.fetchone()
    if not row:
        embed = discord.Embed(title="Error", description="Item not found in item pool.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    rarity = row[0]
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?) ", (user_id, str(user_id)))
    c.execute("SELECT amount FROM inventory WHERE user_id = ? AND item = ?", (user_id, item))
    row = c.fetchone()
    if row:
        c.execute("UPDATE inventory SET amount = amount + ? WHERE user_id = ? AND item = ?", (amount, user_id, item))
    else:
        c.execute("INSERT INTO inventory (user_id, item, rarity, amount) VALUES (?, ?, ?, ?)", (user_id, item, rarity, amount))
    conn.commit()
    embed = discord.Embed(title="Admin Action", description=f"Gave {amount}x {item} ({rarity}) to user {user_id}.", color=0xff8800)
    await interaction.response.send_message(embed=embed)

@tree.command(name="admin_set_pulls", description="[ADMIN] Set a user's pull count.")
@discord.app_commands.describe(user_id="User ID to set pulls for", pulls="Pull count")
async def admin_set_pulls(interaction: discord.Interaction, user_id: int, pulls: int):
    if not is_admin(interaction):
        embed = discord.Embed(title="Unauthorized", description="You are not authorized to use this command.", color=0xff0000)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?) ", (user_id, str(user_id)))
    c.execute("UPDATE users SET pulls = ? WHERE user_id = ?", (pulls, user_id))
    conn.commit()
    embed = discord.Embed(title="Admin Action", description=f"Set pulls for user {user_id} to {pulls}.", color=0xff8800)
    await interaction.response.send_message(embed=embed)

# To run the bot, put your token in a .env file as DISCORD_TOKEN=your_token_here

import sys
def cli_main():
    print("Tactas RNG CLI Mode\nType 'pull' to pull an item, 'inv' for inventory, 'ach' for achievements, 'exit' to quit.")
    user_id = 1  # Local user
    username = "localuser"
    c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    while True:
        cmd = input("> ").strip().lower()
        if cmd == "pull":
            item, rarity = get_weighted_item()
            c.execute("UPDATE users SET pulls = pulls + 1 WHERE user_id = ?", (user_id,))
            c.execute("SELECT amount FROM inventory WHERE user_id = ? AND item = ?", (user_id, item))
            row = c.fetchone()
            if row:
                c.execute("UPDATE inventory SET amount = amount + 1 WHERE user_id = ? AND item = ?", (user_id, item))
            else:
                c.execute("INSERT INTO inventory (user_id, item, rarity, amount) VALUES (?, ?, ?, 1)", (user_id, item, rarity))
            conn.commit()
            print(f"You pulled: {item} ({rarity})")
        elif cmd == "inv":
            c.execute("SELECT item, rarity, amount FROM inventory WHERE user_id = ?", (user_id,))
            items = c.fetchall()
            if not items:
                print("Inventory is empty.")
            else:
                for item, rarity, amount in items:
                    print(f"{item} ({rarity}) x{amount}")
        elif cmd == "ach":
            user_achievements = get_user_achievements(user_id)
            if not user_achievements:
                print("No achievements yet.")
            else:
                for aid, name, desc, _ in ACHIEVEMENTS:
                    if aid in user_achievements:
                        print(f"🏅 {name}: {desc}")
        elif cmd == "exit":
            print("Goodbye!")
            break
        else:
            print("Commands: pull, inv, ach, exit")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        cli_main()
    else:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            print("Please set DISCORD_TOKEN in your .env file.")
        else:
            bot.run(token)
