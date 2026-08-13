"""
Startet BEIDE Bots (Resell-Bot + Wandel-Bot) in einem einzigen
bot-hosting.net-Server — spart einen zweiten Server / Coins.

Nutzung: Im Panel unter „Startup" als Python-Datei  start_beide.py  eintragen.

Benötigte Variablen in der .env:
  DISCORD_TOKEN = Token des Resell-Bots
  WANDEL_TOKEN  = Token des Wandel-Bots (eigene Bot-Application!)
  GUILD_ID      = deine Server-ID (nutzen beide)

Soll nur EINER laufen, trag stattdessen direkt vinted_profit_bot.py
bzw. wandel_bot.py als Startdatei ein.
"""

import os
import subprocess
import sys
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BOTS = ["vinted_profit_bot.py", "wandel_bot.py"]


def main():
    fehlt = []
    if not os.environ.get("DISCORD_TOKEN"):
        fehlt.append("DISCORD_TOKEN (Resell-Bot)")
    if not (os.environ.get("WANDEL_TOKEN") or os.environ.get("DISCORD_TOKEN")):
        fehlt.append("WANDEL_TOKEN (Wandel-Bot)")
    if fehlt:
        print("⚠️  Fehlende Variablen in der .env:", ", ".join(fehlt))

    prozesse = {bot: subprocess.Popen([sys.executable, bot]) for bot in BOTS}
    print("🚀 Gestartet:", ", ".join(BOTS))

    try:
        while True:
            for bot, p in prozesse.items():
                code = p.poll()
                if code is not None:
                    print(f"🔄 {bot} beendet (Code {code}) — Neustart in 10 s …")
                    time.sleep(10)
                    prozesse[bot] = subprocess.Popen([sys.executable, bot])
            time.sleep(5)
    except KeyboardInterrupt:
        for p in prozesse.values():
            p.terminate()


if __name__ == "__main__":
    main()
