from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .scanner import (
    ScannerError,
    ScanResult,
    get_interface_inventory,
    resolve_capture_interface,
    scan_on_interface,
)


class ScoutGui:
    def __init__(self, default_timeout: int = 90) -> None:
        self.root = tk.Tk()
        self.root.title("Py-Scout")
        self.root.geometry("840x560")
        self.root.minsize(720, 500)

        self.default_timeout = default_timeout
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.scan_thread: threading.Thread | None = None
        self.last_result_text = ""

        self.timeout_var = tk.StringVar(value=str(default_timeout))
        self.status_var = tk.StringVar(value="Ready")
        self.adapter_var = tk.StringVar(value="Not scanned")
        self.protocol_var = tk.StringVar(value="Not scanned")
        self.switch_var = tk.StringVar(value="Not scanned")
        self.port_var = tk.StringVar(value="Not scanned")
        self.neighbor_ip_var = tk.StringVar(value="Not scanned")
        self.result_status_var = tk.StringVar(value="Not scanned")

        self._configure_style()
        self._build_layout()

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(bg="#f4f6f8")
        style.configure("TFrame", background="#f4f6f8")
        style.configure("Header.TFrame", background="#162126")
        style.configure(
            "HeaderTitle.TLabel",
            background="#162126",
            foreground="#ffffff",
            font=("Segoe UI", 18, "bold"),
        )
        style.configure(
            "HeaderSub.TLabel",
            background="#162126",
            foreground="#cbd8d3",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Section.TLabelframe",
            background="#f4f6f8",
            bordercolor="#c7d0d5",
        )
        style.configure(
            "Section.TLabelframe.Label",
            background="#f4f6f8",
            foreground="#263238",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("Muted.TLabel", background="#f4f6f8", foreground="#5a6870")
        style.configure(
            "Value.TLabel",
            background="#f4f6f8",
            foreground="#182329",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("Status.TLabel", background="#f4f6f8", foreground="#2f5d44")

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        header = ttk.Frame(self.root, style="Header.TFrame", padding=(20, 16))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Py-Scout", style="HeaderTitle.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Label(
            header,
            text="LLDP/CDP switchport lookup using tshark",
            style="HeaderSub.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        container = ttk.Frame(self.root, padding=18)
        container.grid(row=1, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        self._build_controls(container)
        self._build_results(container)
        self._build_output(container)

        self._set_initial_output()

    def _build_controls(self, parent: ttk.Frame) -> None:
        controls = ttk.Labelframe(
            parent,
            text="Scan Controls",
            style="Section.TLabelframe",
            padding=14,
        )
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(5, weight=1)

        ttk.Label(controls, text="Timeout seconds").grid(row=0, column=0, sticky="w")

        timeout_entry = ttk.Entry(controls, width=8, textvariable=self.timeout_var)
        timeout_entry.grid(row=0, column=1, sticky="w", padx=(8, 16))

        self.scan_button = ttk.Button(controls, text="Scan", command=self.start_scan)
        self.scan_button.grid(row=0, column=2, sticky="w")

        self.list_button = ttk.Button(
            controls,
            text="List Interfaces",
            command=self.show_interfaces,
        )
        self.list_button.grid(row=0, column=3, sticky="w", padx=(8, 0))

        self.copy_button = ttk.Button(
            controls,
            text="Copy Result",
            command=self.copy_result,
        )
        self.copy_button.grid(row=0, column=4, sticky="w", padx=(8, 0))

        ttk.Label(controls, textvariable=self.status_var, style="Status.TLabel").grid(
            row=0,
            column=5,
            sticky="e",
            padx=(16, 0),
        )

    def _build_results(self, parent: ttk.Frame) -> None:
        results = ttk.Labelframe(
            parent,
            text="Current Result",
            style="Section.TLabelframe",
            padding=14,
        )
        results.grid(row=1, column=0, sticky="ew", pady=(14, 14))

        for column in range(3):
            results.columnconfigure(column, weight=1, uniform="result")

        self._add_result_field(results, 0, 0, "Adapter", self.adapter_var)
        self._add_result_field(results, 0, 1, "Protocol", self.protocol_var)
        self._add_result_field(results, 0, 2, "Switch", self.switch_var)
        self._add_result_field(results, 1, 0, "Port", self.port_var)
        self._add_result_field(results, 1, 1, "Neighbor IP", self.neighbor_ip_var)
        self._add_result_field(results, 1, 2, "Status", self.result_status_var)

    def _add_result_field(
        self,
        parent: ttk.Frame,
        row: int,
        column: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        frame = ttk.Frame(parent)
        frame.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=(0 if column == 0 else 12, 0),
            pady=(0 if row == 0 else 12, 0),
        )
        ttk.Label(frame, text=label, style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(frame, textvariable=variable, style="Value.TLabel", wraplength=135).grid(
            row=1,
            column=0,
            sticky="w",
            pady=(2, 0),
        )

    def _build_output(self, parent: ttk.Frame) -> None:
        output_frame = ttk.Labelframe(
            parent,
            text="Details",
            style="Section.TLabelframe",
            padding=10,
        )
        output_frame.grid(row=2, column=0, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.output = scrolledtext.ScrolledText(
            output_frame,
            wrap="word",
            height=12,
            font=("Consolas", 10),
            background="#0f1518",
            foreground="#eef5f1",
            insertbackground="#eef5f1",
            relief="flat",
            padx=12,
            pady=12,
        )
        self.output.grid(row=0, column=0, sticky="nsew")
        self.output.configure(state="disabled")

    def _set_initial_output(self) -> None:
        self._write_output(
            "Ready to scan.\n\n"
            "Scan auto-selects a usable Ethernet adapter and waits for LLDP/CDP.\n"
            "List Interfaces shows tshark capture interfaces and selection roles.\n"
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
            messagebox.showerror(
                "Py-Scout",
                "Timeout must be a whole number of seconds.",
            )
            return None

        if timeout < 1 or timeout > 3600:
            messagebox.showerror(
                "Py-Scout",
                "Timeout must be between 1 and 3600 seconds.",
            )
            return None

        return timeout

    def start_scan(self) -> None:
        if self.scan_thread and self.scan_thread.is_alive():
            return

        timeout = self._parse_timeout()
        if timeout is None:
            return

        self.status_var.set(f"Scanning for up to {timeout} seconds...")
        self.result_status_var.set("Scanning")
        self._set_busy(True)
        self._write_output(
            "Scanning for LLDP/CDP advertisements...\n"
            "The window remains usable while tshark waits for discovery traffic.\n"
        )

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
            self.worker_queue.put(("error", self._format_scanner_error(str(exc))))
        except Exception as exc:  # pragma: no cover - last-resort GUI protection
            self.worker_queue.put(("error", f"Unexpected error: {exc}"))

    def _format_scanner_error(self, message: str) -> str:
        lowered = message.lower()
        if "tshark not found" in lowered:
            return (
                "tshark was not found or could not be started.\n\n"
                "Install Wireshark with tshark, then make sure tshark is on PATH."
            )
        if "could not auto-select" in lowered:
            return (
                "Py-Scout could not find a usable Ethernet capture interface.\n\n"
                "Check the cable or adapter status, then use List Interfaces to "
                "review what tshark can see."
            )
        if "could not map" in lowered:
            return (
                f"{message}\n\n"
                "Use List Interfaces to confirm the Windows adapter name matches "
                "a tshark interface."
            )
        return message

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
            self.last_result_text = str(payload)
            self.status_var.set("Scan failed")
            self.result_status_var.set("Error")
            self._write_output(self.last_result_text)

        self._set_busy(False)

    def _show_scan_result(self, result: object) -> None:
        if not isinstance(result, ScanResult):
            self.last_result_text = "Unexpected scan result."
            self.status_var.set("Scan failed")
            self.result_status_var.set("Error")
            self._write_output(self.last_result_text)
            return

        protocol = result.protocol or "Not detected"
        switch = result.switch or "Not detected"
        port = result.port or "Not detected"
        neighbor_ip = result.neighbor_ip or "Not detected"

        self.adapter_var.set(result.adapter_name)
        self.protocol_var.set(protocol)
        self.switch_var.set(switch)
        self.port_var.set(port)
        self.neighbor_ip_var.set(neighbor_ip)
        self.result_status_var.set(result.status)

        lines = [
            "Scan Result",
            "-----------",
            f"Adapter : {result.adapter_name}",
            f"Protocol: {protocol}",
            f"Switch  : {switch}",
            f"Port    : {port}",
            f"Neighbor IP: {neighbor_ip}",
            f"Status  : {result.status}",
            f"Timeout : {result.timeout_seconds} seconds",
        ]

        if result.status == "success":
            self.status_var.set("Neighbor found")
            lines.append("\nLLDP/CDP neighbor details were detected.")
        elif result.status == "timeout":
            self.status_var.set("No neighbor detected before timeout")
            lines.append(
                "\nNo LLDP/CDP neighbor was detected before the timeout. "
                "Confirm LLDP or CDP is enabled and not filtered on the path."
            )
        else:
            self.status_var.set(result.status)

        self.last_result_text = "\n".join(lines)
        self._write_output(self.last_result_text)

    def show_interfaces(self) -> None:
        try:
            interfaces = get_interface_inventory()
        except ScannerError as exc:
            self.last_result_text = self._format_scanner_error(str(exc))
            self.status_var.set("Interface lookup failed")
            self.result_status_var.set("Error")
            self._write_output(self.last_result_text)
            return

        lines = ["Available tshark capture interfaces", "----------------------------------"]
        for iface in interfaces:
            lines.append(
                f"{iface.number:>4}  {iface.name:<35} {iface.status:<12} {iface.role}"
            )

        self.last_result_text = "\n".join(lines)
        self.status_var.set("Interfaces listed")
        self.result_status_var.set("Interface list")
        self._write_output(self.last_result_text)

    def copy_result(self) -> None:
        if not self.last_result_text:
            messagebox.showinfo("Py-Scout", "There is no result to copy yet.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(self.last_result_text)
        self.status_var.set("Result copied")

    def run(self) -> None:
        self.root.mainloop()


def launch_gui(default_timeout: int = 90) -> None:
    app = ScoutGui(default_timeout=default_timeout)
    app.run()
