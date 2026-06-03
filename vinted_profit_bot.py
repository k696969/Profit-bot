"""
═══════════════════════════════════════════════════════════════
  RESELL-BOT v3  ·  Vinted ↔ eBay  ·  Discord
═══════════════════════════════════════════════════════════════

BEFEHLE
  /profit      Profit-Vergleich Vinted ↔ eBay für einen Artikel
  /marktpreis  eBay-Marktpreise zu einem Suchbegriff (verkaufte Angebote)
  /deal        Deal-Score: Link rein → Einkauf + eBay-Marktwert + Urteil "Kaufen?"
  /kauf        Artikel ins Inventar aufnehmen
  /lager       Inventar anzeigen (offen/alle) + Übersicht
  /gelistet    Artikel als „gelistet" markieren
  /verkauft    Artikel als verkauft markieren → Profit wird berechnet & gespeichert
  /loeschen    Artikel aus dem Inventar löschen
  /watch       Such-Alarm anlegen (pingt dich bei neuen Treffern unter Zielpreis)
  /watchlist   Aktive Such-Alarme anzeigen
  /unwatch     Such-Alarm entfernen

⚠️  Auto-Abruf (Preise/Suche) liest öffentliche Seiten und ist „best effort".
    Vinted/eBay blocken Automatik teils (gegen deren AGB). Der Watch-Alarm
    fragt bewusst SELTEN ab und benachrichtigt nur – er kauft NICHTS.
    Manuelle Eingaben funktionieren immer als Fallback.

Persistenz: Inventar/Watches liegen in SQLite (DB_PATH). Auf Railway ein
Volume anhängen und DB_PATH auf den Mount-Pfad setzen (siehe README_DEPLOY.md),
sonst gehen Daten bei jedem Neu-Deploy verloren.
═══════════════════════════════════════════════════════════════
"""

import os
import re
import sqlite3
import statistics
from datetime import datetime, timezone

import requests
import discord
from discord import app_commands
from discord.ext import tasks

# ╔══════════════════════════════════════════════╗
# ║  KONFIG                                        ║
# ╚══════════════════════════════════════════════╝
VINTED_DOMAIN          = "www.vinted.de"
EBAY_DOMAIN            = "www.ebay.de"
BUYER_PROTECTION_RATE  = 0.05
BUYER_PROTECTION_FIX   = 0.70
EBAY_FEE_RATE          = 0.12
VAT_RATE               = 0.19
GOOD_DEAL_MARGIN       = 30.0     # Marge % ab der ein Deal 🟢 ist
GOOD_DEAL_DISCOUNT     = 20.0     # % unter Marktwert ab dem ein Deal 🟢 ist
LADENHUETER_DAYS       = 30       # ab so vielen Tagen ohne Verkauf → Hinweis
POLL_INTERVAL_MIN      = int(os.environ.get("POLL_INTERVAL_MIN", "20"))  # Watch-Frequenz
DB_PATH                = os.environ.get("DB_PATH", "resell_data.db")
GUILD_ID               = os.environ.get("GUILD_ID")  # Server-ID → Befehle erscheinen SOFORT (statt global ~1h)

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "de-DE,de;q=0.9",
}


# ══════════════ DATENBANK ══════════════
def get_conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with get_conn() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, title TEXT, buy REAL, buy_platform TEXT, link TEXT,
            expected REAL, status TEXT, bought_at TEXT,
            sell REAL, sell_platform TEXT, sold_at TEXT, profit REAL)""")
        con.execute("""CREATE TABLE IF NOT EXISTS watches(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, channel_id TEXT, query TEXT, max_price REAL, created_at TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS seen(
            watch_id INTEGER, item_id TEXT, PRIMARY KEY(watch_id, item_id))""")


def add_item(user_id, title, buy, platform, link, expected):
    with get_conn() as con:
        cur = con.execute(
            "INSERT INTO items(user_id,title,buy,buy_platform,link,expected,status,bought_at) "
            "VALUES(?,?,?,?,?,?, 'gekauft', ?)",
            (str(user_id), title, buy, platform, link, expected, datetime.now(timezone.utc).isoformat()))
        return cur.lastrowid


def list_items(user_id, include_sold=False):
    q = "SELECT * FROM items WHERE user_id=?"
    if not include_sold:
        q += " AND status!='verkauft'"
    q += " ORDER BY id"
    with get_conn() as con:
        return [dict(r) for r in con.execute(q, (str(user_id),)).fetchall()]


def get_item(user_id, item_id):
    with get_conn() as con:
        r = con.execute("SELECT * FROM items WHERE id=? AND user_id=?",
                        (item_id, str(user_id))).fetchone()
        return dict(r) if r else None


def set_status(user_id, item_id, status):
    with get_conn() as con:
        cur = con.execute("UPDATE items SET status=? WHERE id=? AND user_id=?",
                          (status, item_id, str(user_id)))
        return cur.rowcount > 0


def mark_sold(user_id, item_id, sell, sell_platform, ship=0.0, packaging=0.0, tax_mode="kleinunternehmer"):
    it = get_item(user_id, item_id)
    if not it:
        return None
    r = resale(it["buy"], sell, sell_platform, it["buy_platform"], ship, packaging, tax_mode)
    with get_conn() as con:
        con.execute("UPDATE items SET status='verkauft', sell=?, sell_platform=?, sold_at=?, profit=? "
                    "WHERE id=? AND user_id=?",
                    (sell, sell_platform, datetime.now(timezone.utc).isoformat(),
                     r["profit"], item_id, str(user_id)))
    return r["profit"]


def delete_item(user_id, item_id):
    with get_conn() as con:
        cur = con.execute("DELETE FROM items WHERE id=? AND user_id=?", (item_id, str(user_id)))
        return cur.rowcount > 0


def inventory_summary(user_id):
    items = list_items(user_id, include_sold=True)
    open_items = [i for i in items if i["status"] != "verkauft"]
    sold = [i for i in items if i["status"] == "verkauft"]
    invested = sum(i["buy"] for i in open_items)
    realized = sum((i["profit"] or 0) for i in sold)
    return {"open": len(open_items), "sold": len(sold),
            "invested": invested, "realized": realized}


def days_held(iso):
    try:
        d = datetime.fromisoformat(iso)
        return (datetime.now(timezone.utc) - d).days
    except Exception:
        return 0


# Watches
def add_watch(user_id, channel_id, query, max_price):
    with get_conn() as con:
        cur = con.execute("INSERT INTO watches(user_id,channel_id,query,max_price,created_at) VALUES(?,?,?,?,?)",
                          (str(user_id), str(channel_id), query, max_price,
                           datetime.now(timezone.utc).isoformat()))
        return cur.lastrowid


def list_watches(user_id):
    with get_conn() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM watches WHERE user_id=? ORDER BY id", (str(user_id),)).fetchall()]


def all_watches():
    with get_conn() as con:
        return [dict(r) for r in con.execute("SELECT * FROM watches").fetchall()]


def remove_watch(user_id, watch_id):
    with get_conn() as con:
        cur = con.execute("DELETE FROM watches WHERE id=? AND user_id=?", (watch_id, str(user_id)))
        con.execute("DELETE FROM seen WHERE watch_id=?", (watch_id,))
        return cur.rowcount > 0


def is_seen(watch_id, item_id):
    with get_conn() as con:
        return con.execute("SELECT 1 FROM seen WHERE watch_id=? AND item_id=?",
                           (watch_id, str(item_id))).fetchone() is not None


def mark_seen(watch_id, item_id):
    with get_conn() as con:
        con.execute("INSERT OR IGNORE INTO seen(watch_id,item_id) VALUES(?,?)",
                    (watch_id, str(item_id)))


# ══════════════ PREIS-ABRUF (best effort) ══════════════
def detect_platform(link: str) -> str:
    l = (link or "").lower()
    if "vinted." in l:
        return "vinted"
    if "ebay." in l:
        return "ebay"
    return "unknown"


def fetch_vinted_item(link: str):
    m = re.search(r"/items/(\d+)", link)
    if not m:
        raise ValueError("kein gültiger Vinted-Artikellink")
    s = requests.Session(); s.headers.update({**BROWSER_HEADERS, "Accept": "application/json, */*"})
    s.get(f"https://{VINTED_DOMAIN}/", timeout=10)
    r = s.get(f"https://{VINTED_DOMAIN}/api/v2/items/{m.group(1)}", timeout=10)
    r.raise_for_status()
    item = r.json().get("item", {})
    p = item.get("price")
    price = float(p["amount"]) if isinstance(p, dict) else float(str(p).replace(",", "."))
    return (item.get("title") or "Vinted-Artikel"), price


def fetch_ebay_item(link: str):
    s = requests.Session(); s.headers.update({**BROWSER_HEADERS, "Accept": "text/html"})
    r = s.get(link, timeout=10); r.raise_for_status()
    html = r.text
    m = (re.search(r'"price"\s*:\s*"?([0-9]+[.,][0-9]{2})"?', html)
         or re.search(r'itemprop="price"[^>]*content="([0-9]+[.,][0-9]{2})"', html))
    if not m:
        raise ValueError("Preis nicht auslesbar")
    tm = re.search(r"<title>(.*?)</title>", html, re.S)
    title = re.sub(r"\s+", " ", tm.group(1)).strip()[:80] if tm else "eBay-Artikel"
    return title, float(m.group(1).replace(",", "."))


def fetch_item(link: str):
    plat = detect_platform(link)
    if plat == "vinted":
        t, p = fetch_vinted_item(link)
    elif plat == "ebay":
        t, p = fetch_ebay_item(link)
    else:
        raise ValueError("Link weder als Vinted noch eBay erkannt")
    return t, p, plat


def fetch_ebay_market(query: str, sold: bool = True, limit: int = 30):
    params = {"_nkw": query, "_sacat": "0"}
    if sold:
        params.update({"LH_Sold": "1", "LH_Complete": "1"})
    s = requests.Session(); s.headers.update({**BROWSER_HEADERS, "Accept": "text/html"})
    r = s.get(f"https://{EBAY_DOMAIN}/sch/i.html", params=params, timeout=12)
    r.raise_for_status()
    raw = re.findall(r's-item__price[^>]*>\s*(?:<span[^>]*>)?\s*EUR\s*([0-9.]+,[0-9]{2})', r.text)
    if not raw:
        raw = re.findall(r's-item__price[^>]*>\s*(?:<span[^>]*>)?\s*([0-9.]+,[0-9]{2})\s*€', r.text)
    prices = []
    for x in raw[:limit]:
        try:
            prices.append(float(x.replace(".", "").replace(",", ".")))
        except ValueError:
            pass
    if not prices:
        raise ValueError("keine Preise gefunden")
    return prices


def fetch_vinted_search(query, price_to=None, limit=20):
    """Neueste Vinted-Treffer zu einer Suche (für den Watch-Alarm, best effort)."""
    s = requests.Session(); s.headers.update({**BROWSER_HEADERS, "Accept": "application/json, */*"})
    s.get(f"https://{VINTED_DOMAIN}/", timeout=10)
    params = {"search_text": query, "order": "newest_first", "per_page": str(limit)}
    if price_to:
        params["price_to"] = str(price_to)
    r = s.get(f"https://{VINTED_DOMAIN}/api/v2/catalog/items", params=params, timeout=12)
    r.raise_for_status()
    out = []
    for it in r.json().get("items", []):
        p = it.get("price")
        price = float(p["amount"]) if isinstance(p, dict) else float(str(p).replace(",", "."))
        out.append({"id": str(it.get("id")), "title": it.get("title") or "Artikel",
                    "price": price,
                    "url": it.get("url") or f"https://{VINTED_DOMAIN}/items/{it.get('id')}"})
    return out


# ══════════════ RECHNUNG ══════════════
def acquisition_cost(buy, buy_platform, ship_buy):
    protection = (buy * BUYER_PROTECTION_RATE + BUYER_PROTECTION_FIX) if buy_platform == "vinted" else 0.0
    return buy + protection + ship_buy, protection


def resale(buy, sell, sell_platform, buy_platform, ship_buy=0.0, packaging=0.0, tax_mode="kleinunternehmer"):
    acq, protection = acquisition_cost(buy, buy_platform, ship_buy)
    fee = sell * (EBAY_FEE_RATE if sell_platform == "ebay" else 0.0)
    net_rev = sell - fee - packaging
    vat = (max(0.0, sell - buy) * (VAT_RATE / (1 + VAT_RATE))) if tax_mode == "differenzbesteuerung" else 0.0
    profit = net_rev - acq - vat
    margin = (profit / acq * 100.0) if acq else 0.0
    return {"acq": acq, "protection": protection, "fee": fee, "net_rev": net_rev,
            "vat": vat, "profit": profit, "margin": margin, "sell": sell}


def ebay_price_to_beat(target_profit, buy, buy_platform, ship_buy, packaging, tax_mode):
    acq, _ = acquisition_cost(buy, buy_platform, ship_buy)
    k = (VAT_RATE / (1 + VAT_RATE)) if tax_mode == "differenzbesteuerung" else 0.0
    denom = 1 - EBAY_FEE_RATE - k
    return (target_profit + packaging + acq - k * buy) / denom if denom > 0 else float("nan")


def verdict_icon(profit, margin):
    return "🟢" if margin >= GOOD_DEAL_MARGIN else ("🟡" if profit > 0 else "🔴")


# ╔══════════════════════════════════════════════╗
# ║  DISCORD                                       ║
# ╚══════════════════════════════════════════════╝
intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

STEUER_CHOICES = [
    app_commands.Choice(name="Kleinunternehmer (keine MwSt)", value="kleinunternehmer"),
    app_commands.Choice(name="Differenzbesteuerung §25a (19 % auf Marge)", value="differenzbesteuerung"),
]
PLATFORM_CHOICES = [
    app_commands.Choice(name="Vinted", value="vinted"),
    app_commands.Choice(name="eBay", value="ebay"),
]


@client.event
async def on_ready():
    init_db()
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        tree.copy_global_to(guild=guild)      # Befehle diesem Server zuweisen
        synced = await tree.sync(guild=guild)  # sofort sichtbar
    else:
        synced = await tree.sync()             # global (kann ~1h dauern)
    if not watch_loop.is_running():
        watch_loop.start()
    print(f"✅ Eingeloggt als {client.user} — {len(synced)} Befehle bereit. Watch-Intervall: {POLL_INTERVAL_MIN} Min.")


# ---------- /profit ----------
@tree.command(name="profit", description="Profit-Vergleich Vinted<->eBay für einen Artikel")
@app_commands.describe(
    verkaufspreis="Geplanter VK auf Vinted (€)",
    link="Vinted- ODER eBay-Link (Einkauf wird automatisch geladen)",
    ebay_verkaufspreis="Optional: abweichender VK auf eBay (sonst = Vinted-VK)",
    einkaufspreis="Optional: Einkaufspreis manuell",
    versand="Optional: Versand, den DU beim Kauf zahlst (€)",
    verpackung="Optional: Verpackung beim Weiterverkauf (€)",
    gekauft_auf="Bei manuellem Preis: wo gekauft? (Standard: Vinted)",
    steuer="Steuermodus (Standard: Kleinunternehmer)")
@app_commands.choices(gekauft_auf=PLATFORM_CHOICES, steuer=STEUER_CHOICES)
async def profit(interaction, verkaufspreis: float, link: str = None,
                 ebay_verkaufspreis: float = None, einkaufspreis: float = None,
                 versand: float = 0.0, verpackung: float = 0.0,
                 gekauft_auf: app_commands.Choice[str] = None,
                 steuer: app_commands.Choice[str] = None):
    await interaction.response.defer()
    tax_mode = steuer.value if steuer else "kleinunternehmer"
    title, buy = "Manueller Artikel", einkaufspreis
    buy_platform = gekauft_auf.value if gekauft_auf else "vinted"
    if buy is None:
        if not link:
            await interaction.followup.send("⚠️ Bitte `link` ODER `einkaufspreis` angeben."); return
        try:
            title, buy, buy_platform = fetch_item(link)
        except Exception as ex:
            await interaction.followup.send(
                f"⚠️ Auto-Abruf fehlgeschlagen ({ex}). Nutze `einkaufspreis` + `gekauft_auf` manuell."); return
    ebay_vk = ebay_verkaufspreis if ebay_verkaufspreis is not None else verkaufspreis
    v = resale(buy, verkaufspreis, "vinted", buy_platform, versand, verpackung, tax_mode)
    e = resale(buy, ebay_vk, "ebay", buy_platform, versand, verpackung, tax_mode)
    beat = ebay_price_to_beat(v["profit"], buy, buy_platform, versand, verpackung, tax_mode)
    color = 0x09B83E if max(v["margin"], e["margin"]) >= GOOD_DEAL_MARGIN else (
        0xE8A317 if max(v["profit"], e["profit"]) > 0 else 0xD93025)
    emb = discord.Embed(title=f"💰 Profit-Vergleich — {title}", color=color)
    emb.add_field(name="🛒 Gekauft auf", value=buy_platform.capitalize(), inline=True)
    emb.add_field(name="Einkaufspreis", value=f"{buy:.2f} €", inline=True)
    if v["protection"]:
        emb.add_field(name="Käuferschutz", value=f"{v['protection']:.2f} €", inline=True)
    emb.add_field(name="➡️ Einkauf gesamt", value=f"**{v['acq']:.2f} €**", inline=False)
    emb.add_field(name=f"{verdict_icon(v['profit'], v['margin'])} Verkauf auf VINTED",
                  value=f"VK {v['sell']:.2f} € · Gebühr 0 €" + (f" · MwSt −{v['vat']:.2f} €" if v['vat'] else "")
                        + f"\n→ **Profit {v['profit']:.2f} €** · Marge **{v['margin']:.0f} %**", inline=False)
    emb.add_field(name=f"{verdict_icon(e['profit'], e['margin'])} Verkauf auf EBAY",
                  value=f"VK {e['sell']:.2f} € · Gebühr −{e['fee']:.2f} €" + (f" · MwSt −{e['vat']:.2f} €" if e['vat'] else "")
                        + f"\n→ **Profit {e['profit']:.2f} €** · Marge **{e['margin']:.0f} %**", inline=False)
    if e["profit"] > v["profit"]:
        tipp = f"🏆 **eBay lohnt sich** – {e['profit']-v['profit']:.2f} € mehr Gewinn."
    elif v["profit"] > e["profit"]:
        tipp = (f"🏆 **Vinted lohnt sich** – {v['profit']-e['profit']:.2f} € mehr.\n"
                f"🎯 Auf eBay bräuchtest du mind. **{beat:.2f} €** VK, um Vinted zu schlagen.")
    else:
        tipp = "Gleichstand."
    emb.add_field(name="Empfehlung", value=tipp, inline=False)
    emb.set_footer(text="Profit vor Einkommensteuer")
    await interaction.followup.send(embed=emb)


# ---------- /marktpreis ----------
@tree.command(name="marktpreis", description="eBay-Marktpreise zu einem Suchbegriff")
@app_commands.describe(suchbegriff="z. B. 'Nike TN 42'", zustand="verkaufte oder aktuelle Angebote")
@app_commands.choices(zustand=[
    app_commands.Choice(name="Verkaufte Angebote (echter Marktwert)", value="sold"),
    app_commands.Choice(name="Aktuelle Angebote", value="active")])
async def marktpreis(interaction, suchbegriff: str, zustand: app_commands.Choice[str] = None):
    await interaction.response.defer()
    sold = (zustand.value if zustand else "sold") == "sold"
    try:
        prices = fetch_ebay_market(suchbegriff, sold=sold)
    except Exception as ex:
        await interaction.followup.send(f"⚠️ Keine eBay-Preise ({ex}). Tipp: manuell mit Filter „Verkaufte Artikel\"."); return
    emb = discord.Embed(title=f"📊 eBay-Marktpreis — {suchbegriff}", color=0x0064D2)
    emb.add_field(name="Basis", value=f"{len(prices)} {'verkaufte' if sold else 'aktuelle'} Angebote", inline=False)
    emb.add_field(name="Günstigste", value=f"{min(prices):.2f} €", inline=True)
    emb.add_field(name="Median", value=f"**{statistics.median(prices):.2f} €**", inline=True)
    emb.add_field(name="Teuerste", value=f"{max(prices):.2f} €", inline=True)
    emb.set_footer(text="Median = realistischer Richtwert")
    await interaction.followup.send(embed=emb)


# ---------- /deal ----------
@tree.command(name="deal", description="Deal-Score: Einkauf + eBay-Marktwert + Urteil 'Kaufen?'")
@app_commands.describe(
    link="Vinted- ODER eBay-Link des Artikels den du kaufen willst",
    suchbegriff="Optional: Suchbegriff für eBay-Marktwert (sonst aus Titel)",
    einkaufspreis="Optional: Einkaufspreis manuell",
    gekauft_auf="Bei manuellem Preis: wo kaufst du? (Standard: Vinted)",
    versand="Optional: Versand beim Kauf (€)",
    verpackung="Optional: Verpackung beim Weiterverkauf (€)",
    steuer="Steuermodus (Standard: Kleinunternehmer)")
@app_commands.choices(gekauft_auf=PLATFORM_CHOICES, steuer=STEUER_CHOICES)
async def deal(interaction, link: str = None, suchbegriff: str = None,
               einkaufspreis: float = None, gekauft_auf: app_commands.Choice[str] = None,
               versand: float = 0.0, verpackung: float = 0.0,
               steuer: app_commands.Choice[str] = None):
    await interaction.response.defer()
    tax_mode = steuer.value if steuer else "kleinunternehmer"
    title, buy = "Manueller Artikel", einkaufspreis
    buy_platform = gekauft_auf.value if gekauft_auf else "vinted"
    if buy is None:
        if not link:
            await interaction.followup.send("⚠️ Bitte `link` ODER `einkaufspreis` angeben."); return
        try:
            title, buy, buy_platform = fetch_item(link)
        except Exception as ex:
            await interaction.followup.send(f"⚠️ Auto-Abruf fehlgeschlagen ({ex}). Nutze `einkaufspreis` manuell."); return
    query = suchbegriff or title
    median, prices = None, []
    try:
        prices = fetch_ebay_market(query, sold=True)
        median = statistics.median(prices)
    except Exception:
        pass
    if median is None:
        await interaction.followup.send(
            f"⚠️ Kein eBay-Marktwert für '{query}' gefunden. Gib `suchbegriff` genauer an "
            f"oder nutze `/profit` mit eigenem Verkaufspreis."); return
    acq, _ = acquisition_cost(buy, buy_platform, versand)
    v = resale(buy, median, "vinted", buy_platform, versand, verpackung, tax_mode)
    e = resale(buy, median, "ebay", buy_platform, versand, verpackung, tax_mode)
    best = max(v, e, key=lambda r: r["profit"])
    best_name = "Vinted" if best is v else "eBay"
    discount = (median - buy) / median * 100 if median else 0
    if best["margin"] >= GOOD_DEAL_MARGIN and discount >= GOOD_DEAL_DISCOUNT:
        urteil, color = "🟢 KAUFEN", 0x09B83E
    elif best["profit"] > 0:
        urteil, color = "🟡 Grenzwertig", 0xE8A317
    else:
        urteil, color = "🔴 Finger weg", 0xD93025
    emb = discord.Embed(title=f"🎯 Deal-Score — {title}", color=color)
    emb.add_field(name="Einkauf gesamt", value=f"{acq:.2f} €", inline=True)
    emb.add_field(name="eBay-Marktwert (Median)", value=f"{median:.2f} €", inline=True)
    emb.add_field(name="Unter Marktwert", value=f"**{discount:.0f} %**", inline=True)
    emb.add_field(name=f"Bester Weiterverkauf: {best_name}",
                  value=f"VK {median:.2f} € → **Profit {best['profit']:.2f} €** · Marge **{best['margin']:.0f} %**",
                  inline=False)
    emb.add_field(name="Urteil", value=f"## {urteil}", inline=False)
    emb.set_footer(text=f"Marktwert aus {len(prices)} verkauften eBay-Angeboten · vor Einkommensteuer")
    await interaction.followup.send(embed=emb)


# ---------- Inventar ----------
@tree.command(name="kauf", description="Artikel ins Inventar aufnehmen")
@app_commands.describe(titel="Was hast du gekauft?", einkaufspreis="Kaufpreis (€)",
                       gekauft_auf="Wo gekauft? (Standard: Vinted)", link="Optional: Link",
                       erwarteter_vk="Optional: erwarteter Verkaufspreis (€)")
@app_commands.choices(gekauft_auf=PLATFORM_CHOICES)
async def kauf(interaction, titel: str, einkaufspreis: float,
               gekauft_auf: app_commands.Choice[str] = None, link: str = None,
               erwarteter_vk: float = None):
    await interaction.response.defer()
    plat = gekauft_auf.value if gekauft_auf else "vinted"
    iid = add_item(interaction.user.id, titel, einkaufspreis, plat, link, erwarteter_vk)
    await interaction.followup.send(
        f"✅ **#{iid}** hinzugefügt: '{titel}' für {einkaufspreis:.2f} € ({plat.capitalize()})."
        + (f" Erwarteter VK: {erwarteter_vk:.2f} €." if erwarteter_vk else ""))


@tree.command(name="lager", description="Dein Inventar anzeigen")
@app_commands.describe(alle="Auch verkaufte Artikel zeigen?")
async def lager(interaction, alle: bool = False):
    await interaction.response.defer()
    items = list_items(interaction.user.id, include_sold=alle)
    s = inventory_summary(interaction.user.id)
    if not items:
        await interaction.followup.send("📦 Dein Inventar ist leer. Mit `/kauf` etwas hinzufügen."); return
    lines = []
    for i in items:
        if i["status"] == "verkauft":
            lines.append(f"~~#{i['id']} {i['title']}~~ → verkauft für {i['sell']:.2f} € "
                         f"(Profit {i['profit']:.2f} €)")
        else:
            d = days_held(i["bought_at"])
            flag = " 🐌 Ladenhüter" if (d >= LADENHUETER_DAYS) else ""
            lines.append(f"**#{i['id']}** {i['title']} · EK {i['buy']:.2f} € · {i['status']} · {d} Tage{flag}")
    body = "\n".join(lines)[:3500]
    emb = discord.Embed(title="📦 Inventar", description=body, color=0x5865F2)
    emb.add_field(name="Offen", value=f"{s['open']} Artikel", inline=True)
    emb.add_field(name="Gebundenes Kapital", value=f"{s['invested']:.2f} €", inline=True)
    emb.add_field(name="Realisierter Profit", value=f"{s['realized']:.2f} €", inline=True)
    await interaction.followup.send(embed=emb)


@tree.command(name="gelistet", description="Artikel als 'gelistet' markieren")
@app_commands.describe(artikel_id="Die #ID aus /lager")
async def gelistet(interaction, artikel_id: int):
    await interaction.response.defer()
    ok = set_status(interaction.user.id, artikel_id, "gelistet")
    await interaction.followup.send(f"✅ #{artikel_id} ist jetzt **gelistet**." if ok
                                    else f"⚠️ #{artikel_id} nicht gefunden.")


@tree.command(name="verkauft", description="Artikel als verkauft markieren (Profit wird berechnet)")
@app_commands.describe(artikel_id="Die #ID aus /lager", verkaufspreis="Verkaufspreis (€)",
                       verkauft_auf="Wo verkauft? (Standard: Vinted)",
                       versand="Optional: Versandkosten, die DU trägst (€)",
                       verpackung="Optional: Verpackung (€)", steuer="Steuermodus")
@app_commands.choices(verkauft_auf=PLATFORM_CHOICES, steuer=STEUER_CHOICES)
async def verkauft(interaction, artikel_id: int, verkaufspreis: float,
                   verkauft_auf: app_commands.Choice[str] = None,
                   versand: float = 0.0, verpackung: float = 0.0,
                   steuer: app_commands.Choice[str] = None):
    await interaction.response.defer()
    plat = verkauft_auf.value if verkauft_auf else "vinted"
    tax_mode = steuer.value if steuer else "kleinunternehmer"
    profit = mark_sold(interaction.user.id, artikel_id, verkaufspreis, plat, versand, verpackung, tax_mode)
    if profit is None:
        await interaction.followup.send(f"⚠️ #{artikel_id} nicht gefunden."); return
    icon = "🟢" if profit > 0 else "🔴"
    await interaction.followup.send(
        f"{icon} #{artikel_id} verkauft für {verkaufspreis:.2f} € ({plat.capitalize()}) → "
        f"**Profit {profit:.2f} €**.")


@tree.command(name="loeschen", description="Artikel aus dem Inventar löschen")
@app_commands.describe(artikel_id="Die #ID aus /lager")
async def loeschen(interaction, artikel_id: int):
    await interaction.response.defer()
    ok = delete_item(interaction.user.id, artikel_id)
    await interaction.followup.send(f"🗑️ #{artikel_id} gelöscht." if ok else f"⚠️ #{artikel_id} nicht gefunden.")


# ---------- Watch-Alarm ----------
@tree.command(name="watch", description="Such-Alarm: pingt dich bei neuen Treffern unter Zielpreis")
@app_commands.describe(suchbegriff="Wonach suchen (Vinted)", max_preis="Nur Treffer bis zu diesem Preis (€)")
async def watch(interaction, suchbegriff: str, max_preis: float):
    await interaction.response.defer()
    wid = add_watch(interaction.user.id, interaction.channel_id, suchbegriff, max_preis)
    primed = 0
    try:
        for it in fetch_vinted_search(suchbegriff, price_to=max_preis):
            mark_seen(wid, it["id"]); primed += 1
    except Exception:
        pass
    await interaction.followup.send(
        f"🔔 Alarm **#{wid}** aktiv: '{suchbegriff}' ≤ {max_preis:.2f} €.\n"
        f"Ich prüfe ca. alle {POLL_INTERVAL_MIN} Min und melde NEUE Treffer hier im Channel.\n"
        f"({primed} aktuelle Treffer als 'gesehen' markiert.)")


@tree.command(name="watchlist", description="Deine aktiven Such-Alarme")
async def watchlist(interaction):
    await interaction.response.defer()
    ws = list_watches(interaction.user.id)
    if not ws:
        await interaction.followup.send("Keine aktiven Alarme. Mit `/watch` einen anlegen."); return
    body = "\n".join(f"**#{w['id']}** {w['query']} ≤ {w['max_price']:.2f} €" for w in ws)
    await interaction.followup.send(embed=discord.Embed(title="🔔 Such-Alarme", description=body, color=0xFEE75C))


@tree.command(name="unwatch", description="Such-Alarm entfernen")
@app_commands.describe(alarm_id="Die #ID aus /watchlist")
async def unwatch(interaction, alarm_id: int):
    await interaction.response.defer()
    ok = remove_watch(interaction.user.id, alarm_id)
    await interaction.followup.send(f"🔕 Alarm #{alarm_id} entfernt." if ok else f"⚠️ #{alarm_id} nicht gefunden.")


@tasks.loop(minutes=POLL_INTERVAL_MIN)
async def watch_loop():
    """Prüft selten & respektvoll alle gespeicherten Suchen und meldet neue Treffer."""
    for w in all_watches():
        try:
            results = fetch_vinted_search(w["query"], price_to=w["max_price"])
        except Exception:
            continue  # Block/Fehler überspringen, nächster Durchlauf versucht es erneut
        chan = client.get_channel(int(w["channel_id"]))
        for it in results:
            if it["price"] > w["max_price"] or is_seen(w["id"], it["id"]):
                continue
            mark_seen(w["id"], it["id"])
            if chan:
                try:
                    await chan.send(
                        f"🔔 <@{w['user_id']}> neuer Treffer für **{w['query']}** ≤ {w['max_price']:.2f} €:\n"
                        f"**{it['title']}** – {it['price']:.2f} €\n{it['url']}")
                except Exception:
                    pass


@watch_loop.before_loop
async def _before_watch():
    await client.wait_until_ready()


if __name__ == "__main__":
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("❌ Bitte Umgebungsvariable DISCORD_TOKEN setzen (siehe README_DEPLOY.md).")
    client.run(token)
