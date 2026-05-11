"""
Lembretes de medicamento — Windows.
Interface gráfica (criar/editar/excluir/listar) + notificações + bandeja do sistema.
Executável: PyInstaller; config.json junto ao .exe.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import Menu, messagebox, ttk

import pystray
import tkinter as tk
from PIL import Image, ImageDraw
from winotify import Notification, audio


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_PATH = application_directory() / "config.json"


@dataclass(frozen=True)
class Reminder:
    medication_name: str
    time_label: str
    hour: int
    minute: int


def parse_hhmm(s: str) -> tuple[int, int] | None:
    s = str(s).strip()
    parts = s.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h, m


def minutes_between(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Diferença em minutos de a para b no mesmo dia (b depois de a)."""
    ma = a[0] * 60 + a[1]
    mb = b[0] * 60 + b[1]
    d = mb - ma
    if d <= 0:
        d += 24 * 60
    return d


def migrate_legacy_medication(med: dict) -> dict:
    """Converte entrada antiga com 'times' para o novo formato."""
    if "first_time" in med:
        return normalize_medication_dict(med, interval_as_minutes=False)
    times_raw = med.get("times") or []
    parsed: list[tuple[int, int]] = []
    for t in times_raw:
        p = parse_hhmm(t)
        if p:
            parsed.append(p)
    if not parsed:
        return normalize_medication_dict(
            {
                "id": med.get("id") or str(uuid.uuid4()),
                "name": med.get("name", "Medicamento"),
                "first_time": "09:00",
                "interval_hours": 8.0,
                "doses_per_day": 1,
            },
            interval_as_minutes=False,
        )
    parsed.sort(key=lambda x: x[0] * 60 + x[1])
    doses = len(parsed)
    first = parsed[0]
    if doses == 1:
        interval = 24.0
    else:
        deltas = [minutes_between(parsed[i], parsed[i + 1]) for i in range(doses - 1)]
        interval = min(deltas) / 60.0
    return normalize_medication_dict(
        {
            "id": med.get("id") or str(uuid.uuid4()),
            "name": med.get("name", "Medicamento"),
            "first_time": f"{first[0]:02d}:{first[1]:02d}",
            "interval_hours": float(interval),
            "doses_per_day": doses,
        },
        interval_as_minutes=False,
    )


def normalize_medication_dict(
    med: dict, *, interval_as_minutes: bool = False
) -> dict:
    mid = med.get("id") or str(uuid.uuid4())
    name = str(med.get("name", "")).strip() or "Medicamento"
    ft = parse_hhmm(med.get("first_time", "09:00"))
    if not ft:
        ft = (9, 0)
    try:
        interval = float(med.get("interval_hours", 8))
    except (TypeError, ValueError):
        interval = 8.0
    try:
        doses = int(med.get("doses_per_day", 1))
    except (TypeError, ValueError):
        doses = 1
    if interval_as_minutes:
        interval = max(1.0, min(interval, 24 * 60.0))
    else:
        interval = max(0.25, min(interval, 72.0))
    doses = max(1, min(doses, 48))
    return {
        "id": str(mid),
        "name": name,
        "first_time": f"{ft[0]:02d}:{ft[1]:02d}",
        "interval_hours": interval,
        "doses_per_day": doses,
    }


def load_medications(path: Path) -> tuple[list[dict], int, bool, bool]:
    """Devolve (medicamentos, check_interval_seconds, migrou_legacy, debug_minutos)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    check = int(raw.get("check_interval_seconds", 20))
    check = max(5, min(check, 300))
    debug_minutes = bool(raw.get("debug_interval_in_minutes", False))
    meds_in = raw.get("medications", [])
    migrated = False
    out: list[dict] = []
    for med in meds_in:
        if "first_time" not in med and med.get("times"):
            migrated = True
        out.append(migrate_legacy_medication(med))
    return out, check, migrated, debug_minutes


def medications_to_reminders(
    medications: list[dict], *, debug_interval_in_minutes: bool = False
) -> list[Reminder]:
    reminders: list[Reminder] = []
    for med in medications:
        name = str(med.get("name", "Medicamento")).strip() or "Medicamento"
        m = normalize_medication_dict(
            med, interval_as_minutes=debug_interval_in_minutes
        )
        ft = parse_hhmm(m["first_time"])
        if not ft:
            continue
        interval = float(m["interval_hours"])
        n = int(m["doses_per_day"])
        base = datetime(2000, 1, 1, ft[0], ft[1])
        for i in range(n):
            if debug_interval_in_minutes:
                t = base + timedelta(minutes=interval * i)
            else:
                t = base + timedelta(hours=interval * i)
            reminders.append(
                Reminder(
                    medication_name=name,
                    time_label=f"{t.hour:02d}:{t.minute:02d}",
                    hour=t.hour,
                    minute=t.minute,
                )
            )
    return reminders


def load_reminders_from_disk(
    path: Path,
) -> tuple[list[Reminder], int, bool]:
    medications, check, _, debug = load_medications(path)
    return (
        medications_to_reminders(medications, debug_interval_in_minutes=debug),
        check,
        debug,
    )


def save_config(
    path: Path,
    medications: list[dict],
    check_interval: int,
    *,
    debug_interval_in_minutes: bool = False,
) -> None:
    check_interval = max(5, min(int(check_interval), 300))
    data = {
        "check_interval_seconds": check_interval,
        "debug_interval_in_minutes": debug_interval_in_minutes,
        "medications": [
            normalize_medication_dict(
                m, interval_as_minutes=debug_interval_in_minutes
            )
            for m in medications
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def default_config(path: Path) -> None:
    save_config(
        path,
        [
            normalize_medication_dict(
                {
                    "id": str(uuid.uuid4()),
                    "name": "Exemplo — substitua pelo seu remédio",
                    "first_time": "08:00",
                    "interval_hours": 6.0,
                    "doses_per_day": 3,
                },
                interval_as_minutes=False,
            )
        ],
        20,
        debug_interval_in_minutes=False,
    )


def schedule_preview(med: dict, *, debug_interval_in_minutes: bool) -> str:
    m = normalize_medication_dict(
        med, interval_as_minutes=debug_interval_in_minutes
    )
    r = medications_to_reminders(
        [m], debug_interval_in_minutes=debug_interval_in_minutes
    )
    return ", ".join(x.time_label for x in r)


def create_tray_icon(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = size // 8
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(33, 150, 243, 255),
        outline=(25, 118, 210, 255),
        width=max(1, size // 32),
    )
    cx, cy = size // 2, size // 2
    w, h = size // 3, size // 5
    draw.rounded_rectangle(
        [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2],
        radius=h // 3,
        fill=(255, 255, 255, 230),
    )
    return img


def notify_medication(
    name: str, time_label: str, *, debug_interval_in_minutes: bool = False
) -> None:
    title = (
        "[Teste — intervalo em minutos] Hora do remédio"
        if debug_interval_in_minutes
        else "Hora de tomar o medicamento"
    )
    toast = Notification(
        app_id="Lembretes de medicamento",
        title=title,
        msg=f"{name}\nHorário: {time_label}",
        duration="long",
    )
    toast.set_audio(audio.Default, loop=False)
    toast.show()


def reminder_loop(stop: threading.Event, path: Path) -> None:
    fired_today: set[tuple[str, str, str]] = set()
    last_date: date | None = None

    while not stop.is_set():
        try:
            reminders, interval, debug_min = load_reminders_from_disk(path)
        except (OSError, json.JSONDecodeError):
            time.sleep(30)
            continue

        now = datetime.now()
        if last_date != now.date():
            fired_today.clear()
            last_date = now.date()

        for r in reminders:
            if now.hour == r.hour and now.minute == r.minute:
                key = (now.date().isoformat(), r.medication_name, r.time_label)
                if key not in fired_today:
                    notify_medication(
                        r.medication_name,
                        r.time_label,
                        debug_interval_in_minutes=debug_min,
                    )
                    fired_today.add(key)

        stop.wait(interval)


class MedicamentoApp:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._icon: pystray.Icon | None = None
        self._tray_ready = threading.Event()

        if not CONFIG_PATH.is_file():
            default_config(CONFIG_PATH)

        self.medications: list[dict] = []
        self.check_interval = 20
        self.debug_interval_in_minutes = False
        self._load_data()

        self.root = tk.Tk()
        self._update_window_title()
        self.root.minsize(720, 360)
        self.root.geometry("860x400")
        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)

        self._build_menu()
        self._build_main()

        self._reminder_thread = threading.Thread(
            target=reminder_loop,
            args=(self._stop, CONFIG_PATH),
            daemon=True,
            name="reminder-loop",
        )
        self._reminder_thread.start()

        threading.Thread(target=self._run_tray, daemon=True).start()

    def _load_data(self) -> None:
        try:
            (
                self.medications,
                self.check_interval,
                migrated,
                self.debug_interval_in_minutes,
            ) = load_medications(CONFIG_PATH)
            if migrated:
                save_config(
                    CONFIG_PATH,
                    self.medications,
                    self.check_interval,
                    debug_interval_in_minutes=self.debug_interval_in_minutes,
                )
        except (OSError, json.JSONDecodeError):
            self.medications = []
            self.check_interval = 20
            self.debug_interval_in_minutes = False

    def _update_window_title(self) -> None:
        base = "Lembretes de medicamento"
        if self.debug_interval_in_minutes:
            base += " — [DEBUG: intervalo em minutos]"
        self.root.title(base)

    def _build_menu(self) -> None:
        menubar = Menu(self.root)
        m_file = Menu(menubar, tearoff=0)
        m_file.add_command(label="Ocultar para a bandeja", command=self._hide_window)
        m_file.add_separator()
        m_file.add_command(label="Sair", command=self._quit_app)
        menubar.add_cascade(label="Ficheiro", menu=m_file)
        self.root.config(menu=menubar)

    def _build_main(self) -> None:
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill=tk.BOTH, expand=True)

        bar = ttk.Frame(outer)
        bar.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(bar, text="Novo", command=self._new_med).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="Editar", command=self._edit_med).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Button(bar, text="Excluir", command=self._delete_med).pack(
            side=tk.LEFT, padx=(0, 6)
        )
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(bar, text="Verificar relógio a cada (s):").pack(side=tk.LEFT)
        self._spin_check = tk.Spinbox(
            bar,
            from_=5,
            to=300,
            width=6,
            command=self._persist_check_interval,
        )
        self._spin_check.delete(0, tk.END)
        self._spin_check.insert(0, str(self.check_interval))
        self._spin_check.pack(side=tk.LEFT, padx=4)
        self._spin_check.bind("<FocusOut>", lambda e: self._persist_check_interval())
        self._spin_check.bind("<Return>", lambda e: self._persist_check_interval())

        self._var_debug = tk.BooleanVar(value=self.debug_interval_in_minutes)
        dbg = ttk.Checkbutton(
            bar,
            text="Debug: intervalo em minutos (testes)",
            variable=self._var_debug,
            command=self._on_debug_toggle,
        )
        dbg.pack(side=tk.LEFT, padx=(16, 0))

        cols = ("name", "first", "interval", "doses", "preview")
        self.tree = ttk.Treeview(
            outer,
            columns=cols,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("name", text="Medicamento")
        self.tree.heading("first", text="1ª hora do dia")
        self._set_interval_column_heading()
        self.tree.heading("doses", text="Doses / dia")
        self.tree.heading("preview", text="Horários gerados")
        self.tree.column("name", width=180)
        self.tree.column("first", width=100, anchor=tk.CENTER)
        self.tree.column("interval", width=90, anchor=tk.CENTER)
        self.tree.column("doses", width=90, anchor=tk.CENTER)
        self.tree.column("preview", width=320)
        sy = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sy.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sy.pack(side=tk.RIGHT, fill=tk.Y)

        self._refresh_tree()

    def _set_interval_column_heading(self) -> None:
        self.tree.heading(
            "interval",
            text=(
                "Intervalo (min)"
                if self.debug_interval_in_minutes
                else "Intervalo (h)"
            ),
        )

    def _on_debug_toggle(self) -> None:
        self.debug_interval_in_minutes = bool(self._var_debug.get())
        self._update_window_title()
        self._set_interval_column_heading()
        self._save_all()
        self._refresh_tree()

    def _selected_id(self) -> str | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return sel[0]

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for med in self.medications:
            m = normalize_medication_dict(
                med, interval_as_minutes=self.debug_interval_in_minutes
            )
            iv = m["interval_hours"]
            if iv % 1:
                interval_str = f"{iv:.2g}".replace(".", ",")
            else:
                interval_str = str(int(iv))
            self.tree.insert(
                "",
                tk.END,
                iid=m["id"],
                values=(
                    m["name"],
                    m["first_time"],
                    interval_str,
                    m["doses_per_day"],
                    schedule_preview(
                        m, debug_interval_in_minutes=self.debug_interval_in_minutes
                    ),
                ),
            )

    def _persist_check_interval(self) -> None:
        try:
            v = int(self._spin_check.get())
            self.check_interval = max(5, min(v, 300))
        except ValueError:
            self.check_interval = 20
        self._spin_check.delete(0, tk.END)
        self._spin_check.insert(0, str(self.check_interval))
        save_config(
            CONFIG_PATH,
            self.medications,
            self.check_interval,
            debug_interval_in_minutes=self.debug_interval_in_minutes,
        )

    def _save_all(self) -> None:
        save_config(
            CONFIG_PATH,
            self.medications,
            self.check_interval,
            debug_interval_in_minutes=self.debug_interval_in_minutes,
        )

    def _med_dialog(self, title: str, initial: dict | None) -> dict | None:
        dlg = tk.Toplevel(self.root)
        dlg.title(title)
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        data = normalize_medication_dict(
            initial or {"name": ""},
            interval_as_minutes=self.debug_interval_in_minutes,
        )
        result: dict | None = None
        use_min = self.debug_interval_in_minutes

        f = ttk.Frame(dlg, padding=12)
        f.pack(fill=tk.BOTH)

        ttk.Label(f, text="Nome do medicamento:").grid(row=0, column=0, sticky=tk.W)
        e_name = ttk.Entry(f, width=40)
        e_name.insert(0, data["name"])
        e_name.grid(row=0, column=1, columnspan=3, sticky=tk.EW, pady=4)

        ttk.Label(f, text="Primeira toma (HH:MM):").grid(row=1, column=0, sticky=tk.W)
        e_time = ttk.Entry(f, width=10)
        e_time.insert(0, data["first_time"])
        e_time.grid(row=1, column=1, sticky=tk.W, pady=4)

        lbl_int = ttk.Label(
            f,
            text=("Intervalo (minutos):" if use_min else "Intervalo (horas):"),
        )
        lbl_int.grid(row=2, column=0, sticky=tk.W)
        e_int = ttk.Entry(f, width=10)
        e_int.insert(0, str(data["interval_hours"]).replace(".", ","))
        e_int.grid(row=2, column=1, sticky=tk.W, pady=4)

        ttk.Label(f, text="Doses por dia:").grid(row=3, column=0, sticky=tk.W)
        sp_doses = tk.Spinbox(f, from_=1, to=48, width=8)
        sp_doses.delete(0, tk.END)
        sp_doses.insert(0, str(data["doses_per_day"]))
        sp_doses.grid(row=3, column=1, sticky=tk.W, pady=4)

        preview_lbl = ttk.Label(f, text="", wraplength=420)
        preview_lbl.grid(row=4, column=0, columnspan=4, sticky=tk.W, pady=8)

        def update_preview() -> None:
            try:
                nh = float(e_int.get().replace(",", "."))
            except ValueError:
                nh = 1.0 if use_min else 8.0
            try:
                nd = int(sp_doses.get())
            except ValueError:
                nd = 1
            pm = {
                "name": e_name.get(),
                "first_time": e_time.get(),
                "interval_hours": nh,
                "doses_per_day": nd,
            }
            preview_lbl.config(
                text="Horários: "
                + schedule_preview(
                    pm, debug_interval_in_minutes=use_min
                )
            )

        def on_ok() -> None:
            nonlocal result
            name = e_name.get().strip()
            if not name:
                messagebox.showerror("Validação", "Indique o nome do medicamento.", parent=dlg)
                return
            if not parse_hhmm(e_time.get()):
                messagebox.showerror(
                    "Validação",
                    "Hora inválida. Use HH:MM (ex.: 08:30).",
                    parent=dlg,
                )
                return
            try:
                ih = float(e_int.get().replace(",", "."))
            except ValueError:
                messagebox.showerror(
                    "Validação",
                    (
                        "Intervalo em minutos inválido (ex.: 2 ou 1,5)."
                        if use_min
                        else "Intervalo em horas inválido (ex.: 4 ou 4,5)."
                    ),
                    parent=dlg,
                )
                return
            if use_min:
                if ih < 1:
                    messagebox.showerror(
                        "Validação",
                        "No modo debug, o intervalo mínimo é 1 minuto.",
                        parent=dlg,
                    )
                    return
            elif ih <= 0:
                messagebox.showerror(
                    "Validação", "O intervalo deve ser maior que zero.", parent=dlg
                )
                return
            try:
                doses = int(sp_doses.get())
            except ValueError:
                messagebox.showerror("Validação", "Doses por dia inválido.", parent=dlg)
                return
            result = normalize_medication_dict(
                {
                    "id": data["id"],
                    "name": name,
                    "first_time": e_time.get().strip(),
                    "interval_hours": ih,
                    "doses_per_day": doses,
                },
                interval_as_minutes=use_min,
            )
            dlg.destroy()

        def on_cancel() -> None:
            dlg.destroy()

        bf = ttk.Frame(f)
        bf.grid(row=5, column=0, columnspan=4, pady=12)
        ttk.Button(bf, text="OK", command=on_ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="Cancelar", command=on_cancel).pack(side=tk.LEFT, padx=4)

        for w in (e_name, e_time, e_int, sp_doses):
            w.bind("<KeyRelease>", lambda e: update_preview())
        sp_doses.configure(command=update_preview)
        update_preview()

        dlg.wait_window()
        return result

    def _new_med(self) -> None:
        new = self._med_dialog("Novo medicamento", None)
        if new:
            new["id"] = str(uuid.uuid4())
            self.medications.append(new)
            self._save_all()
            self._refresh_tree()

    def _edit_med(self) -> None:
        mid = self._selected_id()
        if not mid:
            messagebox.showinfo("Editar", "Selecione um medicamento na lista.")
            return
        idx = next((i for i, m in enumerate(self.medications) if m.get("id") == mid), -1)
        if idx < 0:
            return
        edited = self._med_dialog("Editar medicamento", self.medications[idx])
        if edited:
            self.medications[idx] = edited
            self._save_all()
            self._refresh_tree()

    def _delete_med(self) -> None:
        mid = self._selected_id()
        if not mid:
            messagebox.showinfo("Excluir", "Selecione um medicamento na lista.")
            return
        if not messagebox.askyesno(
            "Confirmar",
            "Excluir este medicamento da lista de lembretes?",
            parent=self.root,
        ):
            return
        self.medications = [m for m in self.medications if m.get("id") != mid]
        self._save_all()
        self._refresh_tree()

    def _hide_window(self) -> None:
        self.root.withdraw()

    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit_app(self) -> None:
        self._stop.set()
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                pass
        self.root.quit()
        self.root.destroy()

    def _run_tray(self) -> None:
        icon_image = create_tray_icon()

        def show(_icon, _item) -> None:
            self.root.after(0, self._show_window)

        def hide(_icon, _item) -> None:
            self.root.after(0, self._hide_window)

        def quit_app(_icon, _item) -> None:
            self.root.after(0, self._quit_app)

        menu = pystray.Menu(
            pystray.MenuItem("Abrir", show),
            pystray.MenuItem("Ocultar", hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", quit_app),
        )
        self._icon = pystray.Icon(
            "medicamento_app",
            icon_image,
            "Lembretes de medicamento",
            menu,
        )
        self._tray_ready.set()
        self._icon.run()

    def run(self) -> None:
        self._tray_ready.wait(timeout=5.0)
        self.root.mainloop()


def main() -> None:
    MedicamentoApp().run()


if __name__ == "__main__":
    main()
