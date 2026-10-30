#!/usr/bin/env python3
"""
Сортировщик ФИО: вставляет текст из буфера обмена, очищает его от цифр,
формирует таблицу «Фамилия Имя» по алфавиту с комментарием (группа)
и подсчётом уникальных людей.

Запуск:  python3 sorter.py            — GUI (tkinter), кнопка вставки из буфера
         python3 sorter.py --cli      — без GUI: читает буфер через pyperclip/xclip/pbpaste
         python3 sorter.py --file f   — разобрать файл вместо буфера
"""
import re
import sys
import unicodedata

GROUP_KEYS = ("группа", "гр.", "гр", "групп")


def extract_group(raw: str, fallback: str = "—") -> str:
    """Определяет группу по комментарию в строке; если не найдена — fallback (заголовок столбца)."""
    # маркер колоночного комментария: ФИО | "1 Театральная студия" — имя группы как есть
    m = re.search(r"[|—]\s*\"([^\"]*)\"\s*$", raw)
    if m:
        return m.group(1)
    # явный комментарий после разделителя: "| А", "— группа Б", "(гр. В)"
    m = re.search(r"[—|\-/:(]\s*(?:группа|групп|гр\.?)?\s*[:№]?\s*([A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9\-]*)\s*\)?\s*$", raw)
    if m:
        return m.group(1).upper()
    # ключевое слово где угодно в строке: "группа А"
    m = re.search(r"(?:группа|групп|гр\.?)\s*[:№]?\s*([A-Za-zА-Яа-яЁё0-9\-]+)", raw, re.I)
    if m:
        return m.group(1).upper()
    return fallback


CMT_WORDS = {"группа", "гр", "групп", "коммент", "комментарий"}


def _name_words(s: str) -> str:
    """Оставляет только слова-ФИО (буквы, дефис, апостроф), отрезая цифры и служебное."""
    s = re.sub(r"^\s*\d+[\s.)\-:]*", "", s)   # начальный номер "1." / "2)"
    s = re.sub(r"\d+", " ", s)                 # все цифры -> пробел
    s = "".join(ch if (unicodedata.category(ch).startswith("L") or ch in " '-") else " " for ch in s)
    words = [w for w in s.split()
             if (len(w) > 1 or w.isalpha()) and w.lower().rstrip(".") not in CMT_WORDS]
    return " ".join(words[:3])


def clean_name(raw: str) -> str:
    """Убирает цифры, номера строк и комментарий о группе, оставляет Фамилию Имя."""
    # маркер колоночного комментария: ФИО | "1 Театральная студия" — отсечь целиком
    s = re.sub(r"\s*[|—]\s*\"[^\"]*\"\s*$", "", raw)
    if s != raw:
        return _name_words(s)
    # отсекаем комментарий с группой ("— группа А", "| Б", "(гр. В)", ", группа Б-3")
    s = re.sub(r"(?:[—|\-/(:#,.]\s*(?:группа|гр\.?|групп)?\s*[:№]?\s*[A-Za-zА-Яа-яЁё0-9\-]+\s*\)?)\s*$", "", raw, flags=re.I)
    if s == raw:  # ничего не отсечено — оставляем как есть
        trimmed = s
    else:
        trimmed = s
    words_after = [w for w in re.sub(r"\d+", " ", trimmed).split() if re.match(r"[^\W\d_]{2,}$", w, re.U)]
    # если после усечения осталось < 2 слов — возможно, отрезали часть ФИО; пробуем мягкий вариант
    if len(words_after) < 2 and extract_group(raw) != "—":
        soft = re.sub(r"(?:[—|\-/(,#]\s*(?:группа|гр\.?|групп)\s*[:№]?\s*[A-Za-zА-Яа-яЁё0-9\-]+)\s*$", "", raw, flags=re.I)
        if len([w for w in re.sub(r"\d+", " ", soft).split() if re.match(r"[^\W\d_]{2,}$", w, re.U)]) >= 2:
            trimmed = soft
    s = trimmed
    s = re.sub(r"^\s*\d+[\s.)\-:]*", "", s)      # начальный номер "1." / "2)"
    s = re.sub(r"\d+", " ", s)                    # все цифры -> пробел
    s = "".join(ch if (unicodedata.category(ch).startswith("L") or ch in " '-") else " " for ch in s)
    words = [w for w in s.split()
             if (len(w) > 1 or w.isalpha()) and w.lower().rstrip(".") not in CMT_WORDS]
    return " ".join(words[:3])


def split_records(text: str) -> list[str]:
    parts = [l.strip() for l in text.splitlines() if l.strip()]
    if len(parts) <= 2 and re.search(r"\s{2,}", text):
        parts = [p.strip() for p in re.split(r"\s{2,}", text) if p.strip()]
    return parts


NAME_RE = r"[A-ЯЁa-яё][A-ЯЁa-яё'\-]+"


def is_header(line: str) -> bool:
    """Заголовок вида «Группа 1 Театральная Студия»."""
    return bool(re.match(r"^(?:группа|гр\.?)\s*\d+", line.strip(), re.I))


def header_group_name(line: str) -> str:
    """Из заголовка делает имя группы: «Группа 1 Театральная Студия» -> «1 Театральная студия»."""
    s = re.sub(r"^(?:группа|гр\.?)\s*", "", line.strip(), flags=re.I)
    words = s.split(None, 1)
    if not words:
        return "—"
    num = words[0]
    rest = words[1].strip() if len(words) > 1 else ""
    if rest:
        rest = rest.lower().capitalize()  # «Театральная Студия» -> «Театральная студия»
    return f"{num} {rest}".strip()


def has_tabs(text: str) -> bool:
    return "\t" in text


def grid_from_text(text: str, sep: str):
    lines = text.splitlines()
    n_cols = max((len(re.split(sep, l)) for l in lines), default=1)
    if n_cols < 2:
        return None
    grid = [re.split(sep, l) for l in lines]
    return [c + [""] * (n_cols - len(c)) for c in grid]


def parse_columns(text: str, sep: str = "\t"):
    """Разбор многоколоночного списка (как из Excel/таблицы):
    заголовки «Группа N ...» задают группу для ФИО своего столбца ниже.
    Возвращает список сырых записей 'ФИО | "<группа>"'.
    """
    grid = grid_from_text(text, sep)
    if not grid:
        return []

    col_groups: dict[int, str] = {}
    records: list[str] = []
    for cells in grid:
        # если строка — только заголовки групп, сопоставляем их со столбцами
        header_idx = [i for i, c in enumerate(cells) if is_header(c)]
        if header_idx and all(
            (not c.strip()) or is_header(c) or re.fullmatch(r"\d+", c.strip()) for c in cells
        ):
            for i in header_idx:
                col_groups[i] = header_group_name(cells[i])
            continue
        for i, cell in enumerate(cells):
            c = cell.strip()
            if not c or is_header(c):
                continue
            names = re.findall(rf"{NAME_RE}(?:\s+{NAME_RE})+", c)
            if not names:
                continue
            g = col_groups.get(i, "—")
            for nm in names:
                # кавычки-маркер, чтобы clean_name не вырезал слова из названия группы
                records.append(nm if g == "—" else f'{nm} | "{g}"')
    return records


def norm(s: str) -> str:
    s = s.lower().replace("ё", "е")
    return re.sub(r"[^a-zа-я]", "", s)


def align_columns(text: str) -> str:
    """Если табов нет, но есть заголовки «Группа N» в нескольких колонках —
    восстанавливаем сетку по позициям символов (моноширинная раскладка)."""
    lines = text.splitlines()
    hdr_i = next((i for i, l in enumerate(lines) if re.search(r"(?:Группа|Гр\.?)\s*\d", l)), None)
    if hdr_i is None:
        return ""

    def gap_starts(line: str):
        """Позиции первых слов после пробельных разрывов >=3."""
        res = []
        for m in re.finditer(r" {3,}\S+", line):
            res.append(m.end())  # позиция сразу после разрыва = начало следующего фрагмента
        return res

    # границы из строки заголовков: 0 + начала фрагментов после длинных разрывов
    bounds = [0] + gap_starts(lines[hdr_i])
    data_idx = [i for i, l in enumerate(lines)
                if i != hdr_i and l.strip() and not re.search(r"(?:Группа|Гр\.?)\s*\d", l)]

    def add_gaps(bs, line):
        out = list(bs)
        for p in gap_starts(line):
            if all(abs(p - b) > 5 for b in out):
                out.append(p)
        return sorted(set(out))

    # если границ мало — расширяем их по разрывам данных (кластеризация близких позиций)
    if len(bounds) < 3:
        pts = sorted({p for i in data_idx for p in gap_starts(lines[i])})
        clusters: list[list[int]] = []
        for p in pts:
            if clusters and p - clusters[-1][-1] <= 6:
                clusters[-1].append(p)
            else:
                clusters.append([p])
        strong = [sorted(c)[len(c) // 2] for c in clusters if len(c) >= 2]
        for p in strong:
            if all(abs(p - b) > 5 for b in bounds):
                bounds.append(p)
        bounds = sorted(set(bounds))

    # достраиваем границы по данным (разрывы, не попавшие ни в одну колонку)
    col_bounds = [list(bounds) for _ in range(len(lines))]
    for i in data_idx:
        col_bounds[i] = add_gaps(bounds, lines[i])

    out_lines = []
    for i, l in enumerate(lines):
        bs = col_bounds[i]
        cells = []
        for j, b in enumerate(bs):
            end = bs[j + 1] if j + 1 < len(bs) else len(l)
            cells.append(l[b:end].strip() if b < len(l) else "")
        out_lines.append("\t".join(cells))
    # оставляем только если получилась таблица с ФИО
    probe = parse_columns("\n".join(out_lines))
    return "\n".join(out_lines) if probe else ""


def parse(text: str, dedup: bool = True):
    """Возвращает (rows, total_records, unique_count, groups_counter)."""
    recs = []
    col_text = text if has_tabs(text) else align_columns(text)
    col_records = parse_columns(col_text) if col_text else []
    raw_list = col_records if col_records else split_records(text)
    for raw in raw_list:
        name = clean_name(raw)
        if not name:
            continue
        recs.append({"name": name, "group": extract_group(raw)})

    uniq = len({norm(r["name"]) for r in recs})

    if dedup:
        seen, rows = {}, []
        for r in recs:
            k = norm(r["name"])
            if k in seen:
                e = rows[seen[k]]
                e["count"] += 1
                if e["group"] == "—" and r["group"] != "—":
                    e["group"] = r["group"]
            else:
                seen[k] = len(rows)
                rows.append({**r, "count": 1})
    else:
        rows = [{**r, "count": 1} for r in recs]

    rows.sort(key=lambda r: r["name"].casefold())
    groups = {}
    for r in rows:
        groups[r["group"]] = groups.get(r["group"], 0) + r["count"]
    return rows, len(recs), uniq, groups


def get_clipboard() -> str:
    try:
        import tkinter as tk
        root = tk.Tk(); root.withdraw()
        data = root.clipboard_get(); root.destroy()
        return data
    except Exception:
        pass
    import subprocess, shutil
    for cmd in (["xclip", "-selection", "clipboard", "-o"],
                ["xsel", "-b"], ["pbpaste"]):
        if shutil.which(cmd[0]):
            try:
                return subprocess.run(cmd, capture_output=True, text=True).stdout
            except Exception:
                pass
    return ""


# ---------- CLI ----------
def run_cli(text: str):
    rows, total, uniq, groups = parse(text)
    w = max((len(r["name"]) for r in rows), default=10)
    print(f"{'№':>3}  {'Фамилия Имя'.ljust(w)}  Группа")
    print("-" * (6 + w + 10))
    for i, r in enumerate(rows, 1):
        dup = f" ×{r['count']}" if r["count"] > 1 else ""
        print(f"{i:>3}  {(r['name'] + dup).ljust(w)}  {r['group']}")
    print("-" * (6 + w + 10))
    print(f"Записей: {total} | Уникальных людей: {uniq}")
    for g, c in sorted(groups.items()):
        print(f"  Группа {g}: {c}")


# ---------- GUI (tkinter) ----------
def run_gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("Сортировка ФИО по алфавиту с группами")
    root.geometry("980x640")

    style = ttk.Style(root); style.theme_use("clam")
    root.configure(bg="#0f172a")

    frm = ttk.Frame(root, padding=10); frm.pack(fill="both", expand=True)

    txt_in = tk.Text(frm, height=12, width=60, bg="#0b1220", fg="#e2e8f0",
                     insertbackground="#e2e8f0", relief="flat")
    txt_in.pack(side="left", fill="both", expand=True, padx=(0, 8))

    right = ttk.Frame(frm); right.pack(side="left", fill="both", expand=True)

    cols = ("num", "name", "group")
    tree = ttk.Treeview(right, columns=cols, show="headings", height=14)
    for c, t, w in zip(cols, ("№", "Фамилия Имя", "Комментарий / Группа"), (40, 260, 160)):
        tree.heading(c, text=t); tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True)

    status = tk.Label(root, text="Вставьте текст (Ctrl+V) или нажмите «Из буфера»",
                      fg="#94a3b8", bg="#0f172a", anchor="w", padx=12)
    status.pack(fill="x")

    bar = ttk.Frame(root); bar.pack(fill="x", padx=10, pady=6)
    dedup_var = tk.BooleanVar(value=True)

    def refresh(*_):
        text = txt_in.get("1.0", "end").strip()
        for i in tree.get_children():
            tree.delete(i)
        if not text:
            status.config(text="Пусто"); return
        rows, total, uniq, groups = parse(text, dedup_var.get())
        if not rows:
            status.config(text="Записи не распознаны"); return
        for i, r in enumerate(rows, 1):
            dup = f" ×{r['count']}" if r["count"] > 1 else ""
            tree.insert("", "end", values=(i, r["name"] + dup, r["group"]))
        gs = ", ".join(f"{g}: {c}" for g, c in sorted(groups.items()))
        status.config(text=f"Записей: {total} | Уникальных людей: {uniq} | {gs}")

    def paste_buffer():
        data = get_clipboard()
        if data:
            txt_in.delete("1.0", "end"); txt_in.insert("1.0", data); refresh()
        else:
            messagebox.showwarning("Буфер", "Не удалось прочитать буфер обмена.")

    def open_file():
        p = filedialog.askopenfilename(filetypes=[("Текст", "*.txt"), ("Все", "*.*")])
        if p:
            with open(p, encoding="utf-8", errors="replace") as f:
                txt_in.delete("1.0", "end"); txt_in.insert("1.0", f.read())
            refresh()

    def copy_out():
        lines = [f"{i}. {r['name']}" + ("" if r["group"] == "—" else f" — {r['group']}")
                 for i, r in enumerate(parse(txt_in.get("1.0", "end").strip(),
                                             dedup_var.get())[0], 1)]
        root.clipboard_clear(); root.clipboard_append("\n".join(lines))
        status.config(text="Таблица скопирована в буфер обмена")

    ttk.Button(bar, text="📥 Из буфера обмена", command=paste_buffer).pack(side="left", padx=4)
    ttk.Button(bar, text="📂 Из файла", command=open_file).pack(side="left", padx=4)
    ttk.Button(bar, text="✨ Отсортировать", command=refresh).pack(side="left", padx=4)
    ttk.Button(bar, text="📄 Копировать результат", command=copy_out).pack(side="left", padx=4)
    ttk.Checkbutton(bar, text="объединять дубликаты", variable=dedup_var,
                    command=refresh).pack(side="left", padx=10)

    txt_in.bind("<KeyRelease>", refresh)
    root.mainloop()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--file" in args:
        path = args[args.index("--file") + 1]
        with open(path, encoding="utf-8", errors="replace") as f:
            run_cli(f.read())
    elif "--cli" in args or not sys.stdout.isatty():
        text = sys.stdin.read() if not sys.stdin.isatty() else get_clipboard()
        run_cli(text)
    else:
        try:
            run_gui()
        except ImportError:
            print("tkinter недоступен — запуск в режиме CLI (буфер обмена):")
            run_cli(get_clipboard())
