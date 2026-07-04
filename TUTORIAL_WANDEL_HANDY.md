# 📱 Wandel-Bot komplett vom Handy einrichten

Diese Anleitung bringt deinen **Abnehm-Bot (Wandel)** online — **nur mit dem
Handy**, kein PC nötig. Dauer: ~15–20 Minuten.

Du kennst den Ablauf schon vom Resell-Bot ([TUTORIAL_BOTHOSTING.md](TUTORIAL_BOTHOSTING.md)).
Neu ist nur: Der Wandel-Bot braucht eine **eigene Bot-Application** (eigener
Token), und mit `start_beide.py` laufen **beide Bots auf deinem vorhandenen
Gratis-Server** — du brauchst keinen zweiten Server und keine extra Coins.

---

## 📋 Überblick

```
1. Neue Bot-Application erstellen (Handy-Browser)  → Token kopieren
2. Bot auf deinen Discord-Server einladen
3. Dateien auf deinen bot-hosting-Server laden
4. .env um WANDEL_TOKEN ergänzen
5. Startdatei auf start_beide.py umstellen + Restart
6. /profil in Discord ausfüllen — fertig
```

---

## TEIL 1 · Neue Bot-Application (im Handy-Browser)

> 💡 Das Discord Developer Portal funktioniert im Handy-Browser. Falls etwas
> abgeschnitten aussieht: im Browser-Menü **„Desktop-Website anfordern"**
> aktivieren (Chrome: ⋮-Menü · Safari: aA-Symbol).

1. Öffne 👉 **https://discord.com/developers/applications** und logg dich ein.
2. Tippe **„New Application"** → Name: `Wandel` → erstellen.
3. Links im Menü (☰-Symbol) auf **„Bot"**.
4. Tippe **„Reset Token"** → bestätigen → **Token kopieren** 📋
   und z. B. in deine Discord-Selbstnachrichten zwischenspeichern
   (danach dort wieder löschen!).

> ⚠️ Der Token ist wie ein Passwort. Niemals öffentlich posten, niemals auf
> GitHub. Er kommt gleich nur in die `.env` auf deinem Hosting-Server.

---

## TEIL 2 · Bot auf deinen Server einladen

1. Im Developer Portal links auf **„OAuth2"** → **„URL Generator"**.
2. Bei **Scopes** ankreuzen: ☑ `bot`  ☑ `applications.commands`
3. Bei **Bot Permissions** ankreuzen:
   ☑ Send Messages  ☑ Embed Links  ☑ Attach Files
   (Attach Files braucht er für das Gewichts-Chart-Bild!)
4. Ganz unten die **generierte URL kopieren** → in neuem Browser-Tab öffnen
   → deinen Discord-Server auswählen → **Autorisieren**.
5. Der Bot erscheint jetzt (offline) in deiner Mitgliederliste. ✅

Deine **Server-ID (GUILD_ID)** hast du schon in der `.env` — die gilt auch für
den Wandel-Bot. (Falls nicht: Discord-App → Einstellungen → Erweitert →
Entwicklermodus an → lange auf den Servernamen drücken → „ID kopieren".)

---

## TEIL 3 · Dateien auf den Hosting-Server laden

Öffne 👉 **https://bot-hosting.net** im Handy-Browser → Login with Discord →
dein vorhandener Server → Reiter **„Files"**.

Du brauchst **3 neue/aktualisierte Dateien** aus GitHub (Branch beachten!):

| Datei | Direkt-Link (öffnen → Inhalt kopieren oder herunterladen) |
|---|---|
| `wandel_bot.py` | https://raw.githubusercontent.com/k696969/Profit-bot/claude/weight-loss-transformation-l63gow/wandel_bot.py |
| `start_beide.py` | https://raw.githubusercontent.com/k696969/Profit-bot/claude/weight-loss-transformation-l63gow/start_beide.py |
| `requirements.txt` | https://raw.githubusercontent.com/k696969/Profit-bot/claude/weight-loss-transformation-l63gow/requirements.txt |

**Weg A — Hochladen (empfohlen):** Link öffnen → Browser-Menü → „Seite
speichern"/Download → im bot-hosting-Panel unter „Files" → **Upload** → Datei
aus deinem Download-Ordner wählen. (`requirements.txt`: die alte überschreiben.)

**Weg B — Copy & Paste:** Link öffnen → alles markieren & kopieren → im Panel
**„New File"** → exakt benennen (z. B. `wandel_bot.py`) → einfügen → Save.

---

## TEIL 4 · `.env` ergänzen ⭐ wichtig

Im Reiter **„Files"** deine vorhandene **`.env`** antippen → bearbeiten →
**eine Zeile ergänzen** (dein neuer Token aus TEIL 1):

```
DISCORD_TOKEN=dein_resell_bot_token      ← bleibt wie es ist
WANDEL_TOKEN=dein_neuer_wandel_token     ← NEU
GUILD_ID=deine_server_id                 ← bleibt
DB_PATH=resell_data.db                   ← bleibt
```

→ **Save.** (Und jetzt den zwischengespeicherten Token aus deinen
Discord-Nachrichten löschen.)

---

## TEIL 5 · Beide Bots zusammen starten

1. Reiter **„Startup"** → beim Feld **„Main/App Python File"** eintragen:
   ```
   start_beide.py
   ```
   (Das Skript startet Resell-Bot **und** Wandel-Bot zusammen und startet
   einen Bot automatisch neu, falls er abstürzt.)
2. Reiter **„Console"** → **Restart**.
3. Erster Start dauert ein paar Minuten (er installiert matplotlib fürs
   Chart-Bild). Danach siehst du in der Console:
   ```
   🚀 Gestartet: vinted_profit_bot.py, wandel_bot.py
   ✅ Eingeloggt als Resell-Bot#1234 …
   ✅ Wandel-Bot eingeloggt als Wandel#5678 (matplotlib: ja)
   ```

> 🐌 **Installation schlägt fehl / Speicher voll?** matplotlib ist groß.
> Dann in `requirements.txt` die Zeile `matplotlib>=3.8` löschen → Restart.
> Der Wandel-Bot läuft trotzdem — `/verlauf` zeigt den Verlauf dann als Text
> statt als Bild.

---

## TEIL 6 · Loslegen in Discord 🎉

Beide Bots sind jetzt grün/online. In einem Channel:

1. **`/profil`** — einmal ausfüllen (Geschlecht, Alter, Größe, Gewicht,
   Aktivität, Zielgewicht, Tempo). Antwort: deine berechneten Werte
   (Tagesziel kcal, Protein, Wasser). Sieht nur du (ephemeral).
2. Täglich:
   - `/wiegen kg: 94.6` — morgens, nüchtern
   - `/essen name: Haferflocken kcal: 450 protein: 35`
   - `/training art: Joggen minuten: 30` (oder `eigene_kcal:` von der Sportuhr)
   - `/wasser` — pro Glas einmal tippen
   - `/heute` — deine Tagesbilanz
3. `/verlauf` — Gewichtskurve als Bild, Trend, Prognose-Datum
4. `/erinnerung modus: An stunde: 8` — täglicher Wiege-Ping in dem Channel
5. `/quellen` — die Studien hinter allen Berechnungen

> 🔒 Alle Antworten des Bots sind **nur für dich sichtbar** (ephemeral) —
> auch auf einem Server mit anderen Leuten.

---

## ❓ Häufige Probleme

| Problem | Lösung |
|---|---|
| Wandel-Befehle erscheinen nicht | `GUILD_ID` in `.env`? Bot mit Scope `applications.commands` eingeladen (TEIL 2)? Sonst bis zu 1 Std. warten. In der Discord-App hilft oft: App schließen & neu öffnen. |
| `❌ Bitte WANDEL_TOKEN setzen` | `.env` prüfen: Zeile `WANDEL_TOKEN=…` ohne Leerzeichen/Anführungszeichen? |
| Nur ein Bot geht online | Console lesen: welcher fehlt? Meist Token-Zeile falsch. Beide Bots brauchen **verschiedene** Tokens von **verschiedenen** Applications. |
| Kein Chart bei `/verlauf` | matplotlib nicht installiert (siehe TEIL 5) — oder erst < 2 Gewichtseinträge. |
| Bot antwortet „kein Profil" | Zuerst `/profil` ausfüllen. |
| Daten weg nach Server-Neuanlage | `wandel_data.db` ab und zu im „Files"-Reiter herunterladen = Backup (wie beim Resell-Bot). |

---

## 💾 Backup-Tipp

Deine Tracking-Daten liegen in **`wandel_data.db`** auf dem Hosting-Server.
Einmal die Woche im „Files"-Reiter antippen → Download = Backup aufs Handy.
