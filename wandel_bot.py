"""
═══════════════════════════════════════════════════════════════
  WANDEL-BOT  ·  Abnehm- & Transformations-Tracker  ·  Discord
═══════════════════════════════════════════════════════════════

BEFEHLE
  /profil      Profil anlegen (Geschlecht, Alter, Größe, Gewicht, Ziel …)
               → berechnet Grundumsatz, Gesamtumsatz, Tagesziel, Protein, Wasser
  /werte       Deine berechneten Werte anzeigen
  /heute       Tagesbilanz: gegessen, verbrannt, übrig, Protein, Wasser
  /essen       Mahlzeit eintragen (Name, kcal, optional Protein)
  /training    Training eintragen — Schnellauswahl (MET) oder eigene kcal
  /wiegen      Tagesgewicht eintragen (überschreibt heutigen Wert)
  /wasser      Wasser tracken (Gläser à 250 ml)
  /verlauf     Gewichtsverlauf, Trend, Prognose + Chart-Bild
  /rueckgaengig  Letzten Eintrag von heute löschen (Mahlzeit/Training)
  /erinnerung  Tägliche Erinnerung in diesem Kanal an/aus
  /quellen     Wissenschaftliche Grundlagen mit Studien-Links

WISSENSCHAFTLICHE BASIS (Details: /quellen)
  Grundumsatz: Mifflin-St Jeor (Frankenfield 2005: genaueste Formel)
  Tempo: 0,5–1 kg/Woche (CDC/NHS) · Defizit ≈ 7 700 kcal/kg (Näherung, Hall 2011)
  Protein: 1,6 g/kg Zielgewicht (Morton 2018) · Wasser: EFSA 2010
  Training: Netto-METs, Compendium of Physical Activities (Ainsworth 2011)

SETUP (wie beim Resell-Bot, siehe README_DEPLOY.md / TUTORIAL_BOTHOSTING.md)
  1. Eigenen Bot im Discord Developer Portal anlegen (zweite Application!)
  2. Token als Umgebungsvariable WANDEL_TOKEN setzen
     (Fallback: DISCORD_TOKEN, falls der Bot alleine läuft)
  3. Start: python wandel_bot.py
  4. Optional: GUILD_ID setzen → Befehle erscheinen sofort
  5. Optional: matplotlib installieren → /verlauf schickt ein Chart-Bild
     (ohne matplotlib gibt es den Verlauf als Text — der Bot läuft trotzdem)

Persistenz: SQLite (WANDEL_DB_PATH, Standard wandel_data.db). Auf Railway
ein Volume anhängen, sonst gehen Daten beim Neu-Deploy verloren.
═══════════════════════════════════════════════════════════════
"""

import io
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import tasks

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

DB_PATH  = os.environ.get("WANDEL_DB_PATH", "wandel_data.db")
GUILD_ID = os.environ.get("GUILD_ID")

GLAS_LITER = 0.25          # ein Glas = 250 ml
KCAL_PRO_KG = 7700.0       # Näherung Energiegehalt Körperfett (Hall 2011: linear = grob)
MIN_KCAL = {"m": 1500, "w": 1200}   # übliche klinische Untergrenzen

# Netto-MET-Presets (Compendium of Physical Activities, Ainsworth 2011).
# Verrechnet wird MET−1, damit der Grundumsatz nicht doppelt zählt.
MET_PRESETS = {
    "gehen":     ("Gehen (4,8 km/h)",          3.5),
    "zuegig":    ("Zügiges Gehen (5,6 km/h)",  4.3),
    "joggen":    ("Joggen",                    7.0),
    "rad":       ("Radfahren (16–19 km/h)",    6.8),
    "kraft":     ("Krafttraining",             3.5),
    "schwimmen": ("Schwimmen (locker)",        6.0),
    "hiit":      ("HIIT",                      8.0),
}

PAL_CHOICES = [
    app_commands.Choice(name="Sitzend, kaum Bewegung (Büro/Homeoffice)", value="1.2"),
    app_commands.Choice(name="Leicht aktiv (etwas Gehen im Alltag)",     value="1.375"),
    app_commands.Choice(name="Mäßig aktiv (viel auf den Beinen)",        value="1.55"),
    app_commands.Choice(name="Sehr aktiv (körperliche Arbeit)",          value="1.725"),
    app_commands.Choice(name="Extrem aktiv (schwere körperl. Arbeit)",   value="1.9"),
]
TEMPO_CHOICES = [
    app_commands.Choice(name="Gemütlich — 0,25 kg/Woche",                value="0.25"),
    app_commands.Choice(name="Empfohlen — 0,5 kg/Woche",                 value="0.5"),
    app_commands.Choice(name="Zügig — 0,75 kg/Woche",                    value="0.75"),
    app_commands.Choice(name="Obergrenze der Leitlinien — 1 kg/Woche",   value="1.0"),
]
PROTEIN_CHOICES = [
    app_commands.Choice(name="1,2 g/kg — Basis ohne Training",                       value="1.2"),
    app_commands.Choice(name="1,6 g/kg — belegtes Optimum (Morton 2018)",            value="1.6"),
    app_commands.Choice(name="2,2 g/kg — Diät + hartes Krafttraining (Helms 2014)",  value="2.2"),
]
TRAINING_CHOICES = [app_commands.Choice(name=n, value=k) for k, (n, _) in MET_PRESETS.items()]

GRUEN = 0x1E6F5C   # Akzentfarbe der Wandel-App


# ══════════════ DATENBANK ══════════════
def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_conn()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS profile (
        user_id   INTEGER PRIMARY KEY,
        sex       TEXT NOT NULL,
        alter_j   INTEGER NOT NULL,
        groesse   INTEGER NOT NULL,
        start_kg  REAL NOT NULL,
        pal       REAL NOT NULL,
        ziel_kg   REAL NOT NULL,
        tempo     REAL NOT NULL,
        protein_f REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS gewicht (
        user_id INTEGER NOT NULL,
        datum   TEXT NOT NULL,
        kg      REAL NOT NULL,
        PRIMARY KEY (user_id, datum)
    );
    CREATE TABLE IF NOT EXISTS mahlzeit (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        datum   TEXT NOT NULL,
        name    TEXT NOT NULL,
        kcal    INTEGER NOT NULL,
        protein INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS training (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        datum   TEXT NOT NULL,
        name    TEXT NOT NULL,
        kcal    INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS wasser (
        user_id INTEGER NOT NULL,
        datum   TEXT NOT NULL,
        glaeser INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, datum)
    );
    CREATE TABLE IF NOT EXISTS erinnerung (
        user_id    INTEGER PRIMARY KEY,
        channel_id INTEGER NOT NULL,
        stunde     INTEGER NOT NULL
    );
    """)
    con.commit()
    con.close()


def heute() -> str:
    return date.today().isoformat()


def fmt(n, digits=0) -> str:
    """Deutsche Zahlformatierung: 1.234,5"""
    s = f"{n:,.{digits}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ══════════════ BERECHNUNGEN (identisch zur Wandel-Website) ══════════════
def get_profile(user_id):
    con = get_conn()
    row = con.execute("SELECT * FROM profile WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row


def aktuelles_gewicht(user_id, profil=None):
    con = get_conn()
    row = con.execute("SELECT kg FROM gewicht WHERE user_id=? ORDER BY datum DESC LIMIT 1",
                      (user_id,)).fetchone()
    con.close()
    if row:
        return row["kg"]
    return profil["start_kg"] if profil else None


def berechne(profil, kg):
    """Grundumsatz (Mifflin-St Jeor), Gesamtumsatz, Tagesziel, Protein, Wasser."""
    if profil["sex"] == "m":
        bmr = 10 * kg + 6.25 * profil["groesse"] - 5 * profil["alter_j"] + 5
    else:
        bmr = 10 * kg + 6.25 * profil["groesse"] - 5 * profil["alter_j"] - 161
    tdee = bmr * profil["pal"]
    defizit = profil["tempo"] * KCAL_PRO_KG / 7
    minimum = MIN_KCAL[profil["sex"]]
    ziel_raw = tdee - defizit
    ziel = max(ziel_raw, minimum)
    # Protein aufs Zielgewicht bezogen (Körperfett überzeichnet den Bedarf sonst)
    protein_basis = min(kg, profil["ziel_kg"])
    # EFSA 2010: Gesamtwasser 2,5/2,0 l — davon ~80 % aus Getränken
    wasser_l = 2.0 if profil["sex"] == "m" else 1.6
    return {
        "bmr": round(bmr), "tdee": round(tdee), "defizit": round(defizit),
        "ziel": round(ziel), "gedeckelt": ziel_raw < minimum,
        "protein": round(profil["protein_f"] * protein_basis),
        "protein_basis": protein_basis,
        "wasser_glaeser": round(wasser_l / GLAS_LITER),
    }


def tages_summen(user_id, datum):
    con = get_conn()
    m = con.execute("SELECT COALESCE(SUM(kcal),0) k, COALESCE(SUM(protein),0) p "
                    "FROM mahlzeit WHERE user_id=? AND datum=?", (user_id, datum)).fetchone()
    t = con.execute("SELECT COALESCE(SUM(kcal),0) k FROM training WHERE user_id=? AND datum=?",
                    (user_id, datum)).fetchone()
    w = con.execute("SELECT glaeser FROM wasser WHERE user_id=? AND datum=?",
                    (user_id, datum)).fetchone()
    con.close()
    return {"gegessen": m["k"], "protein": m["p"], "verbrannt": t["k"],
            "glaeser": w["glaeser"] if w else 0}


def gewichts_trend(user_id):
    """Lineare Regression über die letzten 21 Tage → kg pro Tag (oder None)."""
    grenze = (date.today() - timedelta(days=21)).isoformat()
    con = get_conn()
    rows = con.execute("SELECT datum, kg FROM gewicht WHERE user_id=? AND datum>=? ORDER BY datum",
                       (user_id, grenze)).fetchall()
    con.close()
    if len(rows) < 3:
        return None
    xs = [date.fromisoformat(r["datum"]).toordinal() for r in rows]
    ys = [r["kg"] for r in rows]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else None


def prognose(user_id, profil, kg):
    """Zieldatum — bevorzugt aus dem echten Trend (Hall 2011: linear überschätzt)."""
    if kg is None or kg <= profil["ziel_kg"]:
        return None
    trend = gewichts_trend(user_id)
    if trend is not None and trend < -0.01:
        pro_tag, basis = -trend, "deinem echten Trend"
    else:
        pro_tag, basis = profil["tempo"] / 7, "deinem geplanten Tempo"
    tage = int((kg - profil["ziel_kg"]) / pro_tag + 0.5)
    if tage > 365 * 3:
        return None
    return date.today() + timedelta(days=tage), basis


# ══════════════ DISCORD ══════════════
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def braucht_profil(user_id):
    p = get_profile(user_id)
    if p is None:
        return None, ("⚠️ Du hast noch kein Profil. Leg zuerst eins an mit "
                      "`/profil` — daraus berechne ich alle deine Werte.")
    return p, None


@client.event
async def on_ready():
    init_db()
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    else:
        await tree.sync()
    if not erinnerungs_loop.is_running():
        erinnerungs_loop.start()
    print(f"✅ Wandel-Bot eingeloggt als {client.user} (matplotlib: {'ja' if HAS_MPL else 'nein'})")


# ────────── /profil ──────────
@tree.command(name="profil", description="Profil anlegen/ändern — berechnet deinen Kalorienbedarf (Mifflin-St Jeor)")
@app_commands.describe(
    geschlecht="Für die Grundumsatz-Formel",
    alter="Alter in Jahren",
    groesse="Größe in cm",
    gewicht="Aktuelles Gewicht in kg",
    aktivitaet="Alltags-Aktivität OHNE Training (das trackst du mit /training)",
    zielgewicht="Zielgewicht in kg",
    tempo="Abnehmtempo (CDC/NHS: 0,5–1 kg/Woche)",
    protein="Proteinziel pro kg Zielgewicht",
)
@app_commands.choices(
    geschlecht=[app_commands.Choice(name="Männlich", value="m"),
                app_commands.Choice(name="Weiblich", value="w")],
    aktivitaet=PAL_CHOICES, tempo=TEMPO_CHOICES, protein=PROTEIN_CHOICES,
)
async def profil_cmd(inter: discord.Interaction, geschlecht: app_commands.Choice[str],
                     alter: app_commands.Range[int, 14, 100],
                     groesse: app_commands.Range[int, 120, 230],
                     gewicht: app_commands.Range[float, 30, 400],
                     aktivitaet: app_commands.Choice[str],
                     zielgewicht: app_commands.Range[float, 30, 400],
                     tempo: app_commands.Choice[str],
                     protein: app_commands.Choice[str] = None):
    protein_f = float(protein.value) if protein else 1.6
    con = get_conn()
    con.execute("""INSERT INTO profile (user_id, sex, alter_j, groesse, start_kg, pal, ziel_kg, tempo, protein_f)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(user_id) DO UPDATE SET sex=excluded.sex, alter_j=excluded.alter_j,
                     groesse=excluded.groesse, start_kg=excluded.start_kg, pal=excluded.pal,
                     ziel_kg=excluded.ziel_kg, tempo=excluded.tempo, protein_f=excluded.protein_f""",
                (inter.user.id, geschlecht.value, alter, groesse, gewicht,
                 float(aktivitaet.value), zielgewicht, float(tempo.value), protein_f))
    con.execute("INSERT OR REPLACE INTO gewicht (user_id, datum, kg) VALUES (?,?,?)",
                (inter.user.id, heute(), gewicht))
    con.commit()
    con.close()
    p = get_profile(inter.user.id)
    await inter.response.send_message(embed=werte_embed(p, gewicht, titel="Profil gespeichert ✅"),
                                      ephemeral=True)


def werte_embed(p, kg, titel="Deine berechneten Werte"):
    c = berechne(p, kg)
    e = discord.Embed(title=titel, color=GRUEN,
                      description=f"Basis: {fmt(kg, 1)} kg · Ziel {fmt(p['ziel_kg'], 1)} kg · "
                                  f"{fmt(p['tempo'], 2)} kg/Woche")
    e.add_field(name="Grundumsatz (Mifflin-St Jeor)", value=f"{fmt(c['bmr'])} kcal/Tag")
    e.add_field(name="Gesamtumsatz (× PAL)", value=f"{fmt(c['tdee'])} kcal/Tag")
    e.add_field(name="Geplantes Defizit", value=f"−{fmt(c['defizit'])} kcal/Tag")
    e.add_field(name="🎯 Dein Tagesziel", value=f"**{fmt(c['ziel'])} kcal/Tag**")
    e.add_field(name=f"Protein (auf {fmt(c['protein_basis'], 1)} kg)", value=f"{fmt(c['protein'])} g/Tag")
    e.add_field(name="Trinkmenge (EFSA)", value=f"{fmt(c['wasser_glaeser'] * GLAS_LITER, 2)} l/Tag")
    if c["gedeckelt"]:
        e.add_field(name="⚠️ Hinweis", inline=False,
                    value=f"Dein Tempo würde das Ziel unter das klinische Minimum drücken — "
                          f"ich habe es auf {fmt(c['ziel'])} kcal begrenzt. Wähle besser ein langsameres Tempo.")
    e.set_footer(text="Evidenzbasierte Richtwerte (/quellen) — kein Ersatz für ärztliche Beratung.")
    return e


# ────────── /werte ──────────
@tree.command(name="werte", description="Deine berechneten Werte: Grundumsatz, Tagesziel, Protein, Wasser")
async def werte_cmd(inter: discord.Interaction):
    p, err = braucht_profil(inter.user.id)
    if err:
        return await inter.response.send_message(err, ephemeral=True)
    kg = aktuelles_gewicht(inter.user.id, p)
    await inter.response.send_message(embed=werte_embed(p, kg), ephemeral=True)


# ────────── /heute ──────────
@tree.command(name="heute", description="Deine Tagesbilanz: gegessen, verbrannt, übrig, Protein, Wasser")
async def heute_cmd(inter: discord.Interaction):
    p, err = braucht_profil(inter.user.id)
    if err:
        return await inter.response.send_message(err, ephemeral=True)
    kg = aktuelles_gewicht(inter.user.id, p)
    c = berechne(p, kg)
    s = tages_summen(inter.user.id, heute())
    budget = c["ziel"] + s["verbrannt"]
    uebrig = budget - s["gegessen"]

    balken_len = 18
    anteil = min(1.0, s["gegessen"] / budget) if budget else 0
    balken = "█" * round(anteil * balken_len) + "░" * (balken_len - round(anteil * balken_len))

    e = discord.Embed(title=f"Heute · {date.today().strftime('%d.%m.%Y')}",
                      color=GRUEN if uebrig >= 0 else 0xD03B3B)
    e.add_field(name="Übrig" if uebrig >= 0 else "Über dem Ziel",
                value=f"**{fmt(abs(uebrig))} kcal**")
    e.add_field(name="Gegessen", value=f"{fmt(s['gegessen'])} / {fmt(budget)} kcal")
    e.add_field(name="Training", value=f"+{fmt(s['verbrannt'])} kcal Budget")
    e.add_field(name="Protein", value=f"{fmt(s['protein'])} / {fmt(c['protein'])} g")
    e.add_field(name="Wasser", value=f"{fmt(s['glaeser'] * GLAS_LITER, 2)} / "
                                     f"{fmt(c['wasser_glaeser'] * GLAS_LITER, 2)} l")
    con = get_conn()
    w = con.execute("SELECT kg FROM gewicht WHERE user_id=? AND datum=?",
                    (inter.user.id, heute())).fetchone()
    con.close()
    e.add_field(name="Gewicht heute", value=f"{fmt(w['kg'], 1)} kg" if w else "noch nicht gewogen (/wiegen)")
    e.add_field(name="Bilanz", value=f"`{balken}`", inline=False)
    await inter.response.send_message(embed=e, ephemeral=True)


# ────────── /essen ──────────
@tree.command(name="essen", description="Mahlzeit eintragen")
@app_commands.describe(name="Was hast du gegessen?", kcal="Kalorien", protein="Protein in g (optional)")
async def essen_cmd(inter: discord.Interaction, name: str,
                    kcal: app_commands.Range[int, 1, 5000],
                    protein: app_commands.Range[int, 0, 500] = 0):
    p, err = braucht_profil(inter.user.id)
    if err:
        return await inter.response.send_message(err, ephemeral=True)
    con = get_conn()
    con.execute("INSERT INTO mahlzeit (user_id, datum, name, kcal, protein) VALUES (?,?,?,?,?)",
                (inter.user.id, heute(), name, kcal, protein))
    con.commit()
    con.close()
    kg = aktuelles_gewicht(inter.user.id, p)
    c = berechne(p, kg)
    s = tages_summen(inter.user.id, heute())
    uebrig = c["ziel"] + s["verbrannt"] - s["gegessen"]
    zusatz = f" · Protein: {fmt(s['protein'])}/{fmt(c['protein'])} g" if protein else ""
    await inter.response.send_message(
        f"🍽️ **{name}** eingetragen ({fmt(kcal)} kcal). "
        f"Übrig heute: **{fmt(uebrig)} kcal**{zusatz}", ephemeral=True)


# ────────── /training ──────────
@tree.command(name="training", description="Training eintragen — Schnellauswahl (Netto-MET) oder eigene kcal")
@app_commands.describe(
    art="Schnellauswahl mit MET-Werten (Compendium of Physical Activities)",
    minuten="Dauer in Minuten (Standard 30)",
    eigene_kcal="Eigener kcal-Wert (z. B. von der Sportuhr) — überschreibt die Schnellauswahl",
    name="Eigener Name (nur bei eigene_kcal)")
@app_commands.choices(art=TRAINING_CHOICES)
async def training_cmd(inter: discord.Interaction,
                       art: app_commands.Choice[str] = None,
                       minuten: app_commands.Range[int, 1, 600] = 30,
                       eigene_kcal: app_commands.Range[int, 1, 5000] = None,
                       name: str = None):
    p, err = braucht_profil(inter.user.id)
    if err:
        return await inter.response.send_message(err, ephemeral=True)
    kg = aktuelles_gewicht(inter.user.id, p)
    if eigene_kcal:
        eintrag_name, kcal = (name or "Training"), eigene_kcal
    elif art:
        label, met = MET_PRESETS[art.value]
        # Netto-kcal: (MET − 1) × 3,5 × kg / 200 × Minuten — Grundumsatz zählt nicht doppelt
        kcal = round((met - 1) * 3.5 * kg / 200 * minuten)
        eintrag_name = f"{label} ({minuten} min)"
    else:
        return await inter.response.send_message(
            "Bitte `art` (Schnellauswahl) **oder** `eigene_kcal` angeben.", ephemeral=True)
    con = get_conn()
    con.execute("INSERT INTO training (user_id, datum, name, kcal) VALUES (?,?,?,?)",
                (inter.user.id, heute(), eintrag_name, kcal))
    con.commit()
    con.close()
    c = berechne(p, kg)
    s = tages_summen(inter.user.id, heute())
    uebrig = c["ziel"] + s["verbrannt"] - s["gegessen"]
    await inter.response.send_message(
        f"💪 **{eintrag_name}** eingetragen (−{fmt(kcal)} kcal). "
        f"Dein Budget heute: **{fmt(c['ziel'] + s['verbrannt'])} kcal**, übrig: **{fmt(uebrig)} kcal**",
        ephemeral=True)


# ────────── /wiegen ──────────
@tree.command(name="wiegen", description="Tagesgewicht eintragen (täglich wiegen hilft — Zheng 2015)")
@app_commands.describe(kg="Gewicht in kg, z. B. 92.4")
async def wiegen_cmd(inter: discord.Interaction, kg: app_commands.Range[float, 30, 400]):
    p, err = braucht_profil(inter.user.id)
    if err:
        return await inter.response.send_message(err, ephemeral=True)
    con = get_conn()
    con.execute("INSERT OR REPLACE INTO gewicht (user_id, datum, kg) VALUES (?,?,?)",
                (inter.user.id, heute(), kg))
    con.commit()
    con.close()
    diff = p["start_kg"] - kg
    trend = gewichts_trend(inter.user.id)
    trend_txt = (f" · Trend: {fmt(trend * 7, 2)} kg/Woche" if trend is not None else "")
    await inter.response.send_message(
        f"⚖️ **{fmt(kg, 1)} kg** gespeichert. Seit Start: "
        f"**{'−' if diff >= 0 else '+'}{fmt(abs(diff), 1)} kg**{trend_txt}\n"
        f"-# Tagesschwankungen sind normal — der Wochentrend zählt.", ephemeral=True)


# ────────── /wasser ──────────
@tree.command(name="wasser", description="Wasser tracken (Gläser à 250 ml)")
@app_commands.describe(glaeser="Anzahl Gläser (Standard 1, negativ zum Korrigieren)")
async def wasser_cmd(inter: discord.Interaction, glaeser: app_commands.Range[int, -20, 20] = 1):
    p, err = braucht_profil(inter.user.id)
    if err:
        return await inter.response.send_message(err, ephemeral=True)
    con = get_conn()
    con.execute("""INSERT INTO wasser (user_id, datum, glaeser) VALUES (?,?,MAX(0,?))
                   ON CONFLICT(user_id, datum) DO UPDATE SET glaeser=MAX(0, glaeser+?)""",
                (inter.user.id, heute(), glaeser, glaeser))
    con.commit()
    con.close()
    kg = aktuelles_gewicht(inter.user.id, p)
    c = berechne(p, kg)
    s = tages_summen(inter.user.id, heute())
    voll = min(s["glaeser"], c["wasser_glaeser"])
    anzeige = "🟦" * voll + "⬜" * max(0, c["wasser_glaeser"] - voll)
    await inter.response.send_message(
        f"💧 {anzeige}  {fmt(s['glaeser'] * GLAS_LITER, 2)} / "
        f"{fmt(c['wasser_glaeser'] * GLAS_LITER, 2)} l heute", ephemeral=True)


# ────────── /verlauf ──────────
@tree.command(name="verlauf", description="Gewichtsverlauf, Wochentrend und Ziel-Prognose (+ Chart)")
async def verlauf_cmd(inter: discord.Interaction):
    p, err = braucht_profil(inter.user.id)
    if err:
        return await inter.response.send_message(err, ephemeral=True)
    con = get_conn()
    rows = con.execute("SELECT datum, kg FROM gewicht WHERE user_id=? ORDER BY datum",
                       (inter.user.id,)).fetchall()
    con.close()
    if not rows:
        return await inter.response.send_message(
            "Noch keine Gewichtseinträge — starte mit `/wiegen`.", ephemeral=True)

    kg = rows[-1]["kg"]
    diff = p["start_kg"] - kg
    trend = gewichts_trend(inter.user.id)
    prog = prognose(inter.user.id, p, kg)

    e = discord.Embed(title="Dein Verlauf", color=GRUEN)
    e.add_field(name="Aktuell", value=f"{fmt(kg, 1)} kg")
    e.add_field(name="Seit Start", value=f"{'−' if diff >= 0 else '+'}{fmt(abs(diff), 1)} kg")
    e.add_field(name="Noch bis Ziel", value=f"{fmt(max(0, kg - p['ziel_kg']), 1)} kg")
    e.add_field(name="Trend/Woche",
                value=f"{fmt(trend * 7, 2)} kg" if trend is not None else "braucht ≥ 3 Einträge in 21 Tagen")
    if prog:
        datum, basis = prog
        e.add_field(name="Ziel erreicht ca.", value=f"{datum.strftime('%d.%m.%Y')} (nach {basis})")
    elif kg <= p["ziel_kg"]:
        e.add_field(name="🎉", value="Zielgewicht erreicht!")

    letzte = rows[-10:]
    zeilen = []
    for i, r in enumerate(letzte):
        d = date.fromisoformat(r["datum"]).strftime("%d.%m.")
        delta = ""
        if i > 0:
            dv = r["kg"] - letzte[i - 1]["kg"]
            delta = f"  ({'+' if dv > 0 else '−'}{fmt(abs(dv), 1)})"
        zeilen.append(f"`{d}  {fmt(r['kg'], 1):>6} kg`{delta}")
    e.add_field(name="Letzte Einträge", value="\n".join(zeilen), inline=False)

    datei = None
    if HAS_MPL and len(rows) >= 2:
        datei = discord.File(chart_png(rows, p["ziel_kg"]), filename="verlauf.png")
        e.set_image(url="attachment://verlauf.png")
    elif not HAS_MPL:
        e.set_footer(text="Tipp: matplotlib installieren → /verlauf zeigt ein Chart-Bild.")

    if datei:
        await inter.response.send_message(embed=e, file=datei, ephemeral=True)
    else:
        await inter.response.send_message(embed=e, ephemeral=True)


def chart_png(rows, ziel_kg) -> io.BytesIO:
    xs = [date.fromisoformat(r["datum"]) for r in rows]
    ys = [r["kg"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 4), dpi=140)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    ax.plot(xs, ys, color="#2a78d6", linewidth=2, solid_capstyle="round", zorder=3)
    ax.plot(xs[-1], ys[-1], "o", color="#2a78d6", markersize=7,
            markeredgecolor="#fcfcfb", markeredgewidth=2, zorder=4)
    ax.annotate(f"{ys[-1]:.1f} kg".replace(".", ","), (xs[-1], ys[-1]),
                textcoords="offset points", xytext=(-8, 10), ha="right",
                fontsize=10, fontweight="bold", color="#0b0b0b")
    ax.axhline(ziel_kg, color="#898781", linestyle=(0, (5, 4)), linewidth=1.5, zorder=2)
    ax.annotate(f"Ziel {ziel_kg:.1f} kg".replace(".", ","),
                (xs[-1], ziel_kg), textcoords="offset points", xytext=(0, 6),
                ha="right", fontsize=9, color="#898781")
    ax.grid(axis="y", color="#e1e0d9", linewidth=0.8)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors="#898781", labelsize=9)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=6))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m."))
    ax.set_title("Gewichtsverlauf (kg)", loc="left", fontsize=11,
                 fontweight="bold", color="#0b0b0b", pad=12)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


# ────────── /rueckgaengig ──────────
@tree.command(name="rueckgaengig", description="Letzten Eintrag von heute löschen")
@app_commands.describe(was="Was soll gelöscht werden?")
@app_commands.choices(was=[app_commands.Choice(name="Letzte Mahlzeit", value="mahlzeit"),
                           app_commands.Choice(name="Letztes Training", value="training")])
async def rueckgaengig_cmd(inter: discord.Interaction, was: app_commands.Choice[str]):
    con = get_conn()
    row = con.execute(f"SELECT id, name, kcal FROM {was.value} WHERE user_id=? AND datum=? "
                      "ORDER BY id DESC LIMIT 1", (inter.user.id, heute())).fetchone()
    if not row:
        con.close()
        return await inter.response.send_message("Heute gibt es dazu keinen Eintrag.", ephemeral=True)
    con.execute(f"DELETE FROM {was.value} WHERE id=?", (row["id"],))
    con.commit()
    con.close()
    await inter.response.send_message(
        f"🗑️ Gelöscht: **{row['name']}** ({fmt(row['kcal'])} kcal)", ephemeral=True)


# ────────── /erinnerung ──────────
@tree.command(name="erinnerung", description="Tägliche Erinnerung (wiegen + tracken) in diesem Kanal an/aus")
@app_commands.describe(modus="An oder aus", stunde="Uhrzeit (Stunde 0–23, deutsche Zeit, Standard 8)")
@app_commands.choices(modus=[app_commands.Choice(name="An", value="an"),
                             app_commands.Choice(name="Aus", value="aus")])
async def erinnerung_cmd(inter: discord.Interaction, modus: app_commands.Choice[str],
                         stunde: app_commands.Range[int, 0, 23] = 8):
    con = get_conn()
    if modus.value == "aus":
        con.execute("DELETE FROM erinnerung WHERE user_id=?", (inter.user.id,))
        con.commit()
        con.close()
        return await inter.response.send_message("🔕 Erinnerung ausgeschaltet.", ephemeral=True)
    con.execute("INSERT OR REPLACE INTO erinnerung (user_id, channel_id, stunde) VALUES (?,?,?)",
                (inter.user.id, inter.channel_id, stunde))
    con.commit()
    con.close()
    await inter.response.send_message(
        f"🔔 Ich erinnere dich täglich um ca. {stunde}:00 Uhr in diesem Kanal.", ephemeral=True)


def deutsche_stunde() -> int:
    """Aktuelle Stunde in Deutschland (MEZ/MESZ, einfache Sommerzeit-Näherung)."""
    jetzt = datetime.now(timezone.utc)
    offset = 2 if 3 < jetzt.month < 11 else 1   # Näherung: Apr–Okt Sommerzeit
    return (jetzt.hour + offset) % 24


@tasks.loop(minutes=30)
async def erinnerungs_loop():
    stunde = deutsche_stunde()
    datum = heute()
    con = get_conn()
    faellig = con.execute("SELECT user_id, channel_id FROM erinnerung WHERE stunde=?",
                          (stunde,)).fetchall()
    for r in faellig:
        schon_gewogen = con.execute("SELECT 1 FROM gewicht WHERE user_id=? AND datum=?",
                                    (r["user_id"], datum)).fetchone()
        if schon_gewogen:
            continue
        kanal = client.get_channel(r["channel_id"])
        if kanal:
            try:
                await kanal.send(f"🌱 <@{r['user_id']}> Guten Morgen! Kurz auf die Waage? "
                                 f"`/wiegen` — und denk an dein Tracking (`/heute`).")
            except discord.HTTPException:
                pass
    con.close()


# ────────── /quellen ──────────
@tree.command(name="quellen", description="Wissenschaftliche Grundlagen aller Berechnungen (Studien-Links)")
async def quellen_cmd(inter: discord.Interaction):
    e = discord.Embed(title="Wissenschaftliche Grundlagen", color=GRUEN,
                      description="Jede Berechnung dieses Bots basiert auf Studien und Leitlinien:")
    e.add_field(inline=False, name="Grundumsatz",
                value="Mifflin-St-Jeor-Formel ([Mifflin 1990](https://pubmed.ncbi.nlm.nih.gov/2305711/)) — "
                      "laut systematischem Review die genaueste Schätzformel "
                      "([Frankenfield 2005](https://pubmed.ncbi.nlm.nih.gov/15883556/)).")
    e.add_field(inline=False, name="Abnehmtempo",
                value="0,5–1 kg/Woche nach [CDC](https://www.cdc.gov/healthy-weight-growth/losing-weight/index.html)"
                      " & [NHS](https://www.nhs.uk/better-health/lose-weight/) — langsamer = besser gehalten.")
    e.add_field(inline=False, name="Defizit & Prognose",
                value="≈ 7 700 kcal/kg ist eine Näherung und überschätzt langfristig "
                      "([Hall 2011, The Lancet](https://pubmed.ncbi.nlm.nih.gov/21872751/)) — "
                      "die Prognose nutzt daher deinen echten Trend.")
    e.add_field(inline=False, name="Protein",
                value="Nutzen steigt bis ~1,6 g/kg/Tag ([Morton 2018](https://pubmed.ncbi.nlm.nih.gov/28698222/)); "
                      "im Defizit mit Krafttraining mehr ([Helms 2014](https://pubmed.ncbi.nlm.nih.gov/24092765/)). "
                      "Bezugsgröße: dein Zielgewicht.")
    e.add_field(inline=False, name="Wasser",
                value="[EFSA 2010](https://efsa.onlinelibrary.wiley.com/doi/10.2903/j.efsa.2010.1459): "
                      "2,5 l/Tag (M) bzw. 2,0 l/Tag (F) Gesamtwasser, ~80 % aus Getränken.")
    e.add_field(inline=False, name="Training",
                value="Netto-METs aus dem Compendium of Physical Activities "
                      "([Ainsworth 2011](https://pubmed.ncbi.nlm.nih.gov/21681120/)).")
    e.add_field(inline=False, name="Tägliches Wiegen",
                value="Mit mehr Gewichtsverlust verbunden, ohne negative psychische Effekte "
                      "([Zheng 2015](https://pubmed.ncbi.nlm.nih.gov/25521523/)).")
    e.set_footer(text="Richtwerte für gesunde Erwachsene — kein Ersatz für ärztliche Beratung.")
    await inter.response.send_message(embed=e, ephemeral=True)


if __name__ == "__main__":
    token = os.environ.get("WANDEL_TOKEN") or os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("❌ Bitte Umgebungsvariable WANDEL_TOKEN (oder DISCORD_TOKEN) setzen "
                         "— eigener Bot-Token aus dem Discord Developer Portal.")
    client.run(token)
