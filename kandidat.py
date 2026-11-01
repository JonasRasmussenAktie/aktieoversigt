"""
Kandidat-motor: rangerer aktierne på din liste efter en enkel, gennemskuelig model
og holder regnskab med, om de udvalgte aktier faktisk klarer sig bedre end
verdensmarkedet (VT).

Kun til eget brug. Information og eksperiment - IKKE investeringsrådgivning.
Modellen ser kun på kursudvikling. Den kender ikke regnskaber eller nyheder.
"""

import csv
import datetime as dt

import morgenbrief as mb

LOG = mb.MAPPE / "kandidater.csv"
ANTAL_LOGGET = 3        # hvor mange kandidater der logges hver uge
INVESTERET = 1000       # fiktive kroner pr. kandidat i regnestykket


def er_kandidat(t):
    """ETF'er (dem med 'ETF' i navnet) er sammenligningsgrundlag, ikke kandidater."""
    return "ETF" not in mb.WATCHLIST[t]


def _rangprocent(værdi, alle):
    """0.0 = dårligst på listen, 1.0 = bedst."""
    if len(alle) < 2:
        return 0.5
    return sum(1 for x in alle if x < værdi) / (len(alle) - 1)


def beregn(kurser, tal):
    """Giver en liste af kandidater, bedste først. Score 0-100."""
    rå = {}
    for t, s in kurser.items():
        if t not in mb.WATCHLIST or not er_kandidat(t) or len(s) < 200:
            continue
        sidste = float(s.iloc[-1])
        rå[t] = {
            "sidste": sidste,
            "r3": mb.pct(sidste, float(s.iloc[-64])),    # ca. 3 måneder
            "r6": mb.pct(sidste, float(s.iloc[-127])),   # ca. 6 måneder
            "sma50": float(s.iloc[-50:].mean()),
            "sma200": float(s.iloc[-200:].mean()),
            "vol": max(tal[t]["svingning"], 5.0),
        }
    if len(rå) < 3:
        return []

    mom_alle = [(x["r3"] + x["r6"]) / 2 for x in rå.values()]
    ra_alle = [x["r6"] / x["vol"] for x in rå.values()]

    resultat = []
    for t, x in rå.items():
        v = tal[t]
        mom = (x["r3"] + x["r6"]) / 2
        p_mom = 40 * _rangprocent(mom, mom_alle)                     # styrke i udviklingen
        p_ra = 20 * _rangprocent(x["r6"] / x["vol"], ra_alle)        # udvikling i forhold til udsving
        over50 = x["sidste"] > x["sma50"]
        trend = x["sma50"] > x["sma200"]
        p_trend = 15 * over50 + 15 * trend                           # stigende trend
        udvidet = mb.pct(x["sidste"], x["sma50"])
        stabil = v["fra_top"] > -15 and udvidet < 20
        p_stabil = 10 if stabil else 0                               # ikke faldet meget, ikke overophedet
        score = round(p_mom + p_ra + p_trend + p_stabil)

        grunde = []
        if p_mom >= 26:
            grunde.append(
                f"Stærk udvikling: {x['r3']:+.0f}% på 3 måneder og {x['r6']:+.0f}% på 6 måneder, "
                "blandt de stærkeste på din liste."
            )
        if over50 and trend:
            grunde.append("Stigende trend: kursen ligger over både sit 50-dages og 200-dages gennemsnit.")
        if p_ra >= 14:
            grunde.append("Udviklingen er kommet med forholdsvis rolige udsving sammenlignet med de andre.")
        if stabil:
            grunde.append("Har ikke tabt meget fra årets top og er ikke løbet løbsk på det seneste.")
        if not grunde:
            grunde.append("Højeste samlede score på din liste, men uden ét tydeligt styrkepunkt.")

        imod = []
        if x["vol"] >= 40:
            imod.append(f"Stor svingning ({x['vol']:.0f}% om året): kursen kan falde hurtigt.")
        if v["fra_top"] >= -3:
            imod.append("Ligger tæt på årets top, så den kan allerede være dyr.")
        if udvidet >= 20:
            imod.append(f"Kursen er {udvidet:.0f}% over sit 50-dages gennemsnit. Det kan være overophedet.")
        if v["dag"] <= -mb.ALARM_DAG_PROCENT:
            imod.append(f"Faldt {abs(v['dag']):.1f}% i dag. Find ud af hvorfor, før du gør noget.")
        imod.append("Modellen ser kun på kursudvikling, ikke på regnskaber, nyheder eller selskabets værdi.")

        resultat.append({
            "ticker": t, "navn": mb.WATCHLIST[t], "score": score, "r6": x["r6"],
            "grunde": grunde, "imod": imod, "tal": v,
        })

    resultat.sort(key=lambda k: (k["score"], k["r6"]), reverse=True)
    return resultat


# ----------------------------------------------------------------------------
# Log og resultater
# ----------------------------------------------------------------------------


def uge_nøgle(dato):
    år, uge, _ = dato.isocalendar()
    return f"{år}-U{uge:02d}"


def log_ugens(kandidater, kurser):
    """Gemmer ugens top-kandidater - højst én gang pr. uge. Returnerer True, hvis der blev logget."""
    if not kandidater or mb.BENCHMARK not in kurser:
        return False
    idag = dt.date.today()
    uge = uge_nøgle(idag)
    findes = LOG.exists()
    if findes:
        with open(LOG, newline="", encoding="utf-8") as f:
            if any(r["uge"] == uge for r in csv.DictReader(f)):
                return False
    bm = float(kurser[mb.BENCHMARK].iloc[-1])
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not findes:
            w.writerow(["uge", "dato", "rang", "ticker", "score", "kurs", "bm_kurs"])
        for rang, k in enumerate(kandidater[:ANTAL_LOGGET], 1):
            w.writerow([uge, idag.isoformat(), rang, k["ticker"], k["score"],
                        f"{k['tal']['kurs']:.4f}", f"{bm:.4f}"])
    return True


def resultater(kurser):
    """Hvordan er de loggede kandidater gået siden, sammenlignet med verdensmarkedet?"""
    if not LOG.exists() or mb.BENCHMARK not in kurser:
        return []
    bm_nu = float(kurser[mb.BENCHMARK].iloc[-1])
    rækker = []
    with open(LOG, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r["ticker"]
            if t not in kurser:
                continue
            ny = mb.pct(float(kurser[t].iloc[-1]), float(r["kurs"]))
            bm = mb.pct(bm_nu, float(r["bm_kurs"]))
            rækker.append({
                "uge": r["uge"], "dato": r["dato"], "rang": int(r["rang"]),
                "ticker": t, "navn": mb.WATCHLIST.get(t, t),
                "ny": ny, "bm": bm, "forskel": ny - bm,
            })
    return rækker
