from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .scanner import ScannerError, get_interface_inventory, resolve_capture_interface, scan_on_interface


class ScoutGui:
    def __init__(self, default_timeout: int = 90) -> None:
        self.root = tk.Tk()
        self.root.title("py-scout")
        self.root.geometry("760x520")
        self.root.minsize(640, 420)

        self.default_timeout = default_timeout
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.scan_thread: threading.Thread | None = None
        self.last_result_text = ""

        self.timeout_var = tk.StringVar(value=str(default_timeout))
        self.status_var = tk.StringVar(value="Ready")

        self._build_layout()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=16)
        container.pack(fill="both", expand=True)

        controls = ttk.Frame(container)
        controls.pack(fill="x")

        ttk.Label(controls, text="Timeout (seconds)").pack(side="left")

        timeout_entry = ttk.Entry(controls, width=8, textvariable=self.timeout_var)
        timeout_entry.pack(side="left", padx=(8, 12))

        self.scan_button = ttk.Button(controls, text="Scan", command=self.start_scan)
        self.scan_button.pack(side="left")

        self.list_button = ttk.Button(
            controls,
            text="List Interfaces",
            command=self.show_interfaces,
        )
        self.list_button.pack(side="left", padx=8)

        self.copy_button = ttk.Button(
            controls,
            text="Copy Result",
            command=self.copy_result,
        )
        self.copy_button.pack(side="left")

        status_frame = ttk.Frame(container, padding=(0, 12, 0, 12))
        status_frame.pack(fill="x")

        ttk.Label(status_frame, text="Status").pack(side="left")
        ttk.Label(status_frame, textvariable=self.status_var).pack(side="left", padx=(8, 0))

        self.output = scrolledtext.ScrolledText(
            container,
            wrap="word",
            height=24,
            font=("Consolas", 10),
        )
        self.output.pack(fill="both", expand=True)
        self.output.configure(state="disabled")

        self._write_output(
            "py-scout\n"
            "--------\n"
            "Use Scan to auto-select an active Ethernet adapter and wait for LLDP/CDP.\n"
            "Use List Interfaces to review tshark capture interfaces.\n"
        )

    def _write_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        self.scan_button.configure(state=state)
        self.list_button.configure(state=state)

    def _parse_timeout(self) -> int | None:
        value = self.timeout_var.get().strip()
        if not value:
            return self.default_timeout

        try:
            timeout = int(value)
        except ValueError:
            messagebox.showerror("py-scout", "Timeout must be a whole number.")
            return None

        if timeout <= 0:
            messagebox.showerror("py-scout", "Timeout must be greater than zero.")
            return None

        return timeout

    def start_scan(self) -> None:
        if self.scan_thread and self.scan_thread.is_alive():
            return

        timeout = self._parse_timeout()
        if timeout is None:
            return

        self.status_var.set("Scanning...")
        self._set_busy(True)
        self._write_output("Scanning for LLDP/CDP advertisements...\n")

        self.scan_thread = threading.Thread(
            target=self._run_scan,
            args=(timeout,),
            daemon=True,
        )
        self.scan_thread.start()
        self.root.after(150, self._poll_queue)

    def _run_scan(self, timeout: int) -> None:
        try:
            selected = resolve_capture_interface(None)
            result = scan_on_interface(selected, timeout)
            self.worker_queue.put(("scan_result", result))
        except ScannerError as exc:
            self.worker_queue.put(("error", str(exc)))
        except Exception as exc:  # pragma: no cover - last-resort GUI protection
            self.worker_queue.put(("error", f"Unexpected error: {exc}"))

    def _poll_queue(self) -> None:
        try:
            event_name, payload = self.worker_queue.get_nowait()
        except queue.Empty:
            if self.scan_thread and self.scan_thread.is_alive():
                self.root.after(150, self._poll_queue)
                return

            self._set_busy(False)
            return

        if event_name == "scan_result":
            self._show_scan_result(payload)
        else:
            self.last_result_text = ""
            self.status_var.set("Scan failed")
            self._write_output(str(payload))

        self._set_busy(False)

    def _show_scan_result(self, result: object) -> None:
        if not hasattr(result, "adapter_name"):
            self.status_var.set("Scan failed")
            self._write_output("Unexpected scan result.")
            return

        adapter_name = getattr(result, "adapter_name", "unknown")
        protocol = getattr(result, "protocol", None) or "unknown"
        switch = getattr(result, "switch", None) or "unknown"
        port = getattr(result, "port", None) or "unknown"
        status = getattr(result, "status", "unknown")
        timeout_seconds = getattr(result, "timeout_seconds", "unknown")

        lines = [
            "Scan Result",
            "-----------",
            f"Adapter : {adapter_name}",
            f"Protocol: {protocol}",
            f"Switch  : {switch}",
            f"Port    : {port}",
            f"Status  : {status}",
            f"Timeout : {timeout_seconds}",
        ]

        self.last_result_text = "\n".join(lines)
        self._write_output(self.last_result_text)

        if status == "success":
            self.status_var.set("Neighbor found")
        elif status == "timeout":
            self.status_var.set("No neighbor detected before timeout")
        else:
            self.status_var.set(status)

    def show_interfaces(self) -> None:
        try:
            interfaces = get_interface_inventory()
        except ScannerError as exc:
            self.status_var.set("Interface lookup failed")
            self._write_output(str(exc))
            return

        lines = ["Available tshark capture interfaces", "----------------------------------"]
        for iface in interfaces:
            lines.append(
                f"{iface.number:>4}  {iface.name:<35} {iface.status:<12} {iface.role}"
            )

        self.last_result_text = "\n".join(lines)
        self.status_var.set("Interfaces listed")
        self._write_output(self.last_result_text)

    def copy_result(self) -> None:
        if not self.last_result_text:
            messagebox.showinfo("py-scout", "There is no result to copy yet.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(self.last_result_text)
        self.status_var.set("Result copied")

    def run(self) -> None:
        self.root.mainloop()


def launch_gui(default_timeout: int = 90) -> None:
    app = ScoutGui(default_timeout=default_timeout)
    app.run()
