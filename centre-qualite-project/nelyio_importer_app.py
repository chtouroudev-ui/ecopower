"""NELYIO V60 local Importer.

Heavy SIMPLIFY2/group imports are explicit operator work and never execute in the
Web/API process.  This Tk application uses the existing verified import pipeline
and keeps the UI responsive by running one import at a time in a worker thread.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import threading
import time
import traceback

BASE = Path(__file__).resolve().parent


def _lower_process_priority():
    """Optional low priority. V60.2 defaults to normal because snapshot mode
    keeps Web readers on the previous stable reference during the import."""
    mode=os.environ.get("NELYIO_IMPORT_PRIORITY","normal").strip().lower()
    if mode not in {"low","below_normal","background"}:
        return
    if os.name == "nt":
        try:
            import ctypes
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS)
        except Exception:
            pass
    else:
        try:
            os.nice(5)
        except Exception:
            pass


def _format_result(result):
    if not isinstance(result, dict):
        return str(result)
    keys = ("status", "message", "import_id", "rows", "calls", "days", "duplicates", "snapshot_mode")
    lines=[f"{k}: {result.get(k)}" for k in keys if k in result]
    perf=result.get("performance") or {}
    if perf:
        lines.append(f"temps total: {perf.get('total_seconds','?')} s")
        core=perf.get('core_seconds') or {}
        if core:
            lines.append('détail import principal: '+', '.join(f"{k}={v}s" for k,v in core.items()))
        steps=perf.get('steps_seconds') or {}
        if steps:
            lines.append('étapes: '+', '.join(f"{k}={v}s" for k,v in steps.items()))
        for name,value in (perf.get("steps_seconds") or {}).items():
            lines.append(f"  - {name}: {value} s")
    quality=result.get("quality_refresh") or result.get("quality_import") or {}
    if isinstance(quality, dict) and quality:
        lines.append("Qualité / groupes :")
        lines.append(f"  - mise à jour: {bool(quality.get('updated'))}")
        if quality.get('source_file'): lines.append(f"  - source: {quality.get('source_file')}")
        if quality.get('accepted_scopes') is not None: lines.append(f"  - scopes: {quality.get('accepted_scopes')}")
        if quality.get('queue_assignments') is not None: lines.append(f"  - affectations agent/file: {quality.get('queue_assignments')}")
        if quality.get('agents') is not None: lines.append(f"  - agents: {quality.get('agents')}")
        if quality.get('reason'): lines.append(f"  - résultat: {quality.get('reason')}")
        if quality.get('message'): lines.append(f"  - message: {quality.get('message')}")
    return "\n".join(lines)


def _import_file(path: Path):
    """Import one operator-selected source.

    Important V60.4 repair: a completed/duplicate daily ZIP can return before
    import_workflow replays the Quality enrichment step.  Group membership
    depends on Agents.csv -> Queues, so we explicitly refresh that small
    configuration snapshot from every selected ZIP/CSV after the durable daily
    import.  This makes re-importing an already-known ZIP self-heal groups.
    """
    raw = path.read_bytes()
    name = path.name
    low = name.lower()
    if low in ("group", "group.har") or low.endswith(".har"):
        from group_har_import import ingest
        result = ingest(raw)
        try:
            from quality_scope import invalidate_quality_scope_cache
            invalidate_quality_scope_cache()
        except Exception:
            pass
        return result

    # Stand-alone configuration sources (Agents.csv, AgentQueues, Lines, etc.)
    # do not contain Stats.AGENT and therefore must bypass the daily-statistics
    # importer.  quality_service already validates the actual CSV structure.
    if low.endswith('.csv') and not low.endswith('.stats.agent.csv'):
        from quality_service import update_quality_from_export
        result = update_quality_from_export(raw, name)
        try:
            from quality_scope import invalidate_quality_scope_cache
            invalidate_quality_scope_cache()
        except Exception:
            pass
        return dict(status='completed' if result.get('updated') else 'review',
                    message=result.get('message') or ('Configuration Qualité importée.' if result.get('updated') else 'Configuration non reconnue.'),
                    quality_refresh=result)

    if not low.endswith((".zip", ".stats.agent.csv")):
        raise ValueError("Choisissez un ZIP SIMPLIFY2, un CSV de configuration (Agents.csv), Stats.AGENT.csv ou group.har.")

    from auto_import import automatic_import_offset
    from export_import import import_export
    offset = automatic_import_offset(name)
    result = import_export(raw, name, offset, "LOCAL_IMPORTER_V60")

    # Always replay the lightweight configuration extraction, even when
    # import_export reports duplicate=True.  This is the key self-heal for the
    # 'Projection des groupes incomplète' warning.
    try:
        from quality_service import update_quality_from_export
        quality = update_quality_from_export(raw, name)
        result['quality_refresh'] = quality
    except Exception as exc:
        result['quality_refresh'] = dict(updated=False, reason='quality_refresh_error', message=str(exc))
    try:
        from quality_scope import invalidate_quality_scope_cache
        invalidate_quality_scope_cache()
    except Exception:
        pass
    return result


def _process_pending():
    from import_workflow import retry_pending_jobs, workflow_status
    total = 0
    for _ in range(100):
        status = workflow_status()
        pending = sum(int(status.get("job_counts", {}).get(k, 0)) for k in ("queued", "partial", "running"))
        if not pending:
            break
        retry_pending_jobs(limit=1)
        total += 1
        time.sleep(0.05)
    return {"status": "completed", "processed_batches": total, "workflow": workflow_status()}


def main():
    _lower_process_priority()
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    events = queue.Queue()
    busy = {"value": False}

    root = tk.Tk()
    root.title("NELYIO V60 - Importer local")
    root.geometry("760x520")
    root.minsize(680, 460)

    outer = ttk.Frame(root, padding=18)
    outer.pack(fill="both", expand=True)
    ttk.Label(outer, text="NELYIO Importer", font=("Segoe UI", 18, "bold")).pack(anchor="w")
    ttk.Label(
        outer,
        text="Import multiple séparé du Web. Sélectionnez plusieurs ZIP/CSV/HAR ; ils sont traités en file sûre sans bloquer le site.",
        wraplength=700,
    ).pack(anchor="w", pady=(4, 14))

    path_var = tk.StringVar()
    selected_paths = []
    row = ttk.Frame(outer)
    row.pack(fill="x")
    entry = ttk.Entry(row, textvariable=path_var, state="readonly")
    entry.pack(side="left", fill="x", expand=True)

    def choose():
        paths = filedialog.askopenfilenames(
            title="Choisir un ou plusieurs exports NELYIO",
            filetypes=[
                ("Exports NELYIO", "*.zip *.csv *.har"),
                ("ZIP SIMPLIFY2", "*.zip"),
                ("CSV configuration / Agents", "*.csv"),
                ("Group HAR", "*.har"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if paths:
            selected_paths[:] = [Path(x) for x in paths]
            if len(selected_paths) == 1:
                path_var.set(str(selected_paths[0]))
            else:
                path_var.set(f"{len(selected_paths)} fichiers sélectionnés")

    ttk.Button(row, text="Parcourir...", command=choose).pack(side="left", padx=(8, 0))

    progress = ttk.Progressbar(outer, mode="indeterminate")
    progress.pack(fill="x", pady=(14, 8))
    status_var = tk.StringVar(value="Prêt. Aucun import ne tourne en arrière-plan.")
    ttk.Label(outer, textvariable=status_var).pack(anchor="w")

    output = tk.Text(outer, height=16, wrap="word", font=("Consolas", 10))
    output.pack(fill="both", expand=True, pady=(10, 10))
    output.insert("end", "V60 : l'import est volontaire et indépendant du Web.\n")
    output.configure(state="disabled")

    actions = ttk.Frame(outer)
    actions.pack(fill="x")

    def write(text):
        output.configure(state="normal")
        output.insert("end", str(text).rstrip() + "\n")
        output.see("end")
        output.configure(state="disabled")

    def finish(ok, payload):
        busy["value"] = False
        progress.stop()
        for widget in (import_btn, pending_btn):
            widget.configure(state="normal")
        if ok:
            status_var.set("Import terminé.")
            write(_format_result(payload) if isinstance(payload, dict) else payload)
        else:
            status_var.set("Import en erreur. La source n'a pas été supprimée.")
            write(payload)

    def poll_events():
        try:
            while True:
                kind, payload = events.get_nowait()
                if kind == "done": finish(True, payload)
                elif kind == "error": finish(False, payload)
                else: write(payload)
        except queue.Empty:
            pass
        root.after(150, poll_events)

    def start_job(fn, label):
        if busy["value"]:
            return
        busy["value"] = True
        status_var.set(label)
        progress.start(10)
        import_btn.configure(state="disabled")
        pending_btn.configure(state="disabled")

        def work():
            try:
                try:
                    import service_state
                    service_state.beat("import", state="running", detail={"mode": "manual-v60", "phase": label})
                except Exception:
                    pass
                result = fn()
                events.put(("done", result))
            except Exception as exc:
                events.put(("error", f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"))
            finally:
                try:
                    import service_state
                    service_state.stop("import", {"mode": "manual-v60"})
                except Exception:
                    pass

        threading.Thread(target=work, name="nelyio-local-import", daemon=True).start()

    def import_selected():
        paths = list(selected_paths)
        # Backward compatibility if a path was typed/set by an older launcher.
        if not paths:
            raw = path_var.get().strip()
            if raw and not raw.endswith(" fichiers sélectionnés"):
                paths = [Path(raw)]
        if not paths:
            messagebox.showwarning("NELYIO Importer", "Choisissez un ou plusieurs fichiers.")
            return
        missing=[str(p) for p in paths if not p.is_file()]
        if missing:
            messagebox.showerror("NELYIO Importer", "Fichier(s) introuvable(s):\n" + "\n".join(missing[:5]))
            return
        for p in paths:
            write(f"En attente: {p.name}")

        def import_many():
            # Imports are intentionally sequential inside one worker: the Nelyio
            # import pipeline uses a global write lock and concurrent writes would
            # be slower/unsafe. The operator can nevertheless select all files in
            # one action and the UI remains responsive.
            summary=[]
            total=len(paths)
            for idx,path in enumerate(paths,1):
                events.put(("log", f"[{idx}/{total}] Import: {path.name}"))
                try:
                    result=_import_file(path)
                    summary.append(dict(file=path.name,ok=True,result=result))
                    events.put(("log", _format_result(result)))
                except Exception as exc:
                    summary.append(dict(file=path.name,ok=False,error=f"{type(exc).__name__}: {exc}"))
                    events.put(("log", f"ERREUR {path.name}: {type(exc).__name__}: {exc}"))
            ok=sum(1 for x in summary if x['ok'])
            failed=total-ok
            return {"status":"completed" if not failed else "partial",
                    "message":f"Import multiple terminé : {ok}/{total} réussi(s), {failed} échec(s).",
                    "files":summary}

        start_job(import_many, f"Import multiple en cours : 0/{len(paths)} - le Web reste disponible...")

    def process_pending():
        write("Traitement de la file d'imports déjà en attente...")
        start_job(_process_pending, "Traitement de la file en attente...")

    import_btn = ttk.Button(actions, text="Importer la sélection", command=import_selected)
    import_btn.pack(side="left")
    pending_btn = ttk.Button(actions, text="Traiter les imports en attente", command=process_pending)
    pending_btn.pack(side="left", padx=(8, 0))
    ttk.Button(actions, text="Fermer", command=root.destroy).pack(side="right")

    ttk.Label(
        outer,
        text="V60.3 : priorité normale par défaut. Définir NELYIO_IMPORT_PRIORITY=low seulement si le serveur manque de CPU.",
        wraplength=700,
    ).pack(anchor="w", pady=(12, 0))

    root.after(150, poll_events)
    root.mainloop()


if __name__ == "__main__":
    main()
