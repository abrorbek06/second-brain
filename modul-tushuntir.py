#!/usr/bin/env python3
"""Har modul uchun o'zbekcha tushuntirish yozadi (Claude Code orqali, bir marta).
Keyin faqat kodi o'zgargan modullarni qayta yozadi.

    python3 ~/Obsidian/modul-tushuntir.py                 # yo'q yoki eskirganlarini yozish (hamma loyiha)
    python3 ~/Obsidian/modul-tushuntir.py staydy          # bitta loyiha
    python3 ~/Obsidian/modul-tushuntir.py --holat         # qaysilari yangi, qaysilari eskirgan — faqat ko'rsatish
    python3 ~/Obsidian/modul-tushuntir.py --parallel 3    # bir vaqtda nechta (standart 3)
"""
import os, re, sys, glob, subprocess, datetime
from concurrent.futures import ThreadPoolExecutor

HOME = os.path.expanduser("~")
VAULT = os.path.join(HOME, "Library/Mobile Documents/iCloud~md~obsidian/Documents/Ikkinchi Miya")
BASE = os.path.join(VAULT, "09 Kod bazasi")
PROJ = os.path.join(HOME, "Projects")
ENV = dict(os.environ, PATH=f"{HOME}/.local/bin:/opt/homebrew/bin:" + os.environ.get("PATH", ""))
NOMLAR = {"staydy": "Staydy", "kipos": "Kipos", "usmle": "USMLE", "pos": "pos (kassa ilovasi)"}  # muhimlik tartibida

PROMPT = """Sen {nom} loyihasining kodini tahlil qilayotgan katta dasturchisan. Vazifa: "{modul}" moduli haqida o'zbek tilida (lotin) to'liq, aniq tushuntirish yoz — keyinchalik project manager va AI shu matnga qarab, kodni qayta o'qimasdan task yozadi.

Modul xaritasi (fayllar, API, jadvallar) quyida. Kod: {src}
Muhim fayllarni o'zing och va o'qi (Read/Grep/Glob). Faqat kodda ko'rganingni yoz, taxmin qilma; noaniq joyni "aniqlanmagan" deb yoz.

Faqat quyidagi markdown'ni chiqar (boshqa gap qo'shma, ``` ichiga olma):

## Vazifasi
1–3 gap: modul nima qiladi, kim uchun.

## Qanday ishlaydi
Asosiy oqimlar qadamma-qadam (har biri: kim boshlaydi → qaysi endpoint/ekran → qaysi funksiya → bazada nima o'zgaradi).

## Asosiy fayllar va funksiyalar
- `fayl/yo'li` — `FunksiyaNomi` (qator): nima qiladi
(eng muhim 8–20 tasi)

## Biznes qoidalari va cheklovlar
Validatsiya, statuslar va ularning o'tishi, ruxsatlar (kim nima qila oladi), hisob-kitob qoidalari, limitlar.

## Ma'lumotlar
Qaysi jadvallar/modellar, muhim ustunlar va ular orasidagi bog'liqlik.

## Bog'liqliklar
Qaysi boshqa modullarni chaqiradi va kim uni chaqiradi; frontend qaysi sahifalari ishlatadi; tashqi servislar.

## Ma'lum muammolar va diqqat qilinadigan joylar
Kodda ko'ringan xatolar, TODO'lar, xavfli joylar, testsiz qismlar.

## O'zgartirish uchun maslahat
Shu modulga o'zgartirish kiritmoqchi bo'lgan dasturchi bilishi kerak bo'lgan 3–5 narsa.

---
MODUL XARITASI:
{xarita}
"""

def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True).stdout.strip()

def repos(src):
    return [os.path.dirname(g) for g in glob.glob(os.path.join(src, "**/.git"), recursive=True) if "node_modules" not in g][:6]

def heads(src):
    return {os.path.relpath(r, PROJ): sh(["git", "rev-parse", "--short", "HEAD"], r) for r in repos(src)}

def changed_files(src, old_heads):
    """old_heads bo'yicha o'zgargan fayllar (commit + commit qilinmagan), loyiha ildiziga nisbatan."""
    out = set()
    for r in repos(src):
        rel = os.path.relpath(r, PROJ); old = old_heads.get(rel)
        if not old: return None  # yangi repo — hammasi o'zgargan deb hisoblanadi
        diff = sh(["git", "diff", "--name-only", old, "HEAD"], r).splitlines()
        diff += [l[3:] for l in sh(["git", "status", "--porcelain"], r).splitlines()]
        prefix = os.path.relpath(r, src)
        out |= {os.path.normpath(os.path.join(prefix, f)) for f in diff if f}
    return out

def module_files(page):
    return set(re.findall(r"^- `([^`]+\.\w+)`", open(page).read(), re.M))

def read_meta(path):
    if not os.path.exists(path): return None
    t = open(path).read()
    m = re.search(r"^heads: (.+)$", t, re.M)
    return dict(x.split("@") for x in m.group(1).split(", ") if "@" in x) if m else {}

def status(key):
    nom = NOMLAR[key]; src = os.path.join(PROJ, key)
    mdir = os.path.join(BASE, nom, "Modullar"); tdir = os.path.join(BASE, nom, "Tushuntirish")
    res = []
    for page in sorted(glob.glob(os.path.join(mdir, "*.md"))):
        mod = os.path.basename(page)[:-3]
        if mod == "Modullar": continue
        out = os.path.join(tdir, f"{mod}.md"); meta = read_meta(out)
        if meta is None: res.append((mod, page, out, "yo'q")); continue
        ch = changed_files(src, meta)
        if ch is None or (ch & module_files(page)): res.append((mod, page, out, "eskirgan"))
        else: res.append((mod, page, out, "yangi"))
    return res

def write_one(key, mod, page, out):
    nom = NOMLAR[key]; src = os.path.join(PROJ, key)
    xarita = open(page).read()
    prompt = PROMPT.format(nom=nom, modul=mod, src=src, xarita=xarita[:12000])
    r = subprocess.run(["claude", "-p", prompt, "--allowedTools", "Read,Grep,Glob", "--add-dir", src],
                       cwd=src, env=ENV, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=900)
    body = r.stdout.strip()
    if r.returncode != 0 or "## Vazifasi" not in body:
        return f"XATO {key}/{mod}: {r.stderr.strip()[:200] or body[:200]}"
    body = body[body.index("## Vazifasi"):]
    hs = heads(src)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write("\n".join([
        "---", "turi: modul-tushuntirish", f"loyiha: {nom}", f"modul: {mod}",
        f"yozilgan: {datetime.date.today()}", "heads: " + ", ".join(f"{k}@{v}" for k, v in hs.items()), "---",
        f"# {nom} — {mod}: qanday ishlaydi", "",
        f"Fayllar, API va jadvallar ro'yxati: [[{nom}/Modullar/{mod}|modul xaritasi]] · Kod bazasi: [[{nom}/{nom} — kod bazasi|{nom}]]", "",
        f"> Claude Code kodni o'qib yozgan ({datetime.date.today()}, commit: {', '.join(hs.values())}). Kod o'zgarsa `python3 ~/Obsidian/modul-tushuntir.py` faqat o'zgarganlarini qayta yozadi.", "",
        body, ""]))
    return f"ok {key}/{mod}"

def main():
    keys = [a for a in sys.argv[1:] if a in NOMLAR] or list(NOMLAR)
    par = int(sys.argv[sys.argv.index("--parallel") + 1]) if "--parallel" in sys.argv else 3
    jobs = []
    for k in keys:
        st = status(k)
        cnt = {s: sum(1 for x in st if x[3] == s) for s in ("yangi", "eskirgan", "yo'q")}
        yoq = cnt["yo'q"]
        print(f"{NOMLAR[k]}: yangi {cnt['yangi']}, eskirgan {cnt['eskirgan']}, yozilmagan {yoq}")
        jobs += [(k, m, p, o) for m, p, o, s in st if s != "yangi"]
    if "--holat" in sys.argv or not jobs:
        return
    print(f"Yoziladi: {len(jobs)} ta modul, {par} tadan parallel", flush=True)
    with ThreadPoolExecutor(par) as ex:
        for msg in ex.map(lambda j: write_one(*j), jobs):
            print(msg, flush=True)
    print("TAYYOR", flush=True)

if __name__ == "__main__":
    main()
