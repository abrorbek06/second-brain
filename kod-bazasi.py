#!/usr/bin/env python3
"""Ikkinchi miyadagi "09 Kod bazasi"ni loyihalar kodidan yig'adi va yangilaydi.

Ishlatish:
    python3 ~/Obsidian/kod-bazasi.py            # graflarni yangilab, bazani qayta yig'ish
    python3 ~/Obsidian/kod-bazasi.py --tez      # graflarni yangilamasdan, faqat ko'chirish
    python3 ~/Obsidian/kod-bazasi.py kipos      # faqat bitta loyiha
"""
import os, re, sys, shutil, subprocess, glob, datetime
from collections import Counter

HOME = os.path.expanduser("~")
VAULT = os.path.join(HOME, "Library/Mobile Documents/iCloud~md~obsidian/Documents/Ikkinchi Miya")
OUT = os.path.join(VAULT, "09 Kod bazasi")
PROJ = os.path.join(HOME, "Projects")
ENV = dict(os.environ, PATH=f"{HOME}/.local/bin:/opt/homebrew/bin:" + os.environ.get("PATH", ""))

SKIP_DIRS = {"node_modules", ".git", "build", "dist", "graphify-out", ".dart_tool", "coverage",
             "playwright-report", "test-results", ".idea", ".vscode", "Pods", "ephemeral",
             "generated", "gen", ".next", ".turbo", "bin", "backups", "migration-recovery-backups"}

PROJECTS = {
    "kipos": dict(nom="Kipos", sahifa="Kipos",
                  docs=["README.md", "*/README.md", "docs/TZ/*.md", "docs/TZ/modullar/*.md",
                        "docs/TZ/qarorlar/*.md", "deploy/*.md", "api/*.md"],
                  api=[("openapi", "api/openapi.yaml")],
                  db=[("sql", "backend/db/schema/*.sql")],
                  modules=[("Backend (Go)", "backend/internal/*"), ("Ofis web (React)", "web/apps/ofis/src/features/*"),
                           ("Kassa ilovasi (Flutter)", "apps/pos/lib/features/*")],
                  skip_mod={"testfix", "seed", "platform", "server", "measure", "idempotency", "calc", "events", "connection"},
                  syn={"ordering": ["order", "checkout", "cart", "sell"], "inventory": ["stock", "warehouse", "inventory", "nomenclature"],
                       "catalog": ["catalog", "menu", "categor", "item", "modifier", "discount"], "hall": ["hall", "floor", "table"],
                       "recipe": ["recipe", "ttk"], "payment": ["payment", "pay", "shift"], "identity": ["identity", "auth", "user", "login", "pin", "role"],
                       "report": ["report", "dashboard"], "printing": ["print", "receipt", "kitchen"], "realtime": ["realtime", "ws", "event"],
                       "media": ["media", "image", "upload"]}),
    "pos": dict(nom="pos (kassa ilovasi)", sahifa="Kipos",
                docs=["README.md", "docs/*.md", "docs/adr/*.md"],
                api=[], db=[],
                modules=[("Ekranlar (view)", "lib/features/view/*"), ("Yadro (core)", "lib/core/*")],
                skip_mod={"constants", "extension", "mixins", "common", "components", "config", "error"}, syn={}),
    "staydy": dict(nom="Staydy", sahifa="Staydy",
                   docs=["*/README.md", "*/AGENTS.md", "*/CLAUDE.md", "*/deploy/*.md", "*/docs/*.md"],
                   api=[("huma", "staydy-backend/internal/controller/http/*.go")],
                   db=[("sql", "staydy-backend/db/query/schema.sql")],
                   modules=[("Backend usecase (Go)", "staydy-backend/internal/usecase/*")],
                   skip_mod={"maintenance"},
                   syn={"crm": ["crm", "lead"], "finance": ["finance", "invoice", "payment", "debtor", "tolov", "balance"],
                        "points": ["point", "xp", "gamification", "reyting"], "shop": ["shop", "dokon"], "lesson": ["lesson", "darslar", "attendance"],
                        "group": ["group", "guruh"], "notify": ["notif", "bildirish", "broadcast", "telegram"], "studentauth": ["studentauth", "login"],
                        "advice": ["advice", "gemini", "ai_"], "chat": ["chat"], "salary": ["salary", "maosh"]}),
    "usmle": dict(nom="USMLE", sahifa="USMLE",
                  docs=["*.md", "*/README.md", "*/STATUS.md", "*/FRONTEND_HANDOFF.md", "*/AGENTS.md",
                        "*/CLAUDE.md", "*/docs/*.md"],
                  api=[("nest", "usmle-backend/src/**/*.controller.ts")],
                  db=[("prisma", "usmle-backend/prisma/schema.prisma")],
                  modules=[("Backend modul (NestJS)", "usmle-backend/src/modules/*"), ("Frontend (React)", "usmle-frontend/src/features/*")],
                  skip_mod={"capabilities", "landing"},
                  syn={"identity": ["identity", "auth", "session", "login", "oauth", "telegram"], "test-engine": ["test-engine", "attempt", "test_engine", "testengine"],
                       "question-bank": ["question-bank", "question_bank", "question", "import"], "mock-exams": ["mock-exam", "mock_exam", "mockexam"],
                       "study-planner": ["planner", "study-plan", "study_plan"], "reference-library": ["reference", "lab-value", "lab_value"],
                       "study-library": ["study-library", "article", "library"], "flashcards": ["flashcard"], "question-bookmarks": ["bookmark"]}),
}

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, env=ENV, capture_output=True, text=True).stdout

def md_escape(s):
    return s.replace("|", "\\|").strip()

# ---------------- API ----------------
def api_openapi(path):
    rows, cur = [], None
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = re.match(r"^  (/[^:]*):\s*$", line)
        if m: cur = m.group(1); continue
        m = re.match(r"^    (get|post|put|patch|delete):\s*$", line)
        if m and cur: rows.append([m.group(1).upper(), cur, ""]); continue
        m = re.match(r"^      summary:\s*(.+)$", line)
        if m and rows and not rows[-1][2]: rows[-1][2] = m.group(1).strip("'\"")
    return rows

def api_huma(files):
    rows = []
    for f in files:
        t = open(f, encoding="utf-8", errors="ignore").read()
        for chunk in t.split("huma.Operation{")[1:]:
            c = chunk[:900]
            p = re.search(r'Path:\s*"([^"]+)"', c)
            m = re.search(r"Method:\s*(?:http\.Method)?\"?(\w+)", c)
            s = re.search(r'Summary:\s*"([^"]*)"', c)
            if p and m: rows.append([m.group(1).upper(), p.group(1), s.group(1) if s else ""])
    return rows

def api_nest(files):
    rows = []
    for f in files:
        t = open(f, encoding="utf-8", errors="ignore").read()
        cm = re.search(r"@Controller\(\s*(?:['\"]([^'\"]*)['\"]|\{[^}]*path:\s*['\"]([^'\"]*)['\"])?", t)
        base = (cm.group(1) or cm.group(2) or "") if cm else ""
        for m in re.finditer(r"@(Get|Post|Put|Patch|Delete)\(\s*(?:['\"]([^'\"]*)['\"])?\s*\)[\s\S]{0,400}?\n\s*(?:async\s+)?(\w+)\s*\(", t):
            path = "/" + "/".join(x.strip("/") for x in [base, m.group(2) or ""] if x and x.strip("/"))
            rows.append([m.group(1).upper(), path or "/", m.group(3)])
    return rows

# ---------------- DB ----------------
def db_sql(files):
    tables = {}
    for f in files:
        t = open(f, encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"CREATE TABLE(?: IF NOT EXISTS)?\s+([\w.\"]+)\s*\((.*?)\n\);", t, re.S | re.I):
            cols = []
            for line in m.group(2).splitlines():
                line = line.strip().rstrip(",")
                mm = re.match(r'"?([a-z_][\w]*)"?\s+([A-Za-z]\w*(?:\([^)]*\))?(?:\[\])?)', line)
                if mm and mm.group(1).upper() not in ("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "EXCLUDE"):
                    cols.append(f"{mm.group(1)} `{mm.group(2).lower()}`")
            tables[m.group(1).replace('"', '')] = cols
        for m in re.finditer(r"ALTER TABLE\s+([\w.\"]+)\s+ADD COLUMN\s+\"?(\w+)\"?\s+(\w+)", t, re.I):
            tables.setdefault(m.group(1).replace('"', ''), []).append(f"{m.group(2)} `{m.group(3).lower()}`")
    return tables

def db_prisma(files):
    tables = {}
    for f in files:
        t = open(f, encoding="utf-8", errors="ignore").read()
        for m in re.finditer(r"^(model|enum)\s+(\w+)\s*\{(.*?)^\}", t, re.S | re.M):
            kind, name, body = m.groups()
            items = []
            for line in body.splitlines():
                line = line.strip()
                if not line or line.startswith("//") or line.startswith("@@"): continue
                parts = line.split()
                items.append(parts[0] if kind == "enum" else f"{parts[0]} `{parts[1]}`" if len(parts) > 1 else parts[0])
            tables[("enum " if kind == "enum" else "") + name] = items
    return tables

# ---------------- Tuzilma ----------------
def tree(root, max_depth=3):
    lines = []
    def walk(d, depth):
        try: entries = sorted(os.scandir(d), key=lambda e: e.name)
        except OSError: return
        for e in entries:
            if e.is_dir(follow_symlinks=False) and e.name not in SKIP_DIRS and not e.name.startswith("."):
                n = sum(len(fs) for _, _, fs in _walk(e.path))
                lines.append(f"{'  ' * depth}- `{e.name}/` — {n} fayl")
                if depth + 1 < max_depth: walk(e.path, depth + 1)
    walk(root, 0)
    return lines

def _walk(p):
    for r, ds, fs in os.walk(p):
        ds[:] = [x for x in ds if x not in SKIP_DIRS and not x.startswith(".")]
        yield r, ds, fs

def ext_stats(root):
    c = Counter()
    for r, ds, fs in _walk(root):
        for f in fs:
            if "." in f: c[f.rsplit(".", 1)[1]] += 1
    return c


# ---------------- Modul xaritasi ----------------
CODE_EXT = {"go", "ts", "tsx", "dart", "sql", "prisma", "js", "jsx", "py"}
def all_files(src):
    out = []
    for r, ds, fs in _walk(src):
        for f in fs:
            if f.rsplit(".", 1)[-1] in CODE_EXT:
                out.append(os.path.relpath(os.path.join(r, f), src))
    return out

def layer_of(rel):
    parts = rel.split("/")
    if "test" in parts or "tests" in parts or re.search(r"(_test\.go|\.spec\.ts|\.test\.tsx?|_test\.dart|e2e)", rel): return "Testlar"
    if rel.endswith(".sql") or rel.endswith(".prisma") or "/db/" in rel or "migrations" in rel: return "Baza (schema/so'rov)"
    return "/".join(parts[:3]) if len(parts) > 3 else "/".join(parts[:-1]) or "."

def modules_map(key, cfg, src, dst, api, tables):
    mods = {}
    for label, pat in cfg.get("modules", []):
        for d in sorted(glob.glob(os.path.join(src, pat))):
            if os.path.isdir(d):
                name = os.path.basename(d)
                if name in cfg.get("skip_mod", set()) or name.startswith((".", "_")): continue
                mods.setdefault(name, []).append((label, os.path.relpath(d, src)))
    if not mods: return 0
    files = all_files(src)
    mdir = os.path.join(dst, "Modullar"); os.makedirs(mdir, exist_ok=True)
    index = []
    for name in sorted(mods):
        stems = cfg.get("syn", {}).get(name) or [name.rstrip("s") if len(name) > 4 else name]
        stems = [x.lower() for x in stems]
        own = [f for f in files if any(f.startswith(root + "/") for _, root in mods[name])]
        rel = [f for f in files if f not in own and any(st in os.path.basename(f).lower() for st in stems)]
        api_m = [r for r in api if any(st in r[1].lower() for st in stems)]
        tab_m = [t for t in tables if not t.startswith("enum ") and any(st in t.lower() for st in stems)]
        L = [f"---", f"turi: kod-modul", f"loyiha: {cfg['sahifa']}", f"---", f"# {cfg['nom']} — modul: {name}", "",
             f"Kod bazasi: [[{cfg['nom']}/{cfg['nom']} — kod bazasi|{cfg['nom']}]] · Kalit so'zlar: {', '.join(stems)}", "",
             "> Avtomatik xarita: fayllar papka va nom bo'yicha topilgan. Task yozishdan oldin fayllarni ochib tasdiqlang.", "",
             "## Modul papkalari"] + [f"- {l}: `{r}/`" for l, r in mods[name]]
        groups = {}
        for f in own + rel: groups.setdefault(layer_of(f), []).append(f)
        L += ["", f"## Fayllar ({len(own)} ta modul ichida, {len(rel)} ta boshqa joyda)"]
        for g in sorted(groups, key=lambda x: (x == "Testlar", x)):
            fl = sorted(groups[g])
            L += ["", f"**{g}** — {len(fl)} ta"] + [f"- `{f}`" for f in fl[:40]] + ([f"- … yana {len(fl) - 40} ta"] if len(fl) > 40 else [])
        if api_m:
            L += ["", f"## API ({len(api_m)} ta)", "| Metod | Yo'l | Tavsif |", "|---|---|---|"] + [f"| {m} | `{md_escape(p)}` | {md_escape(d)} |" for m, p, d in api_m[:60]]
        if tab_m:
            L += ["", f"## Jadvallar ({len(tab_m)} ta)"] + [f"- **{t}**: {', '.join(tables[t][:20])}" for t in tab_m]
        open(os.path.join(mdir, f"{name}.md"), "w").write("\n".join(L))
        index.append(f"| [[{cfg['nom']}/Modullar/{name}\\|{name}]] | {len(own)} + {len(rel)} | {len(api_m)} | {len(tab_m)} |")
    open(os.path.join(mdir, "Modullar.md"), "w").write("\n".join(
        [f"# {cfg['nom']} — modullar xaritasi", "", "Har modul: qaysi qatlamda qaysi fayllar, qaysi API va jadvallar.", "",
         "| Modul | Fayl (ichida + tashqarida) | API | Jadval |", "|---|---|---|---|"] + index))
    return len(mods)

# ---------------- Texnologiyalar ----------------
def deps(src):
    L = []
    for f in sorted(glob.glob(os.path.join(src, "**/go.mod"), recursive=True)):
        if "node_modules" in f: continue
        req = re.findall(r"^\s*([\w./-]+\.[\w./-]+)\s+(v[\w.+-]+)(?!.*// indirect)", open(f).read(), re.M)
        L += ["", f"### Go — `{os.path.relpath(f, src)}`"] + [f"- `{n}` {v}" for n, v in req]
    import json
    for f in sorted(glob.glob(os.path.join(src, "**/package.json"), recursive=True)):
        if "node_modules" in f: continue
        try: j = json.load(open(f))
        except Exception: continue
        d = j.get("dependencies", {}); dd = j.get("devDependencies", {})
        if not d and not dd: continue
        L += ["", f"### Node — `{os.path.relpath(f, src)}`", "**Asosiy:** " + (", ".join(f"`{k}` {v}" for k, v in d.items()) or "—"),
              "", "**Dev:** " + (", ".join(f"`{k}`" for k in dd) or "—")]
    for f in sorted(glob.glob(os.path.join(src, "**/pubspec.yaml"), recursive=True)):
        if "/build/" in f or ".dart_tool" in f or "/ephemeral/" in f: continue
        t = open(f).read(); m = re.search(r"^dependencies:\n((?:[ \t]+.*\n|\n)*)", t, re.M)
        names = re.findall(r"^  ([a-z_0-9]+):", m.group(1), re.M) if m else []
        if names: L += ["", f"### Flutter — `{os.path.relpath(f, src)}`", ", ".join(f"`{n}`" for n in names)]
    return L

# ---------------- Asosiy ----------------
def build(key, cfg, update_graph):
    src = os.path.join(PROJ, key)
    if not os.path.isdir(src):
        print(f"{key}: papka yo'q, o'tkazildi"); return None
    dst = os.path.join(OUT, cfg["nom"])
    print(f"== {key}")
    if update_graph:
        run(["graphify", "update", "."], src)
        run(["graphify", "label", ".", "--missing-only", "--backend=claude-cli"], src)
        run(["graphify", "export", "wiki"], src)
    os.makedirs(dst, exist_ok=True)
    for e in os.listdir(dst):  # "Tushuntirish" (AI yozgan modul tavsiflari) saqlanadi
        if e == "Tushuntirish": continue
        pth = os.path.join(dst, e)
        shutil.rmtree(pth) if os.path.isdir(pth) else os.remove(pth)
    # 1. wiki
    w = os.path.join(src, "graphify-out/wiki")
    if os.path.isdir(w):
        shutil.copytree(w, os.path.join(dst, "Kod wiki"))
    rep = os.path.join(src, "graphify-out/GRAPH_REPORT.md")
    if os.path.exists(rep): shutil.copy(rep, os.path.join(dst, "Graf hisoboti.md"))
    # 2. hujjatlar
    docs = []
    for pat in cfg["docs"]:
        for f in sorted(glob.glob(os.path.join(src, pat), recursive=True)):
            if "node_modules" in f or "graphify-out" in f: continue
            rel = os.path.relpath(f, src)
            target = os.path.join(dst, "Hujjatlar", rel)
            if os.path.exists(target): continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy(f, target); docs.append(rel)
    # 3. API
    api = []
    for kind, pat in cfg["api"]:
        files = sorted(glob.glob(os.path.join(src, pat), recursive=True))
        if kind == "openapi" and files: api += api_openapi(files[0])
        if kind == "huma": api += api_huma(files)
        if kind == "nest": api += api_nest(files)
    if api:
        groups = {}
        for m, p, s in api:
            seg = [x for x in p.split("/") if x and x not in ("api", "v1") and not x.startswith("{")]
            groups.setdefault(seg[0] if seg else "/", []).append((m, p, s))
        L = [f"# {cfg['nom']} — API", "", f"Koddan avtomatik olingan: **{len(api)} ta endpoint**. Yangilangan: {datetime.date.today()}", ""]
        for g in sorted(groups):
            L += [f"## {g}", "", "| Metod | Yo'l | Tavsif |", "|---|---|---|"]
            L += [f"| {m} | `{md_escape(p)}` | {md_escape(s)} |" for m, p, s in groups[g]] + [""]
        open(os.path.join(dst, "API.md"), "w").write("\n".join(L))
    # 4. DB
    tables = {}
    for kind, pat in cfg["db"]:
        files = sorted(glob.glob(os.path.join(src, pat), recursive=True))
        tables.update(db_prisma(files) if kind == "prisma" else db_sql(files))
    if tables:
        L = [f"# {cfg['nom']} — ma'lumotlar bazasi", "", f"Koddan avtomatik olingan: **{len([t for t in tables if not t.startswith('enum ')])} ta jadval**. Yangilangan: {datetime.date.today()}", ""]
        for t in sorted(tables, key=lambda x: (x.startswith("enum "), x)):
            L += [f"### {t}", ", ".join(tables[t]) or "—", ""]
        open(os.path.join(dst, "Ma'lumotlar bazasi.md"), "w").write("\n".join(L))
    nmods = modules_map(key, cfg, src, dst, api, tables)
    dl = deps(src)
    if dl: open(os.path.join(dst, "Texnologiyalar.md"), "w").write("\n".join([f"# {cfg['nom']} — texnologiyalar va kutubxonalar", "", "Koddagi bog'liqlik fayllaridan (go.mod, package.json, pubspec.yaml) avtomatik olingan."] + dl))
    # 5. Tuzilma
    st = ext_stats(src)
    L = [f"# {cfg['nom']} — kod tuzilmasi", "", f"`~/Projects/{key}` — papkalar (3 daraja)", ""] + tree(src)
    open(os.path.join(dst, "Tuzilma.md"), "w").write("\n".join(L))
    # git
    gitinfo = []
    for g in sorted(glob.glob(os.path.join(src, "**/.git"), recursive=True))[:5]:
        r = os.path.dirname(g)
        n = run(["git", "rev-list", "--count", "HEAD"], r).strip()
        last = run(["git", "log", "-1", "--format=%cs — %s"], r).strip()
        dirty = len([x for x in run(["git", "status", "--porcelain"], r).splitlines() if x])
        gitinfo.append(f"| `{os.path.relpath(r, PROJ)}` | {n} | {md_escape(last)} | {dirty} |")
    # 6. indeks
    nodes = comms = "?"
    if os.path.exists(rep):
        m = re.search(r"(\d+) nodes · (\d+) edges · (\d+) communities", open(rep).read())
        if m: nodes, comms = m.group(1), m.group(3)
    top = []
    idx = os.path.join(w, "index.md")
    if os.path.exists(idx):
        for line in open(idx):
            m = re.match(r"- \[(.+?)\]\((.+?)\) — (\d+) nodes", line)
            if m: top.append(f"- [[{cfg['nom']}/Kod wiki/{m.group(2)[:-3]}|{m.group(1)}]] — {m.group(3)} element")
            if len(top) >= 25: break
    L = [f"---", f"turi: kod-bazasi", f"loyiha: {cfg['sahifa']}", f"yangilangan: {datetime.date.today()}", f"---",
         f"# {cfg['nom']} — kod bazasi", "",
         f"Loyiha sahifasi: [[{cfg['sahifa']}]] · Kod: `~/Projects/{key}`", "",
         "> Bu papka avtomatik yig'iladi (`python3 ~/Obsidian/kod-bazasi.py`). Qo'lda tahrirlamang — keyingi yangilanishda o'chadi. O'z eslatmalaringizni loyiha sahifasiga yozing.", "",
         "## Tarkibi",
         f"- [[{cfg['nom']}/API|API]] — {len(api)} ta endpoint" if api else "- API: —",
         f"- [[{cfg['nom']}/Ma'lumotlar bazasi|Ma'lumotlar bazasi]] — {len([t for t in tables if not t.startswith('enum ')])} ta jadval" if tables else "- Ma'lumotlar bazasi: —",
         f"- [[{cfg['nom']}/Modullar/Modullar|Modullar xaritasi]] — {nmods} ta modul: har biri qaysi fayllarda, qaysi API va jadvallar" if nmods else "- Modullar xaritasi: —",
         f"- **Modullar qanday ishlaydi** — `Tushuntirish/` papkasi (har modul uchun o'zbekcha tavsif)",
         f"- [[{cfg['nom']}/Texnologiyalar|Texnologiyalar]] — ishlatilgan kutubxonalar",
         f"- [[{cfg['nom']}/Tuzilma|Kod tuzilmasi]]",
         f"- [[{cfg['nom']}/Graf hisoboti|Graf hisoboti]] — {nodes} element, {comms} bo'lim",
         f"- [[{cfg['nom']}/Kod wiki/index|Kod wiki]] — har bo'lim bo'yicha maqola",
         f"- Hujjatlar — {len(docs)} ta fayl (`Hujjatlar/` papkasi)", "",
         "## Fayllar", ", ".join(f"{e}: {n}" for e, n in st.most_common(8)), "",
         "## Git", "| Repo | Commitlar | Oxirgi commit | Commit qilinmagan fayl |", "|---|---|---|---|"] + gitinfo + ["",
         "## Asosiy bo'limlar (kod wiki)"] + top + ["", "## Hujjatlar"] + [f"- `{d}`" for d in docs]
    open(os.path.join(dst, f"{cfg['nom']} — kod bazasi.md"), "w").write("\n".join(L))
    print(f"   wiki, {len(docs)} hujjat, {len(api)} API, {len(tables)} jadval, {nmods} modul")
    return cfg["nom"], len(api), len(tables), nodes, comms, len(docs)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    update_graph = "--tez" not in sys.argv
    os.makedirs(OUT, exist_ok=True)
    res = []
    for k, cfg in PROJECTS.items():
        if args and k not in args: continue
        r = build(k, cfg, update_graph)
        if r: res.append(r)
    if not args:
        L = ["# Kod bazasi", "", f"Loyihalar kodidan avtomatik yig'ilgan bilim bazasi. Yangilangan: {datetime.datetime.now():%Y-%m-%d %H:%M}", "",
             "Yangilash: Terminal'da `python3 ~/Obsidian/kod-bazasi.py` yoki Claude'ga **\"kod bazasini yangila\"**.", "",
             "| Loyiha | API | Jadval | Graf (element / bo'lim) | Hujjat |", "|---|---|---|---|---|"]
        L += [f"| [[{n}/{n} — kod bazasi\\|{n}]] | {a} | {t} | {no} / {c} | {d} |" for n, a, t, no, c, d in res]
        L += ["", "Ishxona loyihalari (Growz, Bizon, ERP, HRM) kodi bu Mac'da yo'q — ular Notion, Figma va Jira'dagi hujjatlar asosida loyiha sahifalarida."]
        open(os.path.join(OUT, "Kod bazasi.md"), "w").write("\n".join(L))
    print("tayyor")

if __name__ == "__main__":
    main()
