import sys
import sqlite3
import subprocess
import threading
import discord
import asyncio
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QListWidget, QMessageBox, QFileDialog, QGroupBox, QGridLayout, QTextEdit, QCheckBox
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve
from dotenv import load_dotenv
import os
import json
from cryptography.fernet import Fernet

# Ładowanie tokenu
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Klient Discorda do pobierania kanałów/ról
intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

class LibreBotGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LibreBot Control Panel 😈")
        self.setGeometry(100, 100, 1000, 750)
        self.bot_process = None
        self.bot_running = False
        self.guilds = []
        self.channels = {}
        self.roles = {}
        self.current_guild_id = None

        # Styling (czytelny, ciemny temat)
        self.setStyleSheet("""
            QMainWindow { background-color: #1E2124; }
            QTabWidget { background-color: #23272A; color: #FFFFFF; }
            QTabBar::tab { 
                background: #2C2F33; 
                color: #99AAB5; 
                padding: 12px 20px; 
                font-size: 14px; 
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { 
                background: #7289DA; 
                color: #FFFFFF; 
                border-bottom: 2px solid #FFFFFF;
            }
            QPushButton { 
                background-color: #7289DA; 
                color: #FFFFFF; 
                border: none; 
                padding: 10px 15px; 
                border-radius: 5px; 
                font-size: 13px;
            }
            QPushButton:hover { background-color: #677BC4; }
            QPushButton:pressed { background-color: #5B6EAE; }
            QLineEdit, QComboBox, QTextEdit { 
                background-color: #2C2F33; 
                color: #FFFFFF; 
                padding: 8px; 
                border: 1px solid #7289DA; 
                border-radius: 5px; 
                font-size: 13px;
            }
            QListWidget { 
                background-color: #2C2F33; 
                color: #FFFFFF; 
                border: 1px solid #7289DA; 
                border-radius: 5px; 
                padding: 5px;
            }
            QLabel { 
                color: #99AAB5; 
                font-size: 13px; 
                font-weight: bold;
            }
            QGroupBox { 
                border: 1px solid #7289DA; 
                border-radius: 5px; 
                margin-top: 10px; 
                font-size: 14px; 
                color: #FFFFFF;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                subcontrol-position: top left; 
                padding: 5px 10px; 
                color: #7289DA;
            }
            QStatusBar { 
                background-color: #23272A; 
                color: #99AAB5; 
                font-size: 12px;
            }
        """)

        # Status bar
        self.statusBar().showMessage("LibreBot: Wyłączony")

        # Główny widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # Wybór serwera
        self.guild_group = QGroupBox("Serwer")
        self.guild_layout = QHBoxLayout()
        self.guild_selector_label = QLabel("Wybierz serwer:")
        self.guild_selector = QComboBox()
        self.guild_selector.setToolTip("Wybierz serwer, który chcesz skonfigurować")
        self.guild_selector.currentIndexChanged.connect(self.update_guild)
        self.guild_layout.addWidget(self.guild_selector_label)
        self.guild_layout.addWidget(self.guild_selector, stretch=1)
        self.guild_group.setLayout(self.guild_layout)
        self.main_layout.addWidget(self.guild_group)

        # Zakładki
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # Zakładka Moderacja
        self.mod_tab = QWidget()
        self.mod_layout = QVBoxLayout()
        self.mod_layout.setSpacing(10)
        # Sekcja słów zakazanych
        self.mod_words_group = QGroupBox("Słowa zakazane")
        self.mod_words_layout = QGridLayout()
        self.mod_word_label = QLabel("Dodaj słowo:")
        self.mod_word_input = QLineEdit()
        self.mod_word_input.setPlaceholderText("np. idiot")
        self.mod_add_word_btn = QPushButton("Dodaj")
        self.mod_add_word_btn.clicked.connect(self.add_banned_word)
        self.mod_word_list = QListWidget()
        self.mod_remove_word_btn = QPushButton("Usuń wybrane")
        self.mod_remove_word_btn.clicked.connect(self.remove_banned_word)
        self.mod_words_layout.addWidget(self.mod_word_label, 0, 0)
        self.mod_words_layout.addWidget(self.mod_word_input, 0, 1)
        self.mod_words_layout.addWidget(self.mod_add_word_btn, 0, 2)
        self.mod_words_layout.addWidget(self.mod_word_list, 1, 0, 1, 2)
        self.mod_words_layout.addWidget(self.mod_remove_word_btn, 1, 2)
        self.mod_words_group.setLayout(self.mod_words_layout)
        # Sekcja kanału logów
        self.mod_channel_group = QGroupBox("Kanał logów")
        self.mod_channel_layout = QHBoxLayout()
        self.mod_channel_label = QLabel("Kanał:")
        self.mod_channel_selector = QComboBox()
        self.mod_channel_save_btn = QPushButton("Zapisz")
        self.mod_channel_save_btn.clicked.connect(self.save_mod_channel)
        self.mod_channel_layout.addWidget(self.mod_channel_label)
        self.mod_channel_layout.addWidget(self.mod_channel_selector, stretch=1)
        self.mod_channel_layout.addWidget(self.mod_channel_save_btn)
        self.mod_channel_group.setLayout(self.mod_channel_layout)
        self.mod_layout.addWidget(self.mod_words_group)
        self.mod_layout.addWidget(self.mod_channel_group)
        self.mod_layout.addStretch()
        self.mod_tab.setLayout(self.mod_layout)

        # Zakładka XP i Ekonomia
        self.xp_tab = QWidget()
        self.xp_layout = QVBoxLayout()
        self.xp_layout.setSpacing(10)
        # Sekcja nagród za poziom
        self.xp_rewards_group = QGroupBox("Nagrody za poziom")
        self.xp_rewards_layout = QGridLayout()
        self.xp_level_label = QLabel("Poziom:")
        self.xp_level_input = QLineEdit()
        self.xp_level_input.setPlaceholderText("np. 10")
        self.xp_role_label = QLabel("Rola:")
        self.xp_role_selector = QComboBox()
        self.xp_add_reward_btn = QPushButton("Dodaj")
        self.xp_add_reward_btn.clicked.connect(self.add_xp_reward)
        self.xp_rewards_layout.addWidget(self.xp_level_label, 0, 0)
        self.xp_rewards_layout.addWidget(self.xp_level_input, 0, 1)
        self.xp_rewards_layout.addWidget(self.xp_role_label, 1, 0)
        self.xp_rewards_layout.addWidget(self.xp_role_selector, 1, 1)
        self.xp_rewards_layout.addWidget(self.xp_add_reward_btn, 0, 2, 2, 1)
        self.xp_rewards_group.setLayout(self.xp_rewards_layout)
        # Sekcja sklepu
        self.shop_group = QGroupBox("Sklep")
        self.shop_layout = QGridLayout()
        self.shop_name_label = QLabel("Nazwa:")
        self.shop_name_input = QLineEdit()
        self.shop_name_input.setPlaceholderText("np. VIP")
        self.shop_price_label = QLabel("Cena (LC):")
        self.shop_price_input = QLineEdit()
        self.shop_price_input.setPlaceholderText("np. 100")
        self.shop_role_label = QLabel("Rola:")
        self.shop_role_selector = QComboBox()
        self.shop_add_item_btn = QPushButton("Dodaj")
        self.shop_add_item_btn.clicked.connect(self.add_shop_item)
        self.shop_layout.addWidget(self.shop_name_label, 0, 0)
        self.shop_layout.addWidget(self.shop_name_input, 0, 1)
        self.shop_layout.addWidget(self.shop_price_label, 1, 0)
        self.shop_layout.addWidget(self.shop_price_input, 1, 1)
        self.shop_layout.addWidget(self.shop_role_label, 2, 0)
        self.shop_layout.addWidget(self.shop_role_selector, 2, 1)
        self.shop_layout.addWidget(self.shop_add_item_btn, 0, 2, 3, 1)
        self.shop_group.setLayout(self.shop_layout)
        self.xp_layout.addWidget(self.xp_rewards_group)
        self.xp_layout.addWidget(self.shop_group)
        self.xp_layout.addStretch()
        self.xp_tab.setLayout(self.xp_layout)

        # Zakładka Ogłoszenia
        self.alerts_tab = QWidget()
        self.alerts_layout = QVBoxLayout()
        self.alerts_layout.setSpacing(10)
        # Sekcja kanału ogłoszeń
        self.alerts_channel_group = QGroupBox("Kanał ogłoszeń")
        self.alerts_channel_layout = QHBoxLayout()
        self.alerts_channel_label = QLabel("Kanał:")
        self.alerts_channel_selector = QComboBox()
        self.alerts_save_btn = QPushButton("Zapisz")
        self.alerts_save_btn.clicked.connect(self.save_alerts_channel)
        self.alerts_channel_layout.addWidget(self.alerts_channel_label)
        self.alerts_channel_layout.addWidget(self.alerts_channel_selector, stretch=1)
        self.alerts_channel_layout.addWidget(self.alerts_save_btn)
        self.alerts_channel_group.setLayout(self.alerts_channel_layout)
        # Sekcja powitań
        self.welcome_group = QGroupBox("Wiadomość powitalna")
        self.welcome_layout = QGridLayout()
        self.welcome_channel_label = QLabel("Kanał:")
        self.welcome_channel_selector = QComboBox()
        self.welcome_message_label = QLabel("Treść:")
        self.welcome_message_input = QTextEdit()
        self.welcome_message_input.setFixedHeight(100)
        self.welcome_embed_checkbox = QCheckBox("Użyj embeda")
        self.welcome_save_btn = QPushButton("Zapisz")
        self.welcome_save_btn.clicked.connect(self.save_welcome_config)
        self.welcome_layout.addWidget(self.welcome_channel_label, 0, 0)
        self.welcome_layout.addWidget(self.welcome_channel_selector, 0, 1, 1, 2)
        self.welcome_layout.addWidget(self.welcome_message_label, 1, 0)
        self.welcome_layout.addWidget(self.welcome_message_input, 1, 1, 1, 2)
        self.welcome_layout.addWidget(self.welcome_embed_checkbox, 2, 1)
        self.welcome_layout.addWidget(self.welcome_save_btn, 2, 2)
        self.welcome_group.setLayout(self.welcome_layout)
        # Sekcja pożegnań
        self.farewell_group = QGroupBox("Wiadomość pożegnalna")
        self.farewell_layout = QGridLayout()
        self.farewell_channel_label = QLabel("Kanał:")
        self.farewell_channel_selector = QComboBox()
        self.farewell_message_label = QLabel("Treść:")
        self.farewell_message_input = QTextEdit()
        self.farewell_message_input.setFixedHeight(100)
        self.farewell_embed_checkbox = QCheckBox("Użyj embeda")
        self.farewell_save_btn = QPushButton("Zapisz")
        self.farewell_save_btn.clicked.connect(self.save_farewell_config)
        self.farewell_layout.addWidget(self.farewell_channel_label, 0, 0)
        self.farewell_layout.addWidget(self.farewell_channel_selector, 0, 1, 1, 2)
        self.farewell_layout.addWidget(self.farewell_message_label, 1, 0)
        self.farewell_layout.addWidget(self.farewell_message_input, 1, 1, 1, 2)
        self.farewell_layout.addWidget(self.farewell_embed_checkbox, 2, 1)
        self.farewell_layout.addWidget(self.farewell_save_btn, 2, 2)
        self.alerts_layout.addWidget(self.alerts_channel_group)
        self.alerts_layout.addWidget(self.welcome_group)
        self.alerts_layout.addWidget(self.farewell_group)
        self.alerts_layout.addStretch()
        self.alerts_tab.setLayout(self.alerts_layout)

        # Zakładka Tickety
        self.tickets_tab = QWidget()
        self.tickets_layout = QVBoxLayout()
        self.tickets_layout.setSpacing(10)
        self.tickets_group = QGroupBox("System ticketów")
        self.tickets_inner_layout = QGridLayout()
        self.tickets_channel_label = QLabel("Kanał ticketów:")
        self.tickets_channel_selector = QComboBox()
        self.tickets_role_label = QLabel("Rola adminów:")
        self.tickets_role_selector = QComboBox()
        self.tickets_save_btn = QPushButton("Zapisz")
        self.tickets_save_btn.clicked.connect(self.save_tickets_config)
        self.tickets_inner_layout.addWidget(self.tickets_channel_label, 0, 0)
        self.tickets_inner_layout.addWidget(self.tickets_channel_selector, 0, 1)
        self.tickets_inner_layout.addWidget(self.tickets_role_label, 1, 0)
        self.tickets_inner_layout.addWidget(self.tickets_role_selector, 1, 1)
        self.tickets_inner_layout.addWidget(self.tickets_save_btn, 0, 2, 2, 1)
        self.tickets_group.setLayout(self.tickets_inner_layout)
        self.tickets_layout.addWidget(self.tickets_group)
        self.tickets_layout.addStretch()
        self.tickets_tab.setLayout(self.tickets_layout)

        # Zakładka Status
        self.status_tab = QWidget()
        self.status_layout = QVBoxLayout()
        self.status_layout.setSpacing(10)
        self.status_group = QGroupBox("Status bota")
        self.status_inner_layout = QVBoxLayout()
        self.status_log_label = QLabel("Logi:")
        self.status_log_list = QListWidget()
        self.status_panic_btn = QPushButton("Panic Mode (Stop)")
        self.status_panic_btn.setStyleSheet("background-color: #FF5555;")
        self.status_panic_btn.clicked.connect(self.panic_stop)
        self.status_inner_layout.addWidget(self.status_log_label)
        self.status_inner_layout.addWidget(self.status_log_list)
        self.status_inner_layout.addWidget(self.status_panic_btn)
        self.status_group.setLayout(self.status_inner_layout)
        self.status_layout.addWidget(self.status_group)
        self.status_layout.addStretch()
        self.status_tab.setLayout(self.status_layout)

        # Eksport/Import
        self.export_import_group = QGroupBox("Ustawienia")
        self.export_import_layout = QHBoxLayout()
        self.export_btn = QPushButton("Eksportuj")
        self.export_btn.clicked.connect(self.export_settings)
        self.import_btn = QPushButton("Importuj")
        self.import_btn.clicked.connect(self.import_settings)
        self.export_import_layout.addWidget(self.export_btn)
        self.export_import_layout.addWidget(self.import_btn)
        self.export_import_group.setLayout(self.export_import_layout)
        self.main_layout.addWidget(self.export_import_group)

        # Przycisk start/stop bota
        self.bot_toggle_btn = QPushButton("Uruchom LibreBot")
        self.bot_toggle_btn.clicked.connect(self.toggle_bot)
        self.main_layout.addWidget(self.bot_toggle_btn)

        self.tabs.addTab(self.mod_tab, "🛠 Moderacja")
        self.tabs.addTab(self.xp_tab, "📈 XP i Ekonomia")
        self.tabs.addTab(self.alerts_tab, "🔔 Ogłoszenia")
        self.tabs.addTab(self.tickets_tab, "🎟 Tickety")
        self.tabs.addTab(self.status_tab, "📊 Status")

        # Animacja przejść zakładek
        self.tabs.currentChanged.connect(self.animate_tab_change)

        # Uruchom klienta Discorda
        self.discord_thread = threading.Thread(target=self.run_discord_client, daemon=True)
        self.discord_thread.start()

    def animate_tab_change(self, index):
        widget = self.tabs.widget(index)
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(24)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.start()

    def run_discord_client(self):
        @client.event
        async def on_ready():
            self.guilds = client.guilds
            for guild in self.guilds:
                self.channels[guild.id] = [c for c in guild.text_channels]
                self.roles[guild.id] = guild.roles
            self.update_guild_selector()
            print("🎨 Discord client ready for GUI!")
        client.run(DISCORD_TOKEN)

    def update_guild_selector(self):
        self.guild_selector.clear()
        for guild in self.guilds:
            self.guild_selector.addItem(guild.name, guild.id)
        if self.guilds:
            self.update_guild(0)

    def update_guild(self, index):
        if index >= 0:
            self.current_guild_id = self.guild_selector.itemData(index)
            if self.current_guild_id:
                self.update_channels_and_roles()
                self.load_banned_words()

    def update_channels_and_roles(self):
        self.mod_channel_selector.clear()
        self.alerts_channel_selector.clear()
        self.tickets_channel_selector.clear()
        self.welcome_channel_selector.clear()
        self.farewell_channel_selector.clear()
        self.tickets_role_selector.clear()
        self.xp_role_selector.clear()
        self.shop_role_selector.clear()

        channels = self.channels.get(self.current_guild_id, [])
        roles = self.roles.get(self.current_guild_id, [])

        for channel in channels:
            channel_name = f"#{channel.name}"
            self.mod_channel_selector.addItem(channel_name, str(channel.id))
            self.alerts_channel_selector.addItem(channel_name, str(channel.id))
            self.tickets_channel_selector.addItem(channel_name, str(channel.id))
            self.welcome_channel_selector.addItem(channel_name, str(channel.id))
            self.farewell_channel_selector.addItem(channel_name, str(channel.id))
        for role in roles:
            role_name = f"@{role.name}"
            self.tickets_role_selector.addItem(role_name, role.id)
            self.xp_role_selector.addItem(role_name, role.id)
            self.shop_role_selector.addItem(role_name, role.id)

    def load_banned_words(self):
        self.mod_word_list.clear()
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT word FROM banned_words')
        for word in cursor.fetchall():
            self.mod_word_list.addItem(word[0])
        conn.close()

    def add_banned_word(self):
        word = self.mod_word_input.text().strip()
        if not word:
            QMessageBox.warning(self, "Błąd", "Wpisz słowo!")
            return
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO banned_words (word) VALUES (?)', (word.lower(),))
        conn.commit()
        conn.close()
        self.mod_word_input.clear()
        self.load_banned_words()
        QMessageBox.information(self, "Sukces", f"Dodano: {word}")

    def remove_banned_word(self):
        selected = self.mod_word_list.currentItem()
        if not selected:
            QMessageBox.warning(self, "Błąd", "Wybierz słowo!")
            return
        word = selected.text()
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM banned_words WHERE word = ?', (word,))
        conn.commit()
        conn.close()
        self.load_banned_words()
        QMessageBox.information(self, "Sukces", f"Usunięto: {word}")

    def save_mod_channel(self):
        channel_id = self.mod_channel_selector.currentData()
        if not channel_id:
            QMessageBox.warning(self, "Błąd", "Wybierz kanał!")
            return
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (guild_id, mod_channel_id) VALUES (?, ?)', 
                       (self.current_guild_id, int(channel_id)))
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Sukces", "Zapisano kanał logów!")

    def add_xp_reward(self):
        level = self.xp_level_input.text().strip()
        role_id = self.xp_role_selector.currentData()
        if not level.isdigit() or not role_id:
            QMessageBox.warning(self, "Błąd", "Wpisz poziom i wybierz rolę!")
            return
        level = int(level)
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO shop (item_id, name, price, role_id) VALUES (?, ?, ?, ?)', 
                       (role_id, f"Rola za poziom {level}", level * 100, role_id))
        conn.commit()
        conn.close()
        self.xp_level_input.clear()
        QMessageBox.information(self, "Sukces", f"Dodano nagrodę za poziom {level}!")

    def add_shop_item(self):
        name = self.shop_name_input.text().strip()
        price = self.shop_price_input.text().strip()
        role_id = self.shop_role_selector.currentData()
        if not name or not price.isdigit() or not role_id:
            QMessageBox.warning(self, "Błąd", "Wpisz nazwę, cenę i wybierz rolę!")
            return
        price = int(price)
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO shop (item_id, name, price, role_id) VALUES (?, ?, ?, ?)', 
                       (role_id, name, price, role_id))
        conn.commit()
        conn.close()
        self.shop_name_input.clear()
        self.shop_price_input.clear()
        QMessageBox.information(self, "Sukces", f"Dodano: {name}!")

    def save_alerts_channel(self):
        channel_id = self.alerts_channel_selector.currentData()
        if not channel_id:
            QMessageBox.warning(self, "Błąd", "Wybierz kanał!")
            return
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (guild_id, alert_channel_id) VALUES (?, ?)', 
                       (self.current_guild_id, int(channel_id)))
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Sukces", "Zapisano kanał ogłoszeń!")

    def save_welcome_config(self):
        channel_id = self.welcome_channel_selector.currentData()
        message = self.welcome_message_input.toPlainText().strip()
        use_embed = self.welcome_embed_checkbox.isChecked()
        if not channel_id or not message:
            QMessageBox.warning(self, "Błąd", "Wybierz kanał i wpisz treść!")
            return
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (guild_id, welcome_channel_id, welcome_message, welcome_embed) VALUES (?, ?, ?, ?)', 
                       (self.current_guild_id, int(channel_id), message, int(use_embed)))
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Sukces", "Zapisano wiadomość powitalną!")

    def save_farewell_config(self):
        channel_id = self.farewell_channel_selector.currentData()
        message = self.farewell_message_input.toPlainText().strip()
        use_embed = self.farewell_embed_checkbox.isChecked()
        if not channel_id or not message:
            QMessageBox.warning(self, "Błąd", "Wybierz kanał i wpisz treść!")
            return
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (guild_id, farewell_channel_id, farewell_message, farewell_embed) VALUES (?, ?, ?, ?)', 
                       (self.current_guild_id, int(channel_id), message, int(use_embed)))
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Sukces", "Zapisano wiadomość pożegnalną!")

    async def send_ticket_message(self, guild_id, channel_id, role_id):
        guild = discord.utils.get(client.guilds, id=guild_id)
        channel = guild.get_channel(int(channel_id))
        if not channel:
            raise ValueError("Nie znaleziono kanału! Sprawdź, czy kanał istnieje.")
        embed = discord.Embed(title="🎫 System Ticketów", description="Kliknij, by stworzyć ticket!", color=0x00ff00)
        embed.set_footer(text="LibreBot - Wsparcie! 😈")
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")

        class TicketButton(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            @discord.ui.button(label="Stwórz Ticket", style=discord.ButtonStyle.green, emoji="🎫")
            async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                conn = sqlite3.connect('librebot_data.db')
                cursor = conn.cursor()
                cursor.execute('SELECT ticket_role_id FROM settings WHERE guild_id = ?', (interaction.guild.id,))
                settings = cursor.fetchone()
                conn.close()
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
                ticket_channel = await interaction.guild.create_text_channel(f"ticket-{interaction.user.name}", overwrites=overwrites)
                ticket_embed = discord.Embed(title="🎫 Nowy Ticket", description=f"{interaction.user.mention} stworzył ticket. Napisz, w czym pomóc!", color=0x00ff00)
                ticket_embed.add_field(name="Akcje", value="Kliknij 🔒, by zamknąć ticket", inline=False)
                ticket_embed.set_footer(text="LibreBot - Wsparcie! 😈")
                ticket_embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/123456789.png")

                class TicketCloseButton(discord.ui.View):
                    def __init__(self, creator_id, mod_role_id):
                        super().__init__(timeout=None)
                        self.creator_id = creator_id
                        self.mod_role_id = mod_role_id
                    @discord.ui.button(label="Zamknij Ticket", style=discord.ButtonStyle.red, emoji="🔒")
                    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        mod_role = interaction.guild.get_role(self.mod_role_id)
                        if interaction.user.id != self.creator_id and (not mod_role or mod_role not in interaction.user.roles):
                            await interaction.response.send_message("Brak uprawnień! 😢", ephemeral=True)
                            return
                        if not interaction.channel.name.startswith("ticket-"):
                            await interaction.response.send_message("To nie ticket! 😜", ephemeral=True)
                            return
                        conn = sqlite3.connect('librebot_data.db')
                        cursor = conn.cursor()
                        cursor.execute('SELECT mod_channel_id FROM settings WHERE guild_id = ?', (interaction.guild.id,))
                        mod_channel_id = cursor.fetchone()
                        if mod_channel_id and mod_channel_id[0]:
                            mod_channel = interaction.guild.get_channel(mod_channel_id[0])
                            if mod_channel:
                                embed = discord.Embed(title="🎫 Ticket Zamknięty", description=f"Ticket {interaction.channel.name} zamknięty przez {interaction.user.mention}.", color=0x00ff00)
                                embed.set_footer(text="LibreBot - Porządek! 😈")
                                await mod_channel.send(embed=embed)
                        conn.close()
                        await interaction.response.send_message("Ticket zamknięty! 👋", ephemeral=True)
                        await interaction.channel.delete()

                await ticket_channel.send(embed=ticket_embed, view=TicketCloseButton(interaction.user.id, role.id))
                await interaction.response.send_message(f"Ticket utworzony: {ticket_channel.mention}", ephemeral=True)

        message = await channel.send(embed=embed, view=TicketButton())
        return message.id

    def save_tickets_config(self):
        channel_id = self.tickets_channel_selector.currentData()
        role_id = self.tickets_role_selector.currentData()
        if not channel_id or not role_id:
            QMessageBox.warning(self, "Błąd", "Wybierz kanał i rolę!")
            return
        try:
            # Wywołanie asynchronicznej funkcji wysyłania wiadomości
            loop = asyncio.get_event_loop()
            coro = self.send_ticket_message(self.current_guild_id, channel_id, role_id)
            future = asyncio.run_coroutine_threadsafe(coro, client.loop)
            message_id = future.result()

            # Zapis do bazy danych
            conn = sqlite3.connect('librebot_data.db')
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO settings (guild_id, ticket_role_id, ticket_message_id) VALUES (?, ?, ?)', 
                           (self.current_guild_id, role_id, message_id))
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Sukces", f"System ticketów skonfigurowany! Wiadomość wysłana na kanał.")

        except discord.errors.Forbidden:
            QMessageBox.critical(self, "Błąd", "Brak permisji do wysyłania wiadomości! Upewnij się, że bot ma uprawnienia.")
        except ValueError as e:
            QMessageBox.critical(self, "Błąd", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Błąd", f"Wystąpił błąd: {str(e)}")

    def export_settings(self):
        conn = sqlite3.connect('librebot_data.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM settings WHERE guild_id = ?', (self.current_guild_id,))
        settings = cursor.fetchone()
        cursor.execute('SELECT word FROM banned_words')
        banned_words = [row[0] for row in cursor.fetchall()]
        cursor.execute('SELECT item_id, name, price, role_id FROM shop')
        shop_items = cursor.fetchall()
        data = {
            'settings': settings,
            'banned_words': banned_words,
            'shop_items': shop_items
        }
        file_path, _ = QFileDialog.getSaveFileName(self, "Eksportuj ustawienia", "", "JSON Files (*.json)")
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self, "Sukces", "Ustawienia wyeksportowane!")
        conn.close()

    def import_settings(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Importuj ustawienia", "", "JSON Files (*.json)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            conn = sqlite3.connect('librebot_data.db')
            cursor = conn.cursor()
            if data.get('settings'):
                cursor.execute('INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                               (self.current_guild_id, *data['settings'][1:]))
            if data.get('banned_words'):
                cursor.execute('DELETE FROM banned_words')
                for word in data['banned_words']:
                    cursor.execute('INSERT INTO banned_words (word) VALUES (?)', (word,))
            if data.get('shop_items'):
                cursor.execute('DELETE FROM shop')
                for item in data['shop_items']:
                    cursor.execute('INSERT INTO shop (item_id, name, price, role_id) VALUES (?, ?, ?, ?)', item)
            conn.commit()
            conn.close()
            self.load_banned_words()
            QMessageBox.information(self, "Sukces", "Ustawienia zaimportowane!")

    def toggle_bot(self):
        if not self.bot_running:
            try:
                self.bot_process = subprocess.Popen(['python', 'librebot.py'])
                self.bot_running = True
                self.bot_toggle_btn.setText("Zatrzymaj LibreBot")
                self.bot_toggle_btn.setStyleSheet("background-color: #FF5555;")
                self.statusBar().showMessage("LibreBot: Uruchomiony")
                self.status_log_list.addItem("Bot uruchomiony!")
            except Exception as e:
                QMessageBox.critical(self, "Błąd", f"Nie udało się uruchomić bota: {str(e)}")
        else:
            if self.bot_process:
                self.bot_process.terminate()
                self.bot_process = None
                self.bot_running = False
                self.bot_toggle_btn.setText("Uruchom LibreBot")
                self.bot_toggle_btn.setStyleSheet("background-color: #7289DA;")
                self.statusBar().showMessage("LibreBot: Wyłączony")
                self.status_log_list.addItem("Bot zatrzymany!")

    def panic_stop(self):
        if self.bot_process:
            self.bot_process.kill()
            self.bot_process = None
            self.bot_running = False
            self.bot_toggle_btn.setText("Uruchom LibreBot")
            self.bot_toggle_btn.setStyleSheet("background-color: #7289DA;")
            self.statusBar().showMessage("LibreBot: Wyłączony (Panic Mode)")
            self.status_log_list.addItem("Bot zatrzymany (Panic Mode)!")
            QMessageBox.warning(self, "Panic Mode", "Bot został awaryjnie zatrzymany!")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = LibreBotGUI()
    gui.show()
    sys.exit(app.exec_())