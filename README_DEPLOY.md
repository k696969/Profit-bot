# 🚀 Bot online bringen – Schritt-für-Schritt-Tutorial

Diese Anleitung bringt deinen **Resell-Bot (Vinted ↔ eBay)** dauerhaft online,
sodass er 24/7 läuft – auch wenn dein PC aus ist.

> 💸 **Railway kostet inzwischen Geld (kein Gratis-Tarif mehr).**
> Willst du es **komplett kostenlos & ohne Kreditkarte**? → Nimm
> **[TUTORIAL_BOTHOSTING.md](TUTORIAL_BOTHOSTING.md)** (bot-hosting.net).
> Die Railway-Anleitung unten lohnt sich nur, wenn du bereits Credits hast.

> **Warum „funktioniert er nicht"?**
> Ein Discord-Bot ist ein Programm, das **dauerhaft laufen** muss. Solange er nur
> auf deinem PC startet, ist er offline, sobald du das Fenster schließt. Damit er
> immer erreichbar ist, muss er auf einem **Server in der Cloud** laufen.
> Außerdem braucht er einen **DISCORD_TOKEN** (sein „Passwort"). Fehlt der, startet
> er gar nicht. Beides erledigen wir hier.

---

## 📋 Überblick – was wir tun

```
1. Discord-Bot erstellen   →  Token + Einladung in deinen Server
2. Code auf GitHub          →  hast du schon ✅
3. Auf Railway hochladen    →  Server, der den Bot 24/7 laufen lässt
4. Token + Einstellungen    →  als "Variables" eintragen
5. Volume anhängen          →  damit dein Inventar nicht verloren geht
6. Testen                   →  /profit im Discord eingeben
```

Dauer: ca. **20–30 Minuten**. Kosten: Railway hat ein **kostenloses Startguthaben**;
ein kleiner Bot wie dieser kostet danach ~3–5 $/Monat.

---

## TEIL 1 · Discord-Bot erstellen (Token holen)

1. Gehe auf 👉 **https://discord.com/developers/applications**
2. Oben rechts **„New Application"** → Name eingeben (z. B. `Resell-Bot`) → **Create**.
3. Links im Menü auf **„Bot"** klicken.
4. **„Reset Token"** → **Yes, do it!** → der Token wird angezeigt.
   - Klicke **„Copy"** und speichere ihn sicher (z. B. in Notizen).
   - ⚠️ **Diesen Token NIEMALS öffentlich teilen oder in GitHub hochladen!**
     Wer ihn hat, kann deinen Bot übernehmen.

   ```
   ┌─────────────────────────────────────────────┐
   │  TOKEN                                       │
   │  MTIzNDU2Nzg5...   [ Copy ]   [ Reset Token ] │  ← das ist dein DISCORD_TOKEN
   └─────────────────────────────────────────────┘
   ```

5. **Privileged Gateway Intents:** Dieser Bot braucht **keine** speziellen Intents
   (er nutzt nur Slash-Befehle). Du kannst alles auf Standard lassen.

### Bot in deinen Server einladen

6. Links auf **„OAuth2"** → **„URL Generator"**.
7. Bei **SCOPES** ankreuzen:  ✅ `bot`   ✅ `applications.commands`
8. Bei **BOT PERMISSIONS** ankreuzen:
   ✅ `Send Messages`  ✅ `Embed Links`  ✅ `Read Message History`
9. Ganz unten die **„Generated URL"** kopieren, im Browser öffnen,
   deinen Server auswählen → **Autorisieren**.

✅ Der Bot ist jetzt in deinem Server – aber noch **grau/offline**.
Das ändert sich, sobald er in der Cloud läuft (Teil 3).

---

## TEIL 2 · Server-ID holen (Befehle erscheinen SOFORT)

Ohne diesen Schritt dauert es bis zu **1 Stunde**, bis die `/`-Befehle erscheinen.
Mit der Server-ID (`GUILD_ID`) sind sie **sofort** da.

1. Discord öffnen → **Einstellungen** (Zahnrad) → **Erweitert** →
   **Entwicklermodus** einschalten.
2. **Rechtsklick auf deinen Server** (oben links das Server-Icon) →
   **„Server-ID kopieren"**.
3. Diese Zahl merken – das ist deine **`GUILD_ID`**.

---

## TEIL 3 · Auf Railway hochladen (24/7-Server)

Railway lässt dein Programm dauerhaft laufen. GitHub ist schon verbunden mit
deinem Repo `k696969/profit-bot`.

1. Gehe auf 👉 **https://railway.app** → **Login with GitHub**.
2. **„New Project"** → **„Deploy from GitHub repo"**.
3. Wähle dein Repo **`profit-bot`** aus.
   - Falls Railway nach Zugriff fragt: **„Configure GitHub App"** → Repo freigeben.
4. Railway erkennt automatisch:
   - `requirements.txt` → installiert `discord.py` + `requests`
   - `runtime.txt` → nutzt **Python 3.12**
   - `Procfile` → startet `worker: python vinted_profit_bot.py`
5. Der erste Deploy startet – **schlägt aber noch fehl**, weil der Token fehlt.
   Das ist normal. Weiter mit Teil 4.

---

## TEIL 4 · Token & Einstellungen eintragen (Variables)

1. In Railway: dein Projekt öffnen → auf den **Service** (die Bot-Kachel) klicken.
2. Reiter **„Variables"** → **„New Variable"**. Trage folgende ein:

   | Name (Key)         | Wert (Value)                          | Pflicht?                   |
   |--------------------|---------------------------------------|----------------------------|
   | `DISCORD_TOKEN`    | *dein Token aus Teil 1*               | ✅ JA                      |
   | `GUILD_ID`         | *deine Server-ID aus Teil 2*          | empfohlen (Befehle sofort) |
   | `DB_PATH`          | `/data/resell_data.db`                | empfohlen (siehe Teil 5)   |
   | `POLL_INTERVAL_MIN`| `20`                                  | optional (Watch-Frequenz)  |

3. **Speichern.** Railway startet den Bot automatisch neu.

> 💡 `POLL_INTERVAL_MIN` = wie oft der Watch-Alarm Vinted prüft (in Minuten).
> Nicht zu niedrig setzen (min. 15–20), sonst blockt Vinted die Abfragen.

---

## TEIL 5 · Volume anhängen (Daten dauerhaft speichern)

Ohne dies wird dein **Inventar bei jedem Update gelöscht**, weil der Server jedes
Mal frisch startet. Ein „Volume" ist eine dauerhafte Festplatte.

1. Im Service auf **„Settings"** (oder Reiter **„Volumes"**) → **„New Volume"**.
2. **Mount Path** eingeben:  `/data`
3. Speichern. (Dein `DB_PATH` aus Teil 4 zeigt genau auf dieses Volume.)

✅ Jetzt überleben Inventar & Such-Alarme jeden Neustart.

---

## TEIL 6 · Testen

1. In Railway: Reiter **„Deployments"** → **„View Logs"**.
   Wenn alles passt, siehst du:

   ```
   ✅ Eingeloggt als Resell-Bot#1234 — 12 Befehle bereit. Watch-Intervall: 20 Min.
   ```

2. Im Discord ist der Bot jetzt **grün/online**.
3. Tippe `/` in einen Channel → die Befehle erscheinen. Probiere:

   ```
   /profit  verkaufspreis: 45   einkaufspreis: 20
   ```

   Du bekommst ein Embed wie dieses:

   ```
   💰 Profit-Vergleich — Manueller Artikel
   ────────────────────────────────────────
   🛒 Gekauft auf:      Vinted
   Einkaufspreis:        20.00 €
   Käuferschutz:          1.70 €
   ➡️ Einkauf gesamt:    21.70 €

   🟢 Verkauf auf VINTED
   VK 45.00 € · Gebühr 0 €
   → Profit 23.30 €  · Marge 107 %

   🟡 Verkauf auf EBAY
   VK 45.00 € · Gebühr −5.40 €
   → Profit 17.90 €  · Marge 82 %

   Empfehlung: 🏆 Vinted lohnt sich – 5.40 € mehr.
   ```

🎉 **Fertig – dein Bot läuft jetzt 24/7!**

---

## 🔔 Such-Alarm mit Bild & Kalkulation

Genau wie gewünscht: Sobald ein neuer Treffer reinkommt, postet der Bot
**automatisch ein Embed mit Produktfoto + fertiger Profit-Kalkulation**.

So legst du einen Alarm an:

```
/watch  suchbegriff: Nike TN 42   max_preis: 30
```

Wenn der Bot dann einen passenden Vinted-Artikel ≤ 30 € findet, postet er z. B.:

```
🔔 @du
┌──────────────────────────────────────────────┐
│ 🟢 Neuer Treffer — Nike TN Air Max 42         │
│ Suche: Nike TN 42 · Limit ≤ 30.00 €           │
│                                                │
│  [ 📷 Produktfoto ]                            │
│                                                │
│ 🛒 Vinted-Preis (Einkauf):   25.00 €          │
│ 📊 eBay-Marktwert (Median):  79.00 €          │
│ Unter Marktwert:             68 %             │
│                                                │
│ 🟢 Geschätzter Weiterverkauf auf eBay         │
│ VK 79.00 € · Gebühr −9.48 € · Einkauf −26.95 €│
│ → Profit 42.57 €  ·  Marge 158 %              │
│                                                │
│ Marktwert aus 22 verkauften eBay-Angeboten    │
└──────────────────────────────────────────────┘
```

- 🟢 = Top-Deal (hohe Marge + deutlich unter Marktwert)
- 🟡 = grenzwertig (kleiner Gewinn)
- 🔴 = lohnt sich nicht

> Der eBay-Marktwert wird automatisch im Hintergrund geschätzt (best effort).
> Falls eBay gerade blockt, kommt der Treffer trotzdem – nur ohne Kalkulation,
> dann einfach manuell mit `/deal <link>` prüfen.

---

## ❓ Häufige Probleme

| Problem | Lösung |
|---|---|
| **Bot bleibt offline / Logs zeigen `❌ DISCORD_TOKEN setzen`** | Token in Railway → Variables eingetragen? Richtig kopiert (ohne Leerzeichen)? |
| **Befehle (`/profit`) erscheinen nicht** | `GUILD_ID` setzen (Teil 2) → erscheinen sofort. Ohne GUILD_ID bis zu 1 Std warten. |
| **Inventar nach Update weg** | Volume anhängen + `DB_PATH=/data/resell_data.db` (Teil 5). |
| **„Auto-Abruf fehlgeschlagen" bei Links** | Vinted/eBay blocken Automatik manchmal. Nutze die manuellen Felder: `einkaufspreis` + `verkaufspreis`. Funktioniert immer. |
| **Watch findet nichts / keine Kalkulation** | Normal bei Blockade. `POLL_INTERVAL_MIN` nicht unter 15 setzen. Treffer kommt trotzdem, nur ohne eBay-Median. |
| **Deploy schlägt fehl (Build error)** | Logs ansehen. Meist fehlt eine Variable – prüfe Teil 4. |

---

## 🔒 Sicherheit

- Den **DISCORD_TOKEN niemals** in den Code schreiben oder auf GitHub pushen.
  Er gehört **ausschließlich** in die Railway-Variables.
- Falls der Token doch mal öffentlich wurde: in Discord → Developer Portal →
  Bot → **„Reset Token"**, neuen in Railway eintragen.

---

## 🔄 Updates einspielen

Wenn du am Code etwas änderst:
1. Änderung auf GitHub pushen (in den `main`-Branch).
2. Railway erkennt das automatisch und deployt die neue Version.

Fertig – kein manueller Neustart nötig.
```

---

## Alternative Hosts (falls kein Railway)

Der Code läuft überall, wo Python 3.12 + ein dauerhafter „Worker"-Prozess möglich
ist. Das Prinzip ist immer gleich: **Repo verbinden → `DISCORD_TOKEN` als Variable
→ Worker starten → Volume für die DB**.

- **Render.com** – „Background Worker", ähnlich wie Railway.
- **Fly.io** – etwas technischer, mit Volume.
- **Eigener Server / Raspberry Pi** – `pip install -r requirements.txt`,
  `DISCORD_TOKEN` als Umgebungsvariable setzen, dann
  `python vinted_profit_bot.py` (am besten via `systemd` als Dienst).

Bei allen gilt: ohne dauerhaft laufenden Prozess geht der Bot offline.
