
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext
import sqlite3
import subprocess
import threading
import os
import signal


DB_PATH = "rng_game.db"
BOT_PATH = "main.py"
LOG_PATH = "bot.log"


class ControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tactas RNG Control Panel")
        self.geometry("500x600")
        self.conn = sqlite3.connect(DB_PATH)
        self.c = self.conn.cursor()
        self.bot_process = None
        self.create_widgets()
        self.log_updater = None

    def create_widgets(self):
        tk.Label(self, text="Tactas RNG Control Panel", font=("Arial", 16)).pack(pady=10)
        tk.Button(self, text="Start Bot", command=self.start_bot).pack(pady=5)
        tk.Button(self, text="Stop Bot", command=self.stop_bot).pack(pady=5)
        tk.Button(self, text="View All Users", command=self.view_users).pack(pady=5)
        tk.Button(self, text="View User Inventory", command=self.view_inventory).pack(pady=5)
        tk.Button(self, text="Reset All Data", command=self.reset_data, fg="red").pack(pady=5)
        tk.Button(self, text="View Leaderboard", command=self.view_leaderboard).pack(pady=5)
        # Daily/Weekly rewards
        tk.Label(self, text="Rewards", font=("Arial", 12, "bold")).pack(pady=8)
        tk.Button(self, text="Grant Daily Reward (Manual)", command=self.grant_daily_reward).pack(pady=2)
        tk.Button(self, text="Grant Weekly Reward (Manual)", command=self.grant_weekly_reward).pack(pady=2)
        tk.Button(self, text="Check User Streaks", command=self.check_streaks).pack(pady=2)
        # Item pool editor
        tk.Label(self, text="Item Pool Editor", font=("Arial", 12, "bold")).pack(pady=8)
        tk.Button(self, text="View Item Pool", command=self.view_item_pool).pack(pady=2)
        tk.Button(self, text="Add Item to Pool", command=self.add_item_pool).pack(pady=2)
        tk.Button(self, text="Remove Item from Pool", command=self.remove_item_pool).pack(pady=2)
        tk.Button(self, text="Edit Item Rarity", command=self.edit_item_rarity_pool).pack(pady=2)
        tk.Button(self, text="Edit Item Description", command=self.edit_item_description_pool).pack(pady=2)
        tk.Button(self, text="View Item Description", command=self.view_item_description_pool).pack(pady=2)
        tk.Button(self, text="Set Item Image Path", command=self.set_item_image_pool).pack(pady=2)
    def edit_item_description_pool(self):
        item = simpledialog.askstring("Edit Item Description", "Enter the item name:")
        if not item:
            return
        desc = simpledialog.askstring("Edit Item Description", "Enter the new description:")
        if desc is None:
            return
        self.c.execute("UPDATE items SET description = ? WHERE item = ?", (desc, item))
        self.conn.commit()
        self.output.insert(tk.END, f"Updated description for {item}.\n")

    def view_item_description_pool(self):
        item = simpledialog.askstring("View Item Description", "Enter the item name:")
        if not item:
            return
        self.c.execute("SELECT description FROM items WHERE item = ?", (item,))
        row = self.c.fetchone()
        if not row or not row[0]:
            self.output.insert(tk.END, f"No description found for {item}.\n")
        else:
            self.output.insert(tk.END, f"Description for {item}: {row[0]}\n")

    def set_item_image_pool(self):
        item = simpledialog.askstring("Set Item Image", "Enter the item name:")
        if not item:
            return
        image_path = simpledialog.askstring("Set Item Image", "Enter the image path or URL:")
        if not image_path:
            return
        self.c.execute("UPDATE items SET image = ? WHERE item = ?", (image_path, item))
        self.conn.commit()
        self.output.insert(tk.END, f"Set image for {item}.\n")
    def view_item_pool(self):
        self.output.delete(1.0, tk.END)
        self.c.execute("SELECT item, rarity FROM items ORDER BY item")
        items = self.c.fetchall()
        if not items:
            self.output.insert(tk.END, "No items in the pool.\n")
            return
        self.output.insert(tk.END, "Item Pool:\n")
        for item, rarity in items:
            self.output.insert(tk.END, f"{item} ({rarity})\n")

    def add_item_pool(self):
        item = simpledialog.askstring("Add Item", "Enter the item name:")
        if not item:
            return
        rarity = simpledialog.askstring("Add Item", "Enter the rarity:")
        if not rarity:
            return
        self.c.execute("SELECT 1 FROM items WHERE item = ?", (item,))
        if self.c.fetchone():
            messagebox.showerror("Error", "Item already exists.")
            return
        self.c.execute("INSERT INTO items (item, rarity) VALUES (?, ?)", (item, rarity))
        self.conn.commit()
        self.output.insert(tk.END, f"Added {item} ({rarity}) to the item pool.\n")

    def remove_item_pool(self):
        item = simpledialog.askstring("Remove Item", "Enter the item name to remove:")
        if not item:
            return
        self.c.execute("DELETE FROM items WHERE item = ?", (item,))
        self.conn.commit()
        self.output.insert(tk.END, f"Removed {item} from the item pool.\n")

    def edit_item_rarity_pool(self):
        item = simpledialog.askstring("Edit Item Rarity", "Enter the item name:")
        if not item:
            return
        rarity = simpledialog.askstring("Edit Item Rarity", "Enter the new rarity:")
        if not rarity:
            return
        self.c.execute("UPDATE items SET rarity = ? WHERE item = ?", (rarity, item))
        self.conn.commit()
        self.output.insert(tk.END, f"Updated {item} to rarity {rarity}.\n")
    def grant_daily_reward(self):
        import datetime
        user_id = simpledialog.askinteger("User ID", "Enter the user ID:")
        if user_id is None:
            return
        now = datetime.datetime.now().date()
        self.c.execute("SELECT last_daily, coins FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if not row:
            messagebox.showerror("Error", "User not found.")
            return
        last_daily, coins = row
        if last_daily == str(now):
            messagebox.showinfo("Info", "User has already claimed today's daily reward.")
            return
        # Grant reward (e.g., 100 coins)
        new_coins = (coins or 0) + 100
        self.c.execute("UPDATE users SET coins = ?, last_daily = ? WHERE user_id = ?", (new_coins, str(now), user_id))
        self.conn.commit()
        self.output.insert(tk.END, f"Granted daily reward to user {user_id}. Coins: {new_coins}\n")

    def grant_weekly_reward(self):
        import datetime
        user_id = simpledialog.askinteger("User ID", "Enter the user ID:")
        if user_id is None:
            return
        now = datetime.datetime.now().isocalendar()
        week_str = f"{now[0]}-W{now[1]}"
        self.c.execute("SELECT last_weekly, coins FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if not row:
            messagebox.showerror("Error", "User not found.")
            return
        last_weekly, coins = row
        if last_weekly == week_str:
            messagebox.showinfo("Info", "User has already claimed this week's reward.")
            return
        # Grant reward (e.g., 500 coins)
        new_coins = (coins or 0) + 500
        self.c.execute("UPDATE users SET coins = ?, last_weekly = ? WHERE user_id = ?", (new_coins, week_str, user_id))
        self.conn.commit()
        self.output.insert(tk.END, f"Granted weekly reward to user {user_id}. Coins: {new_coins}\n")

    def check_streaks(self):
        import datetime
        user_id = simpledialog.askinteger("User ID", "Enter the user ID:")
        if user_id is None:
            return
        self.c.execute("SELECT last_daily, last_weekly FROM users WHERE user_id = ?", (user_id,))
        row = self.c.fetchone()
        if not row:
            messagebox.showerror("Error", "User not found.")
            return
        last_daily, last_weekly = row
        today = datetime.datetime.now().date()
        week = datetime.datetime.now().isocalendar()
        week_str = f"{week[0]}-W{week[1]}"
        daily_status = "Claimed" if last_daily == str(today) else "Not claimed"
        weekly_status = "Claimed" if last_weekly == week_str else "Not claimed"
        self.output.insert(tk.END, f"User {user_id} - Daily: {daily_status}, Weekly: {weekly_status}\n")
        # Admin controls
        tk.Label(self, text="Admin Controls", font=("Arial", 12, "bold")).pack(pady=8)
        tk.Button(self, text="Give Item to User (Admin)", command=self.admin_give_item).pack(pady=2)
        tk.Button(self, text="Set User Pulls (Admin)", command=self.admin_set_pulls).pack(pady=2)
        tk.Button(self, text="View Pending Trades (Admin)", command=self.admin_view_trades).pack(pady=2)
        tk.Button(self, text="Cancel Trade (Admin)", command=self.admin_cancel_trade).pack(pady=2)
        tk.Label(self, text="Bot Logs:").pack(pady=5)
        self.log_output = scrolledtext.ScrolledText(self, height=12, width=60, state='disabled')
        self.log_output.pack(pady=5)
        tk.Button(self, text="Refresh Logs", command=self.update_logs).pack(pady=2)
        self.output = tk.Text(self, height=10, width=60)
        self.output.pack(pady=10)

    def admin_view_trades(self):
        self.output.delete(1.0, tk.END)
        # Pending trades are only in memory in the bot, so we can't show live trades unless we store them in DB.
        # For now, show a message.
        self.output.insert(tk.END, "Pending trades are only visible while the bot is running.\n")
        self.output.insert(tk.END, "(To persist trades, implement DB storage for trades in the bot.)\n")

    def admin_cancel_trade(self):
        # This is a placeholder, as trades are only in memory in the bot.
        self.output.delete(1.0, tk.END)
        self.output.insert(tk.END, "Cancelling trades from the panel is not supported yet.\n")
        self.output.insert(tk.END, "(To enable this, store trades in the database in the bot.)\n")

    def view_leaderboard(self):
        self.output.delete(1.0, tk.END)
        self.c.execute("SELECT username, pulls FROM users ORDER BY pulls DESC LIMIT 10")
        rows = self.c.fetchall()
        if not rows:
            self.output.insert(tk.END, "No users found.\n")
            return
        self.output.insert(tk.END, "Leaderboard (Top 10 by Pulls):\n")
        for idx, (username, pulls) in enumerate(rows, 1):
            self.output.insert(tk.END, f"#{idx} {username} - Pulls: {pulls}\n")
    def admin_give_item(self):
        user_id = simpledialog.askinteger("User ID", "Enter the user ID:")
        if user_id is None:
            return
        item = simpledialog.askstring("Item", "Enter the item name:")
        if not item:
            return
        amount = simpledialog.askinteger("Amount", "Enter the amount:")
        if not amount:
            amount = 1
        # Find rarity
        rarity = None
        items = [
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
        for i, r in items:
            if i.lower() == item.lower():
                rarity = r
                break
        if not rarity:
            messagebox.showerror("Error", "Item not found.")
            return
        self.c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, str(user_id)))
        self.c.execute("SELECT amount FROM inventory WHERE user_id = ? AND item = ?", (user_id, item))
        row = self.c.fetchone()
        if row:
            self.c.execute("UPDATE inventory SET amount = amount + ? WHERE user_id = ? AND item = ?", (amount, user_id, item))
        else:
            self.c.execute("INSERT INTO inventory (user_id, item, rarity, amount) VALUES (?, ?, ?, ?)", (user_id, item, rarity, amount))
        self.conn.commit()
        self.output.insert(tk.END, f"Gave {amount}x {item} ({rarity}) to user {user_id}.\n")

    def admin_set_pulls(self):
        user_id = simpledialog.askinteger("User ID", "Enter the user ID:")
        if user_id is None:
            return
        pulls = simpledialog.askinteger("Pulls", "Enter the new pull count:")
        if pulls is None:
            return
        self.c.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, str(user_id)))
        self.c.execute("UPDATE users SET pulls = ? WHERE user_id = ?", (pulls, user_id))
        self.conn.commit()
        self.output.insert(tk.END, f"Set pulls for user {user_id} to {pulls}.\n")

    def start_bot(self):
        if self.bot_process and self.bot_process.poll() is None:
            messagebox.showinfo("Info", "Bot is already running.")
            return
        with open(LOG_PATH, "w") as log_file:
            self.bot_process = subprocess.Popen([
                "python3", BOT_PATH
            ], stdout=log_file, stderr=subprocess.STDOUT)
        self.output.insert(tk.END, "Bot started.\n")
        self.schedule_log_update()

    def stop_bot(self):
        if self.bot_process and self.bot_process.poll() is None:
            os.kill(self.bot_process.pid, signal.SIGTERM)
            self.bot_process.wait()
            self.output.insert(tk.END, "Bot stopped.\n")
        else:
            self.output.insert(tk.END, "Bot is not running.\n")
        self.bot_process = None

    def view_users(self):
        self.output.delete(1.0, tk.END)
        self.c.execute("SELECT user_id, username, pulls FROM users")
        users = self.c.fetchall()
        if not users:
            self.output.insert(tk.END, "No users found.\n")
            return
        for user_id, username, pulls in users:
            self.output.insert(tk.END, f"{username} (ID: {user_id}) - Pulls: {pulls}\n")

    def view_inventory(self):
        self.output.delete(1.0, tk.END)
        user_id = simpledialog.askinteger("User ID", "Enter the user ID:")
        if user_id is None:
            return
        self.c.execute("SELECT item, rarity, amount FROM inventory WHERE user_id = ?", (user_id,))
        items = self.c.fetchall()
        if not items:
            self.output.insert(tk.END, "No inventory for this user.\n")
            return
        for item, rarity, amount in items:
            self.output.insert(tk.END, f"{item} ({rarity}) x{amount}\n")

    def reset_data(self):
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to reset all data? This cannot be undone."):
            self.c.execute("DELETE FROM users")
            self.c.execute("DELETE FROM inventory")
            self.conn.commit()
            self.output.delete(1.0, tk.END)
            self.output.insert(tk.END, "All data has been reset.\n")

    def update_logs(self):
        self.log_output.config(state='normal')
        self.log_output.delete(1.0, tk.END)
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r") as f:
                self.log_output.insert(tk.END, f.read())
        self.log_output.config(state='disabled')

    def schedule_log_update(self):
        self.update_logs()
        self.log_updater = self.after(2000, self.schedule_log_update)

    def on_closing(self):
        if self.bot_process and self.bot_process.poll() is None:
            self.stop_bot()
        if self.log_updater:
            self.after_cancel(self.log_updater)
        self.destroy()

if __name__ == "__main__":
    app = ControlPanel()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
