"""
Morgenbrief - dit personlige overvågningsværktøj for aktiemarkedet.

Kun til eget brug. Programmet giver IKKE investeringsrådgivning og kan ikke
forudsige, hvad der giver penge. Det fortæller, hvad der sker, og hvad der
kan være værd at undersøge nærmere.

Sådan bruges det:
    python morgenbrief.py              -> laver dagens morgenbrief
    python morgenbrief.py evaluer      -> viser hvordan tidligere signaler er gået
"""

import csv
import datetime as dt
import sys
from pathlib import Path

import yfinance as yf

# ----------------------------------------------------------------------------
# INDSTILLINGER - her kan du ændre ting uden at kunne programmere
# ----------------------------------------------------------------------------

# Din liste over ting, der følges. Format:  "TICKER": "Navn (region/type)"
# En ticker er aktiens "kaldenavn" på børsen (kan slås op på finance.yahoo.com).
WATCHLIST = {
    # Brede indeks-ETF'er (sammenligningsgrundlag - se forklaring nederst)
    "VT": "Vanguard Total World (hele verden, ETF)",
    "SPY": "S&P 500 (USA, ETF)",
    "EXSA.DE": "STOXX Europe 600 (Europa, ETF)",
    "EEM": "Emerging Markets (vækstlande, ETF)",
    # USA
    "AAPL": "Apple (USA, teknologi)",
    "MSFT": "Microsoft (USA, teknologi)",
    "NVDA": "Nvidia (USA, chips)",
    "GOOGL": "Alphabet/Google (USA, teknologi)",
    "AMZN": "Amazon (USA, handel/cloud)",
    "JNJ": "Johnson & Johnson (USA, sundhed)",
    "XOM": "Exxon Mobil (USA, energi)",
    # Danmark
    "NOVO-B.CO": "Novo Nordisk (Danmark, sundhed)",
    "MAERSK-B.CO": "A.P. Møller - Mærsk (Danmark, shipping)",
    "VWS.CO": "Vestas (Danmark, vindenergi)",
    "DSV.CO": "DSV (Danmark, transport)",
    # Europa
    "ASML.AS": "ASML (Holland, chipmaskiner)",
    "SAP.DE": "SAP (Tyskland, software)",
    "NESN.SW": "Nestlé (Schweiz, fødevarer)",
    # Asien
    "TSM": "TSMC (Taiwan, chips)",
    "7203.T": "Toyota (Japan, biler)",
    "9988.HK": "Alibaba (Kina, handel)",
}

# Det ETF, alt sammenlignes med ("klarede jeg mig bedre end verdensmarkedet?")
BENCHMARK = "VT"

ALARM_DAG_PROCENT = 4.0      # alarm, hvis noget bevæger sig mere end dette på en dag
NY_TOP_BUND_PROCENT = 3.0    # "tæt på 52-ugers top/bund" betyder inden for så mange procent
ANTAL_NYHEDER = 3            # antal nyheder pr. alarm

MAPPE = Path(__file__).parent
BRIEF_MAPPE = MAPPE / "briefs"
SIGNAL_LOG = MAPPE / "signaler.csv"

# ----------------------------------------------------------------------------
# DATA
# ----------------------------------------------------------------------------


def hent_kurser(tickers):
    """Henter 1 års kursdata for alle tickers. Returnerer {ticker: liste af lukkekurser}."""
    data = yf.download(
        list(tickers),
        period="1y",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    resultat = {}
    for t in tickers:
        try:
            serie = data[t]["Close"].dropna()
            if len(serie) >= 30:
                resultat[t] = serie
        except Exception:
            pass  # hvis én ticker fejler, fortsætter vi med de andre
    return resultat


def pct(ny, gammel):
    return (ny / gammel - 1) * 100


def nøgletal(serie):
    """Regner de enkle tal ud, brugt i brieffen."""
    sidste = float(serie.iloc[-1])
    forrige = float(serie.iloc[-2])
    md_siden = float(serie.iloc[-22]) if len(serie) > 22 else float(serie.iloc[0])
    top = float(serie.max())
    bund = float(serie.min())
    daglige = serie.pct_change().dropna().iloc[-30:]
    svingning = float(daglige.std() * (252 ** 0.5) * 100)  # årlig volatilitet i %
    return {
        "kurs": sidste,
        "dag": pct(sidste, forrige),
        "maaned": pct(sidste, md_siden),
        "aar": pct(sidste, float(serie.iloc[0])),
        "fra_top": pct(sidste, top),
        "over_bund": pct(sidste, bund),
        "svingning": svingning,
        "dato": serie.index[-1].date().isoformat(),
    }


def hent_nyheder(ticker):
    """Henter de nyeste overskrifter. Fejler stille, hvis kilden ikke svarer."""
    nyheder = []
    try:
        for n in yf.Ticker(ticker).news[:ANTAL_NYHEDER]:
            indhold = n.get("content", n)
            titel = indhold.get("title")
            link = (
                (indhold.get("canonicalUrl") or {}).get("url")
                or (indhold.get("clickThroughUrl") or {}).get("url")
                or indhold.get("link")
            )
            if titel:
                nyheder.append((titel, link or ""))
    except Exception:
        pass
    return nyheder


# ----------------------------------------------------------------------------
# SIGNALER (observationer - ikke råd)
# ----------------------------------------------------------------------------


def find_signaler(tal):
    signaler = []
    if abs(tal["dag"]) >= ALARM_DAG_PROCENT:
        retning = "steg" if tal["dag"] > 0 else "faldt"
        signaler.append(("STOR_BEVÆGELSE", f"{retning} {abs(tal['dag']):.1f}% på en dag"))
    if tal["fra_top"] >= -NY_TOP_BUND_PROCENT:
        signaler.append(("NÆR_52U_TOP", "ligger tæt på sin højeste kurs det seneste år"))
    if tal["over_bund"] <= NY_TOP_BUND_PROCENT:
        signaler.append(("NÆR_52U_BUND", "ligger tæt på sin laveste kurs det seneste år"))
    if tal["maaned"] >= 10:
        signaler.append(("MOMENTUM_OP", f"er steget {tal['maaned']:.0f}% den seneste måned"))
    if tal["maaned"] <= -10:
        signaler.append(("MOMENTUM_NED", f"er faldet {abs(tal['maaned']):.0f}% den seneste måned"))
    return signaler


FORKLARING = {
    "STOR_BEVÆGELSE": "Store dagsbevægelser skyldes ofte nyheder (fx regnskab). Tjek nyhederne, "
                      "før du tillægger det betydning. Ét stort hop er ikke en trend.",
    "NÆR_52U_TOP": "Tæt på årets top kan betyde stærk udvikling - men også, at aktien allerede er "
                   "dyr. 'Arg for' og 'arg imod' findes begge dele.",
    "NÆR_52U_BUND": "Tæt på årets bund kan være en mulighed - eller et tegn på, at noget er galt "
                    "i selskabet. Find ud af HVORFOR den er faldet, før du overvejer noget.",
    "MOMENTUM_OP": "Momentum betyder, at noget, der har været i gang, ofte fortsætter lidt - "
                   "men det kan vende brat.",
    "MOMENTUM_NED": "Et stærkt fald over en måned: undersøg om årsagen er midlertidig eller varig.",
}

BEGREBER = """
Hvad betyder ordene?
- Kurs: Hvad én aktie koster lige nu.
- ETF: En pakke af mange aktier i ét køb. Brede ETF'er spreder din risiko.
- Svingning (volatilitet): Hvor meget kursen hopper op og ned. Højt tal = mere risiko.
- 52-ugers top/bund: Den højeste/laveste kurs det seneste år.
- Momentum: At en kurs har bevæget sig i en retning et stykke tid.
- Benchmark: Noget du sammenligner med. Her er det hele verdensmarkedet (VT).
  Kan et værktøj ikke slå et bredt indeks over tid, er indekset det bedste valg.

Vigtigt: Dette er information, ikke rådgivning. Ingen kan forudsige kurser.
Invester kun penge, du har råd til at tabe, og undersøg selv, før du handler.
"""

# ----------------------------------------------------------------------------
# BRIEFEN
# ----------------------------------------------------------------------------


def lav_brief():
    print("Henter kursdata... (tager ca. 10-30 sekunder)")
    kurser = hent_kurser(WATCHLIST.keys())
    if not kurser:
        print("Kunne ikke hente data. Tjek din internetforbindelse og prøv igen.")
        return

    tal = {t: nøgletal(s) for t, s in kurser.items()}
    nu = dt.datetime.now().strftime("%d-%m-%Y %H:%M")
    linjer = [f"MORGENBRIEF - {nu}", "=" * 50, ""]

    # 1. Markedet overordnet
    linjer.append("1) MARKEDET I HOVEDTRÆK")
    for t in ("VT", "SPY", "EXSA.DE", "EEM"):
        if t in tal:
            linjer.append(f"   {WATCHLIST[t]}: {tal[t]['dag']:+.1f}% i dag, {tal[t]['maaned']:+.1f}% seneste måned")
    linjer.append("")

    # 2. Største bevægelser
    sorteret = sorted(tal.items(), key=lambda x: x[1]["dag"])
    linjer.append("2) STØRSTE BEVÆGELSER SIDEN SIDST")
    for t, v in list(reversed(sorteret))[:3]:
        linjer.append(f"   OP   {WATCHLIST[t]}: {v['dag']:+.1f}%")
    for t, v in sorteret[:3]:
        linjer.append(f"   NED  {WATCHLIST[t]}: {v['dag']:+.1f}%")
    linjer.append("   (Bemærk: børser har forskellige åbningstider, så 'siden sidst' kan være forskellig.)")
    linjer.append("")

    # 3. Værd at undersøge
    linjer.append("3) VÆRD AT UNDERSØGE NÆRMERE")
    nye_signaler = []
    fundet = False
    for t, v in tal.items():
        for kode, tekst in find_signaler(v):
            fundet = True
            linjer.append(f"\n   * {WATCHLIST[t]} {tekst}.")
            linjer.append(f"     Kurs: {v['kurs']:.2f} | Svingning: {v['svingning']:.0f}% om året")
            linjer.append(f"     Hvad kan det betyde? {FORKLARING[kode]}")
            if kode == "STOR_BEVÆGELSE":
                for titel, link in hent_nyheder(t):
                    linjer.append(f"     Nyhed: {titel}")
                    if link:
                        linjer.append(f"            {link}")
            nye_signaler.append((v["dato"], t, kode, v["kurs"]))
    if not fundet:
        linjer.append("   Intet usædvanligt i dag. Det er helt normalt - de fleste dage er rolige.")
    linjer.append("")

    # 4. Risiko-oversigt
    linjer.append("4) RISIKO (jo højere svingning, jo mere risiko)")
    for t, v in sorted(tal.items(), key=lambda x: x[1]["svingning"], reverse=True)[:5]:
        linjer.append(f"   {WATCHLIST[t]}: {v['svingning']:.0f}%")
    linjer.append(BEGREBER)

    tekst = "\n".join(linjer)
    print("\n" + tekst)

    BRIEF_MAPPE.mkdir(exist_ok=True)
    fil = BRIEF_MAPPE / f"brief_{dt.date.today().isoformat()}.txt"
    fil.write_text(tekst, encoding="utf-8")
    gem_signaler(nye_signaler)
    print(f"\nGemt i: {fil}")


def gem_signaler(nye):
    """Gemmer hvert signal i en logfil, så vi senere kan måle, om de virkede."""
    if not nye:
        return
    findes = SIGNAL_LOG.exists()
    eksisterende = set()
    if findes:
        with open(SIGNAL_LOG, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                eksisterende.add((r["dato"], r["ticker"], r["signal"]))
    with open(SIGNAL_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not findes:
            w.writerow(["dato", "ticker", "signal", "kurs"])
        for dato, t, kode, kurs in nye:
            if (dato, t, kode) not in eksisterende:
                w.writerow([dato, t, kode, f"{kurs:.4f}"])


# ----------------------------------------------------------------------------
# EVALUERING: virkede signalerne?
# ----------------------------------------------------------------------------


def evaluer():
    if not SIGNAL_LOG.exists():
        print("Ingen signaler endnu. Kør først morgenbrief et par uger.")
        return
    with open(SIGNAL_LOG, newline="", encoding="utf-8") as f:
        rækker = list(csv.DictReader(f))
    tickers = {r["ticker"] for r in rækker} | {BENCHMARK}
    kurser = hent_kurser(tickers)
    if BENCHMARK not in kurser:
        print("Kunne ikke hente benchmark-data.")
        return

    def kurs_ved(serie, dato):
        s = serie[serie.index >= dato]
        return float(s.iloc[0]) if len(s) else None

    print(f"{'Dato':<12}{'Aktie':<14}{'Signal':<16}{'Siden':>8}{'Marked':>9}{'Forskel':>9}")
    forskelle = []
    for r in rækker:
        t = r["ticker"]
        if t not in kurser:
            continue
        nu = float(kurser[t].iloc[-1])
        ny = pct(nu, float(r["kurs"]))
        b0 = kurs_ved(kurser[BENCHMARK], r["dato"])
        if b0 is None:
            continue
        bm = pct(float(kurser[BENCHMARK].iloc[-1]), b0)
        forskelle.append(ny - bm)
        print(f"{r['dato']:<12}{t:<14}{r['signal']:<16}{ny:>+7.1f}%{bm:>+8.1f}%{ny - bm:>+8.1f}%")
    if forskelle:
        snit = sum(forskelle) / len(forskelle)
        bedre = sum(1 for x in forskelle if x > 0)
        print(f"\n{bedre} af {len(forskelle)} signaler slog markedet. Gennemsnitlig forskel: {snit:+.1f} procentpoint.")
        print("Vent med at drage konklusioner, til der er mange signaler og flere måneder.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "evaluer":
        evaluer()
    else:
        lav_brief()
