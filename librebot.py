import discord
from discord import app_commands, ui
from discord.ext import commands
import sqlite3
import random
import asyncio
import re
import time
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import os

# Ładowanie tokenu
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Konfiguracja bota
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Szyfrowanie
if not os.path.exists('encryption_key.key'):
    key = Fernet.generate_key()
    with open('encryption_key.key', 'wb') as f:
        f.write(key)
else:
    with open('encryption_key.key', 'rb') as f:
        key = f.read()
cipher = Fernet(key)

# Inicjalizacja bazy
conn = sqlite3.connect('librebot_data.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, xp INTEGER, level INTEGER, coins INTEGER, warns INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS banned_words (word TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY, 
    mod_channel_id INTEGER, 
    alert_channel_id INTEGER, 
    ticket_role_id INTEGER, 
    ticket_message_id INTEGER,
    welcome_channel_id INTEGER,
    welcome_message TEXT,
    welcome_embed INTEGER,
    farewell_channel_id INTEGER,
    farewell_message TEXT,
    farewell_embed INTEGER
)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS shop (item_id INTEGER PRIMARY KEY, name TEXT, price INTEGER, role_id INTEGER)''')
try:
    cursor.execute('ALTER TABLE users ADD COLUMN warns INTEGER')
except sqlite3.OperationalError:
    pass
try:
    cursor.execute('ALTER TABLE settings ADD COLUMN welcome_channel_id INTEGER')
    cursor.execute('ALTER TABLE settings ADD COLUMN welcome_message TEXT')
    cursor.execute('ALTER TABLE settings ADD COLUMN welcome_embed INTEGER')
    cursor.execute('ALTER TABLE settings ADD COLUMN farewell_channel_id INTEGER')
    cursor.execute('ALTER TABLE settings ADD COLUMN farewell_message TEXT')
    cursor.execute('ALTER TABLE settings ADD COLUMN farewell_embed INTEGER')
except sqlite3.OperationalError:
    pass
conn.commit()

# Cache floodu
flood_cache = {}

# Start bota
@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user} 😈')
    await bot.tree.sync()

# Wiadomości powitalne
@bot.event
async def on_member_join(member):
    cursor.execute('SELECT welcome_channel_id, welcome_message, welcome_embed FROM settings WHERE guild_id = ?', (member.guild.id,))
    settings = cursor.fetchone()
    if settings and settings[0]:
        channel = member.guild.get_channel(settings[0])
        if channel:
            message = settings[1].replace("{user}", member.mention).replace("{server}", member.guild.name)
            if settings[2]:  # Użyj embeda
                embed = discord.Embed(description=message, color=0x00ff00)
                embed.set_author(name=f"Witaj, {member.name}!", icon_url=member.avatar.url if member.avatar else None)
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")  # Zmień na swoje
                embed.set_footer(text="LibreBot - Cześć na serwerze! 😈")
                await channel.send(embed=embed)
            else:
                await channel.send(message)

# Wiadomości pożegnalne
@bot.event
async def on_member_remove(member):
    cursor.execute('SELECT farewell_channel_id, farewell_message, farewell_embed FROM settings WHERE guild_id = ?', (member.guild.id,))
    settings = cursor.fetchone()
    if settings and settings[0]:
        channel = member.guild.get_channel(settings[0])
        if channel:
            message = settings[1].replace("{user}", member.name).replace("{server}", member.guild.name)
            if settings[2]:  # Użyj embeda
                embed = discord.Embed(description=message, color=0x00ff00)
                embed.set_author(name=f"Żegnaj, {member.name}!", icon_url=member.avatar.url if member.avatar else None)
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")  # Zmień na swoje
                embed.set_footer(text="LibreBot - Do zobaczenia! 😈")
                await channel.send(embed=embed)
            else:
                await channel.send(message)

# Moderacja
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    words = re.split(r'\s+', message.content.lower().replace(' ', ''))
    cursor.execute('SELECT word FROM banned_words')
    banned_words = [row[0] for row in cursor.fetchall()]
    if any(word in banned_words for word in words):
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, chill z wulgaryzmami! 😈")
            await add_warn(message.author, message.guild, "Wulgaryzmy")
        except discord.Forbidden:
            await message.channel.send("Brak uprawnień do usuwania! 😢")
    user_id = message.author.id
    if user_id not in flood_cache:
        flood_cache[user_id] = []
    flood_cache[user_id].append(time.time())
    flood_cache[user_id] = [t for t in flood_cache[user_id] if time.time() - t < 10]
    if len(flood_cache[user_id]) > 5:
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, wyluzuj z floodem! 😎")
            await add_warn(message.author, message.guild, "Flood")
        except discord.Forbidden:
            pass
    if 'discord.gg' in message.content.lower():
        try:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, bez reklam! 😜")
            await add_warn(message.author, message.guild, "Reklama")
        except discord.Forbidden:
            pass
    cursor.execute('SELECT xp, level, coins, warns FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if user:
        new_xp = user[0] + random.randint(5, 15)
        new_level = new_xp // 100
        new_coins = user[2] + (new_xp // 100 - user[1]) * 10
        cursor.execute('UPDATE users SET xp = ?, level = ?, coins = ?, warns = COALESCE(warns, 0) WHERE user_id = ?', 
                      (new_xp, new_level, new_coins, user_id))
    else:
        cursor.execute('INSERT INTO users (user_id, xp, level, coins, warns) VALUES (?, ?, ?, ?, ?)', 
                      (user_id, 10, 1, 10, 0))
    conn.commit()
    await bot.process_commands(message)

async def add_warn(member, guild, reason):
    cursor.execute('SELECT warns FROM users WHERE user_id = ?', (member.id,))
    warns = cursor.fetchone()
    warns = warns[0] if warns else 0
    warns += 1
    cursor.execute('UPDATE users SET warns = ? WHERE user_id = ?', (warns, member.id))
    conn.commit()
    cursor.execute('SELECT mod_channel_id FROM settings WHERE guild_id = ?', (guild.id,))
    mod_channel_id = cursor.fetchone()
    if mod_channel_id:
        mod_channel = guild.get_channel(mod_channel_id[0])
        if mod_channel:
            await mod_channel.send(f"{member.mention} dostał warn ({warns}/5): {reason}")
    if warns == 3:
        await member.timeout(timedelta(hours=1), reason="3 warny: auto-mute")
        await mod_channel.send(f"{member.mention} wyciszony na 1h (3 warny). 😶")
    elif warns >= 5:
        await member.ban(reason="5 warnów: auto-ban")
        await mod_channel.send(f"{member.mention} zbanowany (5 warnów). 🚫")

# Komendy moderacyjne
@bot.tree.command(name="kick", description="Wyrzuca użytkownika")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Brak powodu"):
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"{member.mention} wyrzucony: {reason}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Brak uprawnień! 😢", ephemeral=True)

@bot.tree.command(name="mute", description="Wycisza użytkownika")
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "Brak powodu"):
    try:
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f"{member.mention} wyciszony na {minutes} minut: {reason}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Brak uprawnień! 😢", ephemeral=True)

@bot.tree.command(name="warn", description="Ostrzega użytkownika")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Brak powodu"):
    try:
        await add_warn(member, interaction.guild, reason)
        await interaction.response.send_message(f"{member.mention} ostrzeżony: {reason}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Brak uprawnień! 😢", ephemeral=True)

@bot.tree.command(name="ban", description="Banuje użytkownika")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Brak powodu"):
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"{member.mention} zbanowany: {reason}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Brak uprawnień! 😢", ephemeral=True)

# Dodawanie LibreCoins
@bot.tree.command(name="addcoins", description="Dodaj LibreCoins (mod only)")
async def addcoins(interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Brak powodu"):
    cursor.execute('SELECT ticket_role_id FROM settings WHERE guild_id = ?', (interaction.guild.id,))
    mod_role_id = cursor.fetchone()
    if not mod_role_id or not mod_role_id[0]:
        await interaction.response.send_message("Rola modów nie skonfigurowana! Użyj /ticket_setup.", ephemeral=True)
        return
    mod_role = interaction.guild.get_role(mod_role_id[0])
    if not mod_role or mod_role not in interaction.user.roles:
        await interaction.response.send_message("Brak uprawnień! 😢", ephemeral=True)
        return
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (member.id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute('INSERT INTO users (user_id, xp, level, coins, warns) VALUES (?, ?, ?, ?, ?)', 
                      (member.id, 0, 1, amount, 0))
    else:
        cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (amount, member.id))
    conn.commit()
    cursor.execute('SELECT mod_channel_id FROM settings WHERE guild_id = ?', (interaction.guild.id,))
    mod_channel_id = cursor.fetchone()
    if mod_channel_id:
        mod_channel = interaction.guild.get_channel(mod_channel_id[0])
        if mod_channel:
            embed = discord.Embed(title="💸 Dodano LibreCoins", color=0x00ff00)
            embed.add_field(name="Użytkownik", value=member.mention, inline=False)
            embed.add_field(name="Ilość", value=f"{amount} LC", inline=True)
            embed.add_field(name="Powód", value=reason, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.set_footer(text="LibreBot - Ekonomia! 😈")
            await mod_channel.send(embed=embed)
    await interaction.response.send_message(f"Dodano {amount} LC dla {member.mention}: {reason} 💸", ephemeral=True)

# System XP
@bot.tree.command(name="rank", description="Sprawdź poziom")
async def rank(interaction: discord.Interaction):
    cursor.execute('SELECT xp, level, coins, warns FROM users WHERE user_id = ?', (interaction.user.id,))
    user = cursor.fetchone()
    if user:
        embed = discord.Embed(title=f"🔥 Staty {interaction.user.name}", color=0x00ff00)
        embed.add_field(name="XP", value=user[0], inline=True)
        embed.add_field(name="Poziom", value=user[1], inline=True)
        embed.add_field(name="LibreCoins", value=user[2], inline=True)
        embed.add_field(name="Warny", value=user[3] if user[3] is not None else 0, inline=True)
        embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else "https://cdn.discordapp.com/embed/avatars/0.png")
        embed.set_footer(text="LibreBot - Król Discorda! 😈")
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("Brak danych, napisz coś! 😎", ephemeral=True)

# Ekonomia
@bot.tree.command(name="pay", description="Przelej LibreCoins")
async def pay(interaction: discord.Interaction, member: discord.Member, amount: int):
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (interaction.user.id,))
    sender = cursor.fetchone()
    if not sender or sender[0] < amount:
        await interaction.response.send_message("Za mało LibreCoins! 😜", ephemeral=True)
        return
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (member.id,))
    receiver = cursor.fetchone()
    if not receiver:
        await interaction.response.send_message("Ten user nie ma konta! 😢", ephemeral=True)
        return
    cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (amount, interaction.user.id))
    cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (amount, member.id))
    conn.commit()
    await interaction.response.send_message(f"Przelano {amount} LC do {member.mention}! 💸", ephemeral=True)

@bot.tree.command(name="shop", description="Sprawdź sklep")
async def shop(interaction: discord.Interaction):
    cursor.execute('SELECT item_id, name, price, role_id FROM shop')
    items = cursor.fetchall()
    if not items:
        await interaction.response.send_message("Sklep pusty! 😢", ephemeral=True)
        return
    embed = discord.Embed(title="🏬 Sklep LibreBot", color=0x00ff00)
    for idx, item in enumerate(items, 1):
        embed.add_field(name=f"{idx}. {item[1]}", value=f"Cena: {item[2]} LC", inline=False)
    embed.set_footer(text="Użyj /buy [numer lub nazwa]! 😎")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Kup przedmiot")
@app_commands.autocomplete(item=app_commands.Choice(name="item", value="item"))
async def buy(interaction: discord.Interaction, item: str):
    cursor.execute('SELECT item_id, name, price, role_id FROM shop')
    items = cursor.fetchall()
    selected_item = None
    if item.isdigit():
        idx = int(item) - 1
        if 0 <= idx < len(items):
            selected_item = items[idx]
    else:
        for it in items:
            if it[1].lower() == item.lower():
                selected_item = it
                break
    if not selected_item:
        await interaction.response.send_message("Nie znaleziono przedmiotu! Sprawdź /shop. 😢", ephemeral=True)
        return
    item_id, name, price, role_id = selected_item
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (interaction.user.id,))
    user = cursor.fetchone()
    if not user or user[0] < price:
        await interaction.response.send_message("Za mało LibreCoins! 😜", ephemeral=True)
        return
    cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (price, interaction.user.id))
    if role_id:
        role = interaction.guild.get_role(role_id)
        if role:
            await interaction.user.add_roles(role)
    conn.commit()
    await interaction.response.send_message(f"Kupiłeś **{name}** za {price} LC! 🎉", ephemeral=True)

@buy.autocomplete('item')
async def buy_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice]:
    cursor.execute('SELECT name FROM shop')
    items = [row[0] for row in cursor.fetchall()]
    choices = [app_commands.Choice(name=f"{idx + 1}. {item}", value=str(idx + 1)) for idx, item in enumerate(items)]
    choices += [app_commands.Choice(name=item, value=item) for item in items]
    return [choice for choice in choices if current.lower() in choice.name.lower()][:25]

# Blackjack
@bot.tree.command(name="blackjack", description="Zagraj w blackjacka")
async def blackjack(interaction: discord.Interaction, bet: int):
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (interaction.user.id,))
    user = cursor.fetchone()
    if not user or user[0] < bet:
        await interaction.response.send_message("Za mało LibreCoins! 😜", ephemeral=True)
        return
    player_cards = [random.randint(1, 11), random.randint(1, 11)]
    bot_cards = [random.randint(1, 11), random.randint(1, 11)]
    player_total = sum(player_cards)
    bot_total = bot_cards[0]
    class BlackjackButtons(ui.View):
        def __init__(self):
            super().__init__(timeout=30)
        @ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="✅")
        async def hit_button(self, interaction: discord.Interaction, button: ui.Button):
            nonlocal player_cards, player_total
            player_cards.append(random.randint(1, 11))
            player_total = sum(player_cards)
            if player_total > 21:
                cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (bet, interaction.user.id))
                conn.commit()
                embed = discord.Embed(title="🎰 Blackjack - Wynik", color=0x00ff00)
                embed.add_field(name="Twoje karty", value=f"{player_cards} (Suma: {player_total})", inline=False)
                embed.add_field(name="Karty bota", value=f"{bot_cards} (Suma: {sum(bot_cards)})", inline=False)
                embed.add_field(name="Wynik", value=f"Przegrałeś! -{bet} LC 😢", inline=False)
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
                embed.set_footer(text="LibreBot - Graj odpowiedzialnie! 😈")
                await interaction.response.edit_message(embed=embed, view=None)
                self.stop()
                return
            embed = discord.Embed(title="🎰 Blackjack", color=0x00ff00)
            embed.add_field(name="Twoje karty", value=f"{player_cards} (Suma: {player_total})", inline=False)
            embed.add_field(name="Karty bota", value=f"[{bot_cards[0]}, ?]", inline=False)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
            await interaction.response.edit_message(embed=embed, view=self)
        @ui.button(label="Stand", style=discord.ButtonStyle.red, emoji="❌")
        async def stand_button(self, interaction: discord.Interaction, button: ui.Button):
            nonlocal bot_total, bot_cards
            while bot_total < 17:
                bot_cards.append(random.randint(1, 11))
                bot_total = sum(bot_cards)
            embed = discord.Embed(title="🎰 Blackjack - Wynik", color=0x00ff00)
            embed.add_field(name="Twoje karty", value=f"{player_cards} (Suma: {player_total})", inline=False)
            embed.add_field(name="Karty bota", value=f"{bot_cards} (Suma: {bot_total})", inline=False)
            if bot_total > 21 or player_total > bot_total:
                cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (bet, interaction.user.id))
                conn.commit()
                embed.add_field(name="Wynik", value=f"Wygrałeś! +{bet} LC 🎉", inline=False)
            elif player_total == bot_total:
                embed.add_field(name="Wynik", value="Remis! 😎", inline=False)
            else:
                cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (bet, interaction.user.id))
                conn.commit()
                embed.add_field(name="Wynik", value=f"Przegrałeś! -{bet} LC 😢", inline=False)
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
            embed.set_footer(text="LibreBot - Graj odpowiedzialnie! 😈")
            await interaction.response.edit_message(embed=embed, view=None)
            self.stop()
    embed = discord.Embed(title="🎰 Blackjack", color=0x00ff00)
    embed.add_field(name="Twoje karty", value=f"{player_cards} (Suma: {player_total})", inline=False)
    embed.add_field(name="Karty bota", value=f"[{bot_cards[0]}, ?]", inline=False)
    embed.add_field(name="Akcje", value="✅ Hit | ❌ Stand", inline=False)
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
    embed.set_footer(text="LibreBot - Graj odpowiedzialnie! 😈")
    await interaction.response.send_message(embed=embed, view=BlackjackButtons())

# Ruletka
@bot.tree.command(name="roulette", description="Zagraj w ruletkę")
async def roulette(interaction: discord.Interaction, bet: int, choice: str):
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (interaction.user.id,))
    user = cursor.fetchone()
    if not user or user[0] < bet:
        await interaction.response.send_message("Za mało LibreCoins! 😜", ephemeral=True)
        return
    valid_choices = ['czerwone', 'czarne'] + [str(i) for i in range(1, 37)]
    if choice.lower() not in valid_choices:
        await interaction.response.send_message("Wybierz: czerwone, czarne lub 1-36! 😎", ephemeral=True)
        return
    result = random.randint(1, 36)
    red_numbers = [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]
    color = 'czerwone' if result in red_numbers else 'czarne'
    embed = discord.Embed(title="🎡 Ruletka", color=0x00ff00)
    embed.add_field(name="Wynik", value=f"Wypadło: {result} ({color})", inline=False)
    if choice.lower() == str(result):
        winnings = bet * 36
        cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (winnings - bet, interaction.user.id))
        conn.commit()
        embed.add_field(name="Wynik", value=f"Wygrałeś! +{winnings} LC 🎉", inline=False)
    elif choice.lower() in ['czerwone', 'czarne'] and choice.lower() == color:
        winnings = bet * 2
        cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (winnings - bet, interaction.user.id))
        conn.commit()
        embed.add_field(name="Wynik", value=f"Wygrałeś! +{winnings} LC 🎉", inline=False)
    else:
        cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (bet, interaction.user.id))
        conn.commit()
        embed.add_field(name="Wynik", value=f"Przegrałeś! -{bet} LC 😢", inline=False)
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
    embed.set_footer(text="LibreBot - Kręć i wygrywaj! 😈")
    await interaction.response.send_message(embed=embed)

# Poker
@bot.tree.command(name="poker", description="Zagraj w pokera za LibreCoins")
async def poker(interaction: discord.Interaction, bet: int):
    cursor.execute('SELECT coins FROM users WHERE user_id = ?', (interaction.user.id,))
    user = cursor.fetchone()
    if not user or user[0] < bet:
        await interaction.response.send_message("Nie masz tyle LibreCoins, ziom! 😜", ephemeral=True)
        return
    player_cards = [random.randint(1, 13), random.randint(1, 13)]
    bot_cards = [random.randint(1, 13), random.randint(1, 13)]
    embed = discord.Embed(title="🃏 Poker", color=0x00ff00)
    embed.add_field(name="Twoje karty", value=f"{player_cards}", inline=False)
    embed.add_field(name="Karty bota", value=f"{bot_cards}", inline=False)
    player_score = max(player_cards)
    bot_score = max(bot_cards)
    if player_score > bot_score:
        cursor.execute('UPDATE users SET coins = coins + ? WHERE user_id = ?', (bet, interaction.user.id))
        conn.commit()
        embed.add_field(name="Wynik", value=f"Wygrałeś, królu! +{bet} LC 🎉", inline=False)
    elif player_score == bot_score:
        embed.add_field(name="Wynik", value="Remis! 😎", inline=False)
    else:
        cursor.execute('UPDATE users SET coins = coins - ? WHERE user_id = ?', (bet, interaction.user.id))
        conn.commit()
        embed.add_field(name="Wynik", value=f"Przegrałeś! -{bet} LC 😢", inline=False)
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
    embed.set_footer(text="LibreBot - Pokerowy mistrz! 😈")
    await interaction.response.send_message(embed=embed)

# System ticketów
class TicketButton(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="Stwórz Ticket", style=discord.ButtonStyle.green, emoji="🎫")
    async def create_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        cursor.execute('SELECT ticket_role_id FROM settings WHERE guild_id = ?', (interaction.guild.id,))
        settings = cursor.fetchone()
        if not settings or not settings[0]:
            await interaction.response.send_message("Tickety nie skonfigurowane! Użyj /ticket_setup.", ephemeral=True)
            return
        role = interaction.guild.get_role(settings[0])
        if not role:
            await interaction.response.send_message("Błąd roli adminów! Skontaktuj się z adminem.", ephemeral=True)
            return
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            role: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }
        channel = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites)
        embed = discord.Embed(title="🎫 Nowy Ticket", description=f"{interaction.user.mention} stworzył ticket. Napisz, w czym pomóc!", color=0x00ff00)
        embed.add_field(name="Akcje", value="Kliknij 🔒, by zamknąć ticket", inline=False)
        embed.set_footer(text="LibreBot 😈")
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
        await channel.send(embed=embed, view=TicketCloseButton(interaction.user.id, role.id))
        await interaction.response.send_message(f"Ticket utworzony: {channel.mention}", ephemeral=True)

class TicketCloseButton(ui.View):
    def __init__(self, creator_id, mod_role_id):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.mod_role_id = mod_role_id
    @ui.button(label="Zamknij Ticket", style=discord.ButtonStyle.red, emoji="🔒")
    async def close_ticket_button(self, interaction: discord.Interaction, button: ui.Button):
        mod_role = interaction.guild.get_role(self.mod_role_id)
        if interaction.user.id != self.creator_id and (not mod_role or mod_role not in interaction.user.roles):
            await interaction.response.send_message("Brak uprawnień! 😢", ephemeral=True)
            return
        if not interaction.channel.name.startswith("ticket-"):
            await interaction.response.send_message("To nie ticket! 😜", ephemeral=True)
            return
        cursor.execute('SELECT mod_channel_id FROM settings WHERE guild_id = ?', (interaction.guild.id,))
        mod_channel_id = cursor.fetchone()
        if mod_channel_id:
            mod_channel = interaction.guild.get_channel(mod_channel_id[0])
            if mod_channel:
                embed = discord.Embed(title="🎫 Ticket Zamknięty", description=f"Ticket {interaction.channel.name} zamknięty przez {interaction.user.mention}.", color=0x00ff00)
                embed.set_footer(text="LibreBot - Porządek! 😈")
                await mod_channel.send(embed=embed)
        await interaction.response.send_message("Ticket zamknięty! 👋", ephemeral=True)
        await interaction.channel.delete()

@bot.tree.command(name="ticket_setup", description="Skonfiguruj tickety")
async def ticket_setup(interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
    try:
        embed = discord.Embed(title="🎫 System Ticketów", description="Kliknij, by stworzyć ticket!", color=0x00ff00)
        embed.set_footer(text="LibreBot - Wsparcie! 😈")
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
        msg = await channel.send(embed=embed, view=TicketButton())
        cursor.execute('INSERT OR REPLACE INTO settings (guild_id, ticket_role_id, ticket_message_id) VALUES (?, ?, ?)', 
                       (interaction.guild.id, role.id, msg.id))
        conn.commit()
        await interaction.response.send_message(f"Tickety skonfigurowane w {channel.mention}! 😎", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Brak uprawnień do wysyłania! 😢", ephemeral=True)

@bot.tree.command(name="ticket_close", description="Zamknij ticket")
async def ticket_close(interaction: discord.Interaction):
    if not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message("To nie ticket! 😜", ephemeral=True)
        return
    cursor.execute('SELECT mod_channel_id FROM settings WHERE guild_id = ?', (interaction.guild.id,))
    mod_channel_id = cursor.fetchone()
    if mod_channel_id:
        mod_channel = interaction.guild.get_channel(mod_channel_id[0])
        if mod_channel:
            embed = discord.Embed(title="🎫 Ticket Zamknięty", description=f"Ticket {interaction.channel.name} zamknięty przez {interaction.user.mention}.", color=0x00ff00)
            embed.set_footer(text="LibreBot - Porządek! 😈")
            await mod_channel.send(embed=embed)
    await interaction.response.send_message("Ticket zamknięty! 👋", ephemeral=True)
    await interaction.channel.delete()

# Konfiguracja powitań
@bot.tree.command(name="welcome_setup", description="Skonfiguruj wiadomość powitalną")
async def welcome_setup(interaction: discord.Interaction, channel: discord.TextChannel, message: str, use_embed: bool = True):
    cursor.execute('INSERT OR REPLACE INTO settings (guild_id, welcome_channel_id, welcome_message, welcome_embed) VALUES (?, ?, ?, ?)', 
                   (interaction.guild.id, channel.id, message, int(use_embed)))
    conn.commit()
    await interaction.response.send_message(f"Wiadomość powitalna ustawiona na kanale {channel.mention}! 😊", ephemeral=True)

# Konfiguracja pożegnań
@bot.tree.command(name="farewell_setup", description="Skonfiguruj wiadomość pożegnalną")
async def farewell_setup(interaction: discord.Interaction, channel: discord.TextChannel, message: str, use_embed: bool = True):
    cursor.execute('INSERT OR REPLACE INTO settings (guild_id, farewell_channel_id, farewell_message, farewell_embed) VALUES (?, ?, ?, ?)', 
                   (interaction.guild.id, channel.id, message, int(use_embed)))
    conn.commit()
    await interaction.response.send_message(f"Wiadomość pożegnalna ustawiona na kanale {channel.mention}! 👋", ephemeral=True)

# Ankieta
@bot.tree.command(name="ankieta", description="Utwórz ankietę")
async def ankieta(interaction: discord.Interaction, pytanie: str):
    embed = discord.Embed(title=f"📊 Ankieta: {pytanie}", color=0x00ff00)
    embed.add_field(name="Opcje", value="✅ Tak | ➖ 50/50 | ❌ Nie", inline=False)
    embed.set_footer(text="Wyniki za 24h | LibreBot 😈")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
    msg = await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    await msg.add_reaction("✅")
    await msg.add_reaction("➖")
    await msg.add_reaction("❌")
    await asyncio.sleep(24 * 3600)
    msg = await interaction.channel.fetch_message(msg.id)
    reactions = {str(r.emoji): r.count - 1 for r in msg.reactions if str(r.emoji) in ["✅", "➖", "❌"]}
    embed.add_field(name="Wyniki", value=f"✅: {reactions.get('✅', 0)}\n➖: {reactions.get('➖', 0)}\n❌: {reactions.get('❌', 0)}", inline=False)
    await interaction.followup.send(embed=embed)

# Ogłoszenia
@bot.tree.command(name="ogloszenie", description="Opublikuj ogłoszenie")
async def ogloszenie(interaction: discord.Interaction, tresc: str, pin: bool = False):
    cursor.execute('SELECT alert_channel_id FROM settings WHERE guild_id = ?', (interaction.guild.id,))
    channel_id = cursor.fetchone()
    if not channel_id or not channel_id[0]:
        await interaction.response.send_message("Kanał ogłoszeń nie skonfigurowany! Użyj /setup.", ephemeral=True)
        return
    channel = interaction.guild.get_channel(channel_id[0])
    if not channel:
        await interaction.response.send_message("Błąd kanału! 😢", ephemeral=True)
        return
    embed = discord.Embed(title="📢 Ogłoszenie", description=tresc, color=0x00ff00, timestamp=datetime.utcnow())
    embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_footer(text="LibreBot - Ważne! 😈")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
    msg = await channel.send(embed=embed)
    if pin:
        await msg.pin()
    await interaction.response.send_message("Ogłoszenie opublikowane! 🎉", ephemeral=True)

# Powiadomienia (placeholder)
@bot.tree.command(name="alert_set_youtube", description="Ustaw powiadomienia YouTube")
async def alert_set_youtube(interaction: discord.Interaction, channel_id: str):
    await interaction.response.send_message("Powiadomienia YouTube w budowie! 😎", ephemeral=True)

@bot.tree.command(name="alert_set_twitch", description="Ustaw powiadomienia Twitch")
async def alert_set_twitch(interaction: discord.Interaction, channel_name: str):
    await interaction.response.send_message("Powiadomienia Twitch w budowie! 😎", ephemeral=True)

# Konfiguracja
class SetupButtons(ui.View):
    def __init__(self):
        super().__init__(timeout=60)
    @ui.button(label="Moderacja", style=discord.ButtonStyle.primary, emoji="🛠")
    async def moderation_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Wpisz zakazane słowo:", ephemeral=True)
        def check_msg(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check_msg)
            cursor.execute('INSERT INTO banned_words (word) VALUES (?)', (msg.content.lower(),))
            conn.commit()
            await interaction.followup.send(f"Dodano: {msg.content} 😈", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Czas minął! 😢", ephemeral=True)
    @ui.button(label="XP i Ekonomia", style=discord.ButtonStyle.primary, emoji="📈")
    async def xp_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Wpisz ID roli dla poziomu 10 (lub 'brak'):", ephemeral=True)
        def check_msg(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check_msg)
            if msg.content.lower() != 'brak':
                role_id = int(msg.content)
                cursor.execute('INSERT OR REPLACE INTO shop (item_id, name, price, role_id) VALUES (?, ?, ?, ?)', 
                              (role_id, f"Rola za poziom 10", 100, role_id))
                conn.commit()
            await interaction.followup.send("Nagroda za poziom 10 ustawiona! 🎉", ephemeral=True)
        except (ValueError, asyncio.TimeoutError):
            await interaction.followup.send("Błąd lub czas minął! 😢", ephemeral=True)
    @ui.button(label="Ogłoszenia", style=discord.ButtonStyle.primary, emoji="🔔")
    async def alerts_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Wpisz kanał dla ogłoszeń (np. #ogłoszenia):", ephemeral=True)
        def check_msg(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check_msg)
            channel = discord.utils.get(interaction.guild.text_channels, mention=msg.content)
            if not channel:
                await interaction.followup.send("Nie znaleziono kanału! 😢", ephemeral=True)
                return
            cursor.execute('INSERT OR REPLACE INTO settings (guild_id, alert_channel_id) VALUES (?, ?)', 
                          (interaction.guild.id, channel.id))
            conn.commit()
            await interaction.followup.send(f"Ustawiono kanał: {channel.mention} 😎", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Czas minął! 😢", ephemeral=True)
    @ui.button(label="Tickety", style=discord.ButtonStyle.primary, emoji="🎫")
    async def tickets_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Wpisz kanał i rolę (np. '#tickety @Admin'):", ephemeral=True)
        def check_msg(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check_msg)
            args = msg.content.split()
            if len(args) != 2:
                await interaction.followup.send("Wpisz kanał i rolę, np. '#tickety @Admin'! 😢", ephemeral=True)
                return
            channel = discord.utils.get(interaction.guild.text_channels, mention=args[0])
            role = discord.utils.get(interaction.guild.roles, mention=args[1])
            if not channel or not role:
                await interaction.followup.send("Błąd kanału lub roli! 😢", ephemeral=True)
                return
            embed = discord.Embed(title="🎫 System Ticketów", description="Kliknij, by stworzyć ticket!", color=0x00ff00)
            embed.set_footer(text="LibreBot - Wsparcie! 😈")
            embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
            msg = await channel.send(embed=embed, view=TicketButton())
            cursor.execute('INSERT OR REPLACE INTO settings (guild_id, ticket_role_id, ticket_message_id) VALUES (?, ?, ?)', 
                          (interaction.guild.id, role.id, msg.id))
            conn.commit()
            await interaction.followup.send(f"Tickety skonfigurowane w {channel.mention}! 😎", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Czas minął! 😢", ephemeral=True)
    @ui.button(label="Powitania/Pożegnania", style=discord.ButtonStyle.primary, emoji="👋")
    async def welcome_farewell_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("Wpisz kanał, treść powitania i treść pożegnania (np. '#powitania Witaj {user}! Żegnaj {user}!'):", ephemeral=True)
        def check_msg(m):
            return m.author == interaction.user and m.channel == interaction.channel
        try:
            msg = await bot.wait_for('message', timeout=60.0, check=check_msg)
            args = msg.content.split(maxsplit=2)
            if len(args) != 3:
                await interaction.followup.send("Wpisz kanał, powitanie i pożegnanie, np. '#powitania Witaj {user}! Żegnaj {user}!'", ephemeral=True)
                return
            channel = discord.utils.get(interaction.guild.text_channels, mention=args[0])
            if not channel:
                await interaction.followup.send("Błąd kanału! 😢", ephemeral=True)
                return
            welcome_msg, farewell_msg = args[1], args[2]
            cursor.execute('INSERT OR REPLACE INTO settings (guild_id, welcome_channel_id, welcome_message, welcome_embed, farewell_channel_id, farewell_message, farewell_embed) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                          (interaction.guild.id, channel.id, welcome_msg, 1, channel.id, farewell_msg, 1))
            conn.commit()
            await interaction.followup.send(f"Powitania i pożegnania ustawione w {channel.mention}! 😊", ephemeral=True)
        except asyncio.TimeoutError:
            await interaction.followup.send("Czas minął! 😢", ephemeral=True)

@bot.tree.command(name="setup", description="Konfiguracja bota")
async def setup(interaction: discord.Interaction):
    embed = discord.Embed(title="🔧 Konfiguracja LibreBot", description="Wybierz opcję:", color=0x00ff00)
    embed.add_field(name="🛠 Moderacja", value="Słowa zakazane, kanał logów", inline=False)
    embed.add_field(name="📈 XP i Ekonomia", value="Progi poziomów, sklep", inline=False)
    embed.add_field(name="🔔 Ogłoszenia", value="Kanał ogłoszeń", inline=False)
    embed.add_field(name="🎫 Tickety", value="System ticketów", inline=False)
    embed.add_field(name="👋 Powitania/Pożegnania", value="Wiadomości powitalne i pożegnalne", inline=False)
    embed.set_footer(text="LibreBot - Setup! 😈")
    embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")
    await interaction.response.send_message(embed=embed, view=SetupButtons(), ephemeral=True)

# Uruchomienie bota
bot.run(DISCORD_TOKEN)