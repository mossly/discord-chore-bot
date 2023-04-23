import os
import sqlite3
import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timedelta
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")

# Set up the SQL database
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS parent_chores (
    id SERIAL PRIMARY KEY,
    creation_date DATE,
    task_name TEXT,
    assigned_persons TEXT,
    repeat_period INTEGER,
    active BOOLEAN
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS child_chores (
    id SERIAL PRIMARY KEY,
    parent_id INTEGER,
    task_name TEXT,
    assigned_person TEXT,
    due_date DATE,
    completed BOOLEAN
)
""")
conn.commit()
```

bot = commands.Bot(command_prefix="!")

@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")

@bot.command()
async def create_parent_chore(ctx, task_name: str, assigned_persons: str, repeat_period: int):
    creation_date = datetime.now().strftime("%Y-%m-%d")
    assigned_persons_list = assigned_persons.split("|")
    active = 1
    c.execute("""
    INSERT INTO parent_chores (creation_date, task_name, assigned_persons, repeat_period, active)
    VALUES (?, ?, ?, ?, ?)
    """, (creation_date, task_name, assigned_persons, repeat_period, active))
    conn.commit()
    parent_chore_id = c.lastrowid
    create_child_chore(parent_chore_id, task_name, assigned_persons_list)
    await ctx.send(f"Parent chore '{task_name}' created successfully.")

def create_child_chore(parent_chore_id, task_name, assigned_persons_list):
    due_date = datetime.now() + timedelta(days=7)
    assigned_person = assigned_persons_list[0]
    completed = 0
    c.execute("""
    INSERT INTO child_chores (parent_id, task_name, assigned_person, due_date, completed)
    VALUES (?, ?, ?, ?, ?)
    """,(parent_chore_id, task_name, assigned_person, due_date.strftime("%Y-%m-%d"), completed))
    conn.commit()
    assigned_persons_list.append(assigned_persons_list.pop(0))
    c.execute("""
    UPDATE parent_chores
    SET assigned_persons = ?
    WHERE id = ?
    """, ("|".join(assigned_persons_list), parent_chore_id))
    conn.commit()

@bot.command()
async def complete_chore(ctx, chore_id: int):
    c.execute("""
    UPDATE child_chores
    SET completed = 1
    WHERE id = ?
    """, (chore_id,))
    conn.commit()
    await ctx.send(f"Chore {chore_id} marked as complete.")

async def create_new_child_chores():
    c.execute("SELECT * FROM parent_chores WHERE active = 1")
    parent_chores = c.fetchall()
    for parent_chore in parent_chores:
        parent_chore_id, _, task_name, assigned_persons, repeat_period, _ = parent_chore
        assigned_persons_list = assigned_persons.split("|")
        create_child_chore(parent_chore_id, task_name, assigned_persons_list)

async def send_daily_chores():
    await bot.wait_until_ready()
    while not bot.is_closed():
        if datetime.now().hour == 12:
            c.execute("""
            SELECT id, task_name, assigned_person, due_date, completed
            FROM child_chores
            WHERE completed = 0
            ORDER BY assigned_person, due_date
            """)
            chores = c.fetchall()
            chores_by_person = {}
            for chore in chores:
                chore_id, task_name, assigned_person, due_date, _ = chore
                due_date_obj = datetime.strptime(due_date, "%Y-%m-%d")
                days_remaining = (due_date_obj - datetime.now()).days
                if days_remaining >= 0:
                    status = f"Due in {days_remaining} days ({due_date})"
                else:
                    status = f"**OVERDUE by {-days_remaining} days ({due_date})**"
                chore_text = f"{task_name} (ID: {chore_id}) - {status}"
                if assigned_person not in chores_by_person:
                    chores_by_person[assigned_person] = [chore_text]
                else:
                    chores_by_person[assigned_person].append(chore_text)

            for person, chore_list in chores_by_person.items():
                message = f"**{person}'s Chores:**\n" + "\n".join(chore_list)
                await ctx.send(message)
            await create_new_child_chores()
            await asyncio.sleep(3600)  # Wait for 1 hour to avoid sending multiple messages
        else:
            await asyncio.sleep(60)  # Check every minute if it's time to send the message

BOT_API_TOKEN = os.getenv("BOT_API_TOKEN")

bot.loop.create_task(send_daily_chores())
bot.run(BOT_API_TOKEN)
