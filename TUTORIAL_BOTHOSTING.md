# 🆓 Bot kostenlos online bringen mit bot-hosting.net

Railway kostet inzwischen Geld. Diese Anleitung bringt deinen **Resell-Bot**
**komplett kostenlos** und **ohne Kreditkarte** dauerhaft online – über
**bot-hosting.net** (speziell für Discord-Bots gemacht).

> **Wichtig vorab:** bot-hosting.net ist gratis, finanziert sich aber über
> „Coins". Du bekommst täglich Coins gratis (Login-Bonus + eine AFK-Seite).
> Solange genug Coins da sind, läuft der Bot 24/7. Einmal am Tag kurz einloggen
> reicht meist. Es ist die einfachste Gratis-Lösung – dafür etwas weniger
> „kugelsicher" als ein bezahlter Server.

Voraussetzung: Du hast bereits einen **Discord-Bot-Token** und den Bot in deinen
Server eingeladen. **Falls nicht → mach zuerst TEIL 1 + 2 aus der
[`README_DEPLOY.md`](README_DEPLOY.md)** (Token erstellen, Bot einladen,
Server-ID holen). Den Rest (Railway) brauchst du nicht – stattdessen kommt hier.

---

## 📋 Überblick

```
1. Bei bot-hosting.net anmelden (mit Discord)
2. Gratis-Server erstellen (Python)
3. Bot-Dateien hochladen
4. .env-Datei mit Token anlegen
5. Startdatei einstellen + starten
6. Testen im Discord
```

Dauer: ~15 Minuten.

---

## TEIL 1 · Anmelden

1. Gehe auf 👉 **https://bot-hosting.net**
2. **„Login with Discord"** → autorisieren.
3. Du landest im Dashboard. Oben siehst du deine **Coins**.
   - Tipp: Es gibt einen **„AFK Page"**-/„Earn Coins"-Button. Lass die Seite
     nebenbei offen, dann sammelst du Coins fürs Hosting.

---

## TEIL 2 · Gratis-Server erstellen

1. Im Dashboard auf **„Create Server"** (oder „New Server").
2. Als Typ/Software **Python** wählen.
3. Den kostenlosen Plan bestätigen (Free / 0 Coins-Setup).
4. Der Server wird angelegt und öffnet ein **Control Panel** (Pterodactyl).
   Dort gibt es Reiter wie **Console**, **Files**, **Startup**.

---

## TEIL 3 · Bot-Dateien hochladen

Du brauchst aus diesem Repo nur **2 Dateien**:
`vinted_profit_bot.py` und `requirements.txt`.

1. Lade beide aus GitHub herunter:
   - Öffne https://github.com/k696969/Profit-bot
   - Klick auf die Datei → Button **„Download raw file"** (Download-Symbol).
   - Mach das für **`vinted_profit_bot.py`** und **`requirements.txt`**.
2. Im bot-hosting-Panel: Reiter **„Files"**.
3. Oben **„Upload"** → beide Dateien hochladen (oder reinziehen).

> 💡 Noch einfacher (optional): Im Reiter **„Startup"** gibt es oft ein Feld
> **„Git Repo Address"**. Trägst du dort `https://github.com/k696969/Profit-bot`
> ein, holt sich der Server die Dateien automatisch selbst – dann kannst du das
> manuelle Hochladen überspringen.

---

## TEIL 4 · `.env`-Datei mit Token anlegen ⭐ wichtig

Hier kommt dein Token rein. Der Bot liest ihn automatisch aus dieser Datei.

1. Im Reiter **„Files"** auf **„New File"** (Neue Datei).
2. Dateiname **exakt**:  `.env`   (mit Punkt am Anfang!)
3. Inhalt einfügen (deinen echten Token + Server-ID einsetzen):

   ```
   DISCORD_TOKEN=dein_token_hier_einfuegen
   GUILD_ID=deine_server_id_hier
   DB_PATH=resell_data.db
   POLL_INTERVAL_MIN=20
   ```

4. **Speichern** (Save).

   ```
   ┌─ .env ───────────────────────────────────┐
   │ DISCORD_TOKEN=MTIzNDU2Nzg5MD...           │  ← dein Bot-Token
   │ GUILD_ID=112233445566778899               │  ← deine Server-ID
   │ DB_PATH=resell_data.db                     │
   │ POLL_INTERVAL_MIN=20                        │
   └────────────────────────────────────────────┘
   ```

> ⚠️ **Den Token NIEMALS woanders posten oder auf GitHub hochladen.** Er gehört
> nur in diese `.env` auf dem Server. (Die `.env` ist in `.gitignore` – sie
> landet absichtlich nie auf GitHub.)

---

## TEIL 5 · Startdatei einstellen & starten

1. Reiter **„Startup"**.
2. Beim Feld **„Main/App Python File"** (oder „Python File") eintragen:
   ```
   vinted_profit_bot.py
   ```
3. Falls es ein Feld **„Additional Python Packages"** oder
   **„Auto-Install requirements.txt"** gibt → sicherstellen, dass
   `requirements.txt` installiert wird (meist automatisch, da die Datei vorhanden ist).
   Notfalls dort manuell eintragen: `discord.py requests python-dotenv`
4. Zurück zum Reiter **„Console"** → **„Start"** klicken.
5. Beim ersten Start installiert er die Pakete (dauert ~1 Min). Danach erscheint:

   ```
   ✅ Eingeloggt als Resell-Bot#1234 — 12 Befehle bereit. Watch-Intervall: 20 Min.
   ```

---

## TEIL 6 · Testen

1. Dein Bot ist im Discord jetzt **grün/online**.
2. Tippe `/` in einen Channel → die Befehle erscheinen (sofort, dank `GUILD_ID`).
3. Probiere:

   ```
   /profit  verkaufspreis: 45   einkaufspreis: 20
   ```

   → Du bekommst den Profit-Vergleich als Embed. 🎉

4. Such-Alarm mit **Bild + Kalkulation**:

   ```
   /watch  suchbegriff: Nike TN 42   max_preis: 30
   ```

---

## ⚠️ Daten-Hinweis (wichtig bei Gratis-Hosting)

Dein Inventar liegt in der Datei `resell_data.db` auf dem Server. Solange der
Server bestehen bleibt, bleibt sie erhalten. Wird der Server aber **gelöscht**
(z. B. weil längere Zeit keine Coins da waren), ist auch das Inventar weg.

**Sicher gehen:** ab und zu im Reiter „Files" die Datei `resell_data.db`
herunterladen = dein Backup. Wer es dauerhaft stabil will, nimmt langfristig
**Oracle Cloud Always Free** (siehe unten).

---

## 🔄 Bot am Laufen halten

- **Coins:** täglich einmal bei bot-hosting.net einloggen (Login-Bonus) und/oder
  die **AFK-Seite** offen lassen. Solange Coins da sind, läuft der Bot rund um
  die Uhr.
- **Bot abgestürzt?** Reiter „Console" → „Start" / „Restart".
- **Code aktualisiert (auf GitHub)?** Neue `vinted_profit_bot.py` herunterladen
  und im „Files"-Reiter hochladen (alte überschreiben) → „Restart". Oder, falls
  du die Git-Repo-Option aus Teil 3 nutzt: „Pull"/Neustart.

---

## ❓ Häufige Probleme

| Problem | Lösung |
|---|---|
| **Console: `❌ DISCORD_TOKEN setzen`** | `.env`-Datei prüfen: heißt sie wirklich `.env` (mit Punkt)? Token korrekt, ohne Leerzeichen/Anführungszeichen? |
| **Befehle `/profit` erscheinen nicht** | `GUILD_ID` in der `.env` gesetzt? Sonst bis zu 1 Std warten. |
| **`ModuleNotFoundError: discord`** | `requirements.txt` mit hochgeladen? In „Startup" Auto-Install aktiv? Notfalls Packages manuell eintragen (Teil 5.3). |
| **Bot geht nachts offline** | Coins leer. Einloggen / AFK-Seite nutzen. |
| **„Auto-Abruf fehlgeschlagen" bei Links** | Vinted/eBay blocken Automatik manchmal. Manuelle Felder nutzen: `einkaufspreis` + `verkaufspreis` – geht immer. |

---

## 🔒 Dauerhaft stabil später?

Wenn dir das Coin-Sammeln zu lästig wird, ist **Oracle Cloud Always Free** die
beste dauerhaft-kostenlose Lösung (eigener kleiner Linux-Server, läuft ohne
Coins durch). Es ist etwas technischer und braucht eine Kreditkarte **nur zur
Verifizierung** (kostet nichts). Sag Bescheid, dann schreibe ich dir auch dafür
eine Anleitung.
