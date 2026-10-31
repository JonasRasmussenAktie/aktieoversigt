"""
Dashboard - samler morgenbriefen i en overskuelig hjemmeside (dashboard.html).

Kør:  python dashboard.py
Siden åbner automatisk i din browser.

Kun til eget brug. Information, ikke investeringsrådgivning.
"""

import datetime as dt
import html
import sys
import webbrowser

import morgenbrief as mb

LABELS = {
    "STOR_BEVÆGELSE": "Stor bevægelse",
    "NÆR_52U_TOP": "Nær årets top",
    "NÆR_52U_BUND": "Nær årets bund",
    "MOMENTUM_OP": "Stærk måned",
    "MOMENTUM_NED": "Svag måned",
}


def e(x):
    """Gør tekst sikker at sætte ind i en hjemmeside."""
    return html.escape(str(x))


def sikkert_link(url):
    return url if url.startswith(("http://", "https://")) else ""


def klasse(v):
    return "op" if v >= 0 else "ned"


def pil(v):
    return "▲" if v >= 0 else "▼"


def sparkline(serie, w=100, h=28):
    v = [float(x) for x in serie.iloc[-60:]]
    lo, hi = min(v), max(v)
    spænd = (hi - lo) or 1.0
    pkt = " ".join(
        f"{i * w / (len(v) - 1):.1f},{h - 2 - (x - lo) / spænd * (h - 4):.1f}"
        for i, x in enumerate(v)
    )
    k = "op" if v[-1] >= v[0] else "ned"
    return (
        f'<svg class="spark {k}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
        f'role="img" aria-label="Kursudvikling de seneste 60 dage">'
        f'<polyline points="{pkt}" fill="none" stroke="currentColor" '
        f'stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>'
    )


def markedskort(t, v):
    return (
        '<div class="kort">'
        f'<div class="lille">{e(mb.WATCHLIST[t])}</div>'
        f'<div class="stor {klasse(v["dag"])}">{pil(v["dag"])} {v["dag"]:+.1f}%</div>'
        f'<div class="lille">Seneste måned: {v["maaned"]:+.1f}%</div>'
        "</div>"
    )


def signalkort(t, v, signaler, nyheder):
    tags = "".join(f'<span class="tag">{e(LABELS[k])}</span>' for k, _ in signaler)
    punkter = "".join(f"<li>{e(tekst)}</li>" for _, tekst in signaler)
    forklaringer = "".join(
        f'<p class="forklaring"><strong>Hvad kan det betyde?</strong> {e(mb.FORKLARING[k])}</p>'
        for k, _ in signaler
    )
    nyhedshtml = ""
    if nyheder:
        li = ""
        for titel, link in nyheder:
            link = sikkert_link(link)
            if link:
                li += f'<li><a href="{e(link)}" target="_blank" rel="noopener noreferrer">{e(titel)}</a></li>'
            else:
                li += f"<li>{e(titel)}</li>"
        nyhedshtml = f'<div class="nyheder"><strong>Nyheder</strong><ul>{li}</ul></div>'
    return (
        '<article class="kort signal">'
        f'<header><h3>{e(mb.WATCHLIST[t])}</h3>'
        f'<span class="{klasse(v["dag"])} tal">{pil(v["dag"])} {v["dag"]:+.1f}% i dag</span></header>'
        f'<div class="tags">{tags}</div>'
        f"<ul>{punkter}</ul>"
        f'<p class="lille">Kurs: {v["kurs"]:.2f} · Svingning: {v["svingning"]:.0f}% om året</p>'
        f"{forklaringer}{nyhedshtml}"
        "</article>"
    )


def tabelrække(t, v, serie):
    def celle(værdi, tekst, ekstra=""):
        return f'<td data-v="{værdi}" class="{ekstra}">{tekst}</td>'

    return (
        "<tr>"
        f'<th scope="row" data-v="{e(mb.WATCHLIST[t])}">{e(mb.WATCHLIST[t])}</th>'
        + celle(v["kurs"], f'{v["kurs"]:.2f}')
        + celle(v["dag"], f'{pil(v["dag"])} {v["dag"]:+.1f}%', klasse(v["dag"]))
        + celle(v["maaned"], f'{v["maaned"]:+.1f}%', klasse(v["maaned"]))
        + celle(v["aar"], f'{v["aar"]:+.0f}%', klasse(v["aar"]))
        + celle(v["svingning"], f'{v["svingning"]:.0f}%')
        + f'<td data-v="0">{sparkline(serie)}</td>'
        "</tr>"
    )


SKABELON = """<!doctype html>
<html lang="da">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Min aktieoversigt</title>
<style>
:root{
  --bg:#f6f7f9; --kort:#ffffff; --tekst:#1a1d23; --dæmpet:#5b6270; --kant:#e3e6ea;
  --op:#0a7d4f; --ned:#c0392b; --accent:#2457d6; --tag:#eef2ff;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0f1115; --kort:#181b21; --tekst:#e6e8ec; --dæmpet:#9aa1ad; --kant:#2a2f38;
    --op:#3ecf8e; --ned:#ff7b6b; --accent:#8aa8ff; --tag:#222a44;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tekst);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.5}
.side{max-width:980px;margin:0 auto;padding:20px 16px 48px}
h1{font-size:1.5rem;margin:0 0 4px}
h2{font-size:1.1rem;margin:32px 0 12px}
h3{font-size:1rem;margin:0}
.lille{font-size:.85rem;color:var(--dæmpet)}
.advarsel{background:var(--kort);border:1px solid var(--kant);border-left:4px solid var(--accent);
  border-radius:8px;padding:10px 14px;margin:14px 0;font-size:.9rem}
.gitter{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.kort{background:var(--kort);border:1px solid var(--kant);border-radius:10px;padding:14px}
.stor{font-size:1.5rem;font-weight:650}
.op{color:var(--op)} .ned{color:var(--ned)}
.signal header{display:flex;justify-content:space-between;gap:8px;align-items:baseline;flex-wrap:wrap}
.tal{font-weight:600}
.tags{margin:8px 0}
.tag{display:inline-block;background:var(--tag);color:var(--accent);border-radius:99px;
  padding:2px 10px;font-size:.78rem;margin:0 6px 4px 0}
.signal ul{margin:6px 0 6px 18px;padding:0}
.forklaring{font-size:.9rem;margin:8px 0}
.nyheder{font-size:.9rem;border-top:1px solid var(--kant);margin-top:10px;padding-top:8px}
.nyheder a{color:var(--accent)}
.tom{color:var(--dæmpet)}
.værktøj{display:flex;gap:8px;margin-bottom:8px}
input[type=search]{flex:1;padding:9px 12px;border-radius:8px;border:1px solid var(--kant);
  background:var(--kort);color:var(--tekst);font-size:1rem}
.rul{overflow-x:auto;border:1px solid var(--kant);border-radius:10px;background:var(--kort)}
table{border-collapse:collapse;width:100%;min-width:640px;font-size:.92rem}
th,td{padding:9px 12px;text-align:right;border-bottom:1px solid var(--kant);white-space:nowrap}
th[scope=row],thead th:first-child{text-align:left}
thead th{font-size:.8rem;color:var(--dæmpet);cursor:pointer;user-select:none}
thead th:hover,thead th:focus{color:var(--accent);outline:none}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:none}
.spark{width:90px;height:26px;display:block;margin-left:auto}
.spark.op{color:var(--op)} .spark.ned{color:var(--ned)}
details{background:var(--kort);border:1px solid var(--kant);border-radius:10px;padding:10px 14px}
summary{cursor:pointer;font-weight:600}
pre{white-space:pre-wrap;font-family:inherit;margin:10px 0 0;font-size:.92rem}
footer{margin-top:32px;font-size:.8rem;color:var(--dæmpet)}
</style>
</head>
<body>
<main class="side">
  <h1>Min aktieoversigt</h1>
  <div class="lille">Opdateret {{OPDATERET}}</div>
  <div class="advarsel">Dette er information, ikke rådgivning. Ingen kan forudsige kurser.
    Invester kun penge, du har råd til at tabe.</div>

  <h2>Markedet i dag</h2>
  <div class="gitter">{{MARKED}}</div>

  <h2>Værd at undersøge nærmere</h2>
  <div class="gitter">{{SIGNALER}}</div>

  <h2>Alle dine aktier</h2>
  <div class="værktøj"><input type="search" id="sog" placeholder="Søg efter aktie..." aria-label="Søg efter aktie"></div>
  <div class="rul">
  <table id="tabel">
    <thead><tr>
      <th data-k="t" tabindex="0">Navn</th>
      <th data-k="n" tabindex="0">Kurs*</th>
      <th data-k="n" tabindex="0">I dag</th>
      <th data-k="n" tabindex="0">Måned</th>
      <th data-k="n" tabindex="0">År</th>
      <th data-k="n" tabindex="0">Svingning</th>
      <th>60 dage</th>
    </tr></thead>
    <tbody>{{TABEL}}</tbody>
  </table>
  </div>
  <p class="lille">*Kurser er i hver børs' egen valuta (kroner, dollar, euro, yen osv.), så de kan ikke
  sammenlignes direkte. Sammenlign procenterne. Klik på en kolonne for at sortere.</p>

  <h2>Hvad betyder ordene?</h2>
  <details><summary>Vis ordliste</summary><pre>{{BEGREBER}}</pre></details>

  <footer>Data fra Yahoo Finance (uofficiel kilde, kan være forsinket eller have fejl).</footer>
</main>
<script>
const rækker = () => [...document.querySelectorAll('#tabel tbody tr')];
document.getElementById('sog').addEventListener('input', ev => {
  const q = ev.target.value.toLowerCase();
  rækker().forEach(r => r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none');
});
document.querySelectorAll('th[data-k]').forEach(th => {
  const sorter = () => {
    const i = th.cellIndex, tal = th.dataset.k === 'n';
    const dir = th.dataset.dir === 'a' ? -1 : 1;
    th.dataset.dir = dir === 1 ? 'a' : 'd';
    const tb = document.querySelector('#tabel tbody');
    rækker().sort((a, b) => {
      const x = a.cells[i].dataset.v, y = b.cells[i].dataset.v;
      return (tal ? x - y : x.localeCompare(y, 'da')) * dir;
    }).forEach(r => tb.appendChild(r));
  };
  th.addEventListener('click', sorter);
  th.addEventListener('keydown', ev => { if (ev.key === 'Enter') sorter(); });
});
</script>
</body>
</html>
"""


def main():
    åbn_browser = "--ingen-browser" not in sys.argv

    print("Henter kursdata... (tager ca. 10-30 sekunder)")
    kurser = mb.hent_kurser(mb.WATCHLIST.keys())
    # Hvis for meget data mangler, stopper vi i stedet for at lave en halv side.
    # (På GitHub betyder det, at den gamle, hele side bliver stående.)
    if len(kurser) < len(mb.WATCHLIST) / 2:
        print("Kunne ikke hente nok data. Tjek din internetforbindelse og prøv igen.")
        sys.exit(1)

    tal = {t: mb.nøgletal(s) for t, s in kurser.items()}

    marked = "".join(markedskort(t, tal[t]) for t in ("VT", "SPY", "EXSA.DE", "EEM") if t in tal)

    kort = []
    nye_signaler = []
    for t, v in tal.items():
        signaler = mb.find_signaler(v)
        if not signaler:
            continue
        nyheder = []
        if any(k == "STOR_BEVÆGELSE" for k, _ in signaler):
            nyheder = mb.hent_nyheder(t)
        kort.append(signalkort(t, v, signaler, nyheder))
        for k, _ in signaler:
            nye_signaler.append((v["dato"], t, k, v["kurs"]))
    signaler_html = "".join(kort) or (
        '<p class="tom">Intet usædvanligt i dag. Det er helt normalt - de fleste dage er rolige.</p>'
    )

    tabel = "".join(tabelrække(t, tal[t], kurser[t]) for t in tal)

    side = (
        SKABELON.replace("{{OPDATERET}}", e(dt.datetime.now().strftime("%d-%m-%Y kl. %H:%M")))
        .replace("{{MARKED}}", marked)
        .replace("{{SIGNALER}}", signaler_html)
        .replace("{{TABEL}}", tabel)
        .replace("{{BEGREBER}}", e(mb.BEGREBER.strip()))
    )

    fil = mb.MAPPE / "dashboard.html"
    fil.write_text(side, encoding="utf-8")
    mb.gem_signaler(nye_signaler)
    print(f"Færdig! Siden er gemt som: {fil}")

    if åbn_browser:
        webbrowser.open(fil.as_uri())


if __name__ == "__main__":
    main()
