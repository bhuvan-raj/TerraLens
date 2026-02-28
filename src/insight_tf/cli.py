"""
Insight-TF: A Terminal-based Terraform Dashboard
Built with Textual
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    Log,
    RichLog,
    Static,
    Tab,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)
from textual.widgets.tree import TreeNode
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box


# ─────────────────────────────────────────────
# App config (written by setup.py)
# ─────────────────────────────────────────────
def load_app_config() -> dict:
    config_path = Path(__file__).parent / ".insight-tf.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except Exception:
            pass
    return {}

APP_CONFIG = load_app_config()


# ─────────────────────────────────────────────
# Sample / fallback state (used when no real
# terraform.tfstate is found in cwd)
# ─────────────────────────────────────────────
SAMPLE_STATE: dict[str, Any] = {
    "version": 4,
    "terraform_version": "1.7.4",
    "serial": 42,
    "lineage": "abc123-def456",
    "resources": [
        {
            "type": "aws_instance",
            "name": "web_server",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {
                    "attributes": {
                        "id": "i-0abc123def456789",
                        "ami": "ami-0c55b159cbfafe1f0",
                        "instance_type": "t3.micro",
                        "availability_zone": "us-east-1a",
                        "public_ip": "54.123.45.67",
                        "private_ip": "10.0.1.100",
                        "tags": {"Name": "WebServer", "Env": "prod"},
                    }
                }
            ],
        },
        {
            "type": "aws_s3_bucket",
            "name": "assets",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {
                    "attributes": {
                        "id": "my-assets-bucket-prod",
                        "bucket": "my-assets-bucket-prod",
                        "region": "us-east-1",
                        "acl": "private",
                        "versioning": [{"enabled": True}],
                    }
                }
            ],
        },
        {
            "type": "aws_security_group",
            "name": "web_sg",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {
                    "attributes": {
                        "id": "sg-0123456789abcdef0",
                        "name": "web-security-group",
                        "description": "Security group for web servers",
                        "vpc_id": "vpc-0a1b2c3d4e5f",
                        "ingress": [
                            {"from_port": 80, "to_port": 80, "protocol": "tcp"},
                            {"from_port": 443, "to_port": 443, "protocol": "tcp"},
                        ],
                    }
                }
            ],
        },
        {
            "type": "aws_db_instance",
            "name": "main_db",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {
                    "attributes": {
                        "id": "main-db-prod",
                        "identifier": "main-db-prod",
                        "engine": "postgres",
                        "engine_version": "14.7",
                        "instance_class": "db.t3.medium",
                        "allocated_storage": 100,
                        "multi_az": True,
                    }
                }
            ],
        },
        {
            "type": "aws_vpc",
            "name": "main",
            "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
            "instances": [
                {
                    "attributes": {
                        "id": "vpc-0a1b2c3d4e5f",
                        "cidr_block": "10.0.0.0/16",
                        "enable_dns_hostnames": True,
                        "enable_dns_support": True,
                        "tags": {"Name": "MainVPC"},
                    }
                }
            ],
        },
    ],
}


# ─────────────────────────────────────────────
# State loader
# ─────────────────────────────────────────────
def load_state(path: str = "terraform.tfstate") -> dict[str, Any]:
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return SAMPLE_STATE


def format_value(v: Any, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(v, dict):
        lines = ["{"]
        for k, val in v.items():
            lines.append(f"{pad}  {k}: {format_value(val, indent+1)}")
        lines.append(pad + "}")
        return "\n".join(lines)
    elif isinstance(v, list):
        if not v:
            return "[]"
        lines = ["["]
        for item in v:
            lines.append(f"{pad}  {format_value(item, indent+1)}")
        lines.append(pad + "]")
        return "\n".join(lines)
    else:
        return str(v)


# ─────────────────────────────────────────────
# Overview Page
# ─────────────────────────────────────────────
class StatCard(Static):
    DEFAULT_CSS = """
    StatCard {
        border: tall $accent;
        padding: 1 2;
        margin: 1;
        width: 1fr;
        background: $surface;
        height: 7;
    }
    StatCard .card-label {
        color: $text-muted;
        text-style: italic;
    }
    StatCard .card-value {
        text-style: bold;
        color: $accent;
        content-align: center middle;
        text-align: center;
        padding-top: 1;
    }
    """

    def __init__(self, label: str, value: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._label = label
        self._value = value

    def compose(self) -> ComposeResult:
        yield Label(self._label, classes="card-label")
        yield Label(self._value, classes="card-value")


class OverviewPage(Container):
    DEFAULT_CSS = """
    OverviewPage {
        padding: 1 2;
    }
    #cards-row {
        height: auto;
        margin-bottom: 1;
    }
    #resource-table {
        border: tall $panel;
        padding: 1 2;
        background: $surface;
        height: 1fr;
    }
    .section-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    """

    def __init__(self, state: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._state = state

    def compose(self) -> ComposeResult:
        resources = self._state.get("resources", [])
        tf_ver = self._state.get("terraform_version", "N/A")
        serial = self._state.get("serial", "N/A")
        total = len(resources)

        yield Label("📊  Infrastructure Overview", classes="section-title")
        with Horizontal(id="cards-row"):
            yield StatCard("Terraform Version", tf_ver)
            yield StatCard("State Serial", str(serial))
            yield StatCard("Total Resources", str(total))
            yield StatCard(
                "Providers",
                str(len({r.get("provider", "").split("/")[-1] for r in resources})),
            )

        yield Label("Resource Summary", classes="section-title")
        yield self._build_table(resources)

    def _build_table(self, resources: list[dict]) -> Static:
        table = Table(
            "Type",
            "Name",
            "Provider",
            "Instances",
            box=box.SIMPLE_HEAVY,
            border_style="cyan",
            header_style="bold cyan",
            show_lines=True,
        )
        for r in resources:
            rtype = r.get("type", "N/A")
            name = r.get("name", "N/A")
            provider = r.get("provider", "N/A").split("/")[-1].replace('"', "")
            instances = str(len(r.get("instances", [])))
            table.add_row(rtype, name, provider, instances)
        return Static(table)


# ─────────────────────────────────────────────
# Manage Page
# ─────────────────────────────────────────────
class ResourceTree(Tree):
    DEFAULT_CSS = """
    ResourceTree {
        border: tall $panel;
        background: $surface;
        padding: 0 1;
        width: 35;
    }
    """


class AttributePanel(ScrollableContainer):
    DEFAULT_CSS = """
    AttributePanel {
        border: tall $panel;
        background: $surface;
        padding: 1 2;
        width: 1fr;
    }
    #attr-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #attr-content {
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Select a resource →", id="attr-title")
        yield Label("", id="attr-content")

    def show_resource(self, resource: dict, instance_attrs: dict) -> None:
        title = f"{resource['type']}.{resource['name']}"
        self.query_one("#attr-title", Label).update(f"📦  {title}")

        lines = []
        for k, v in instance_attrs.items():
            val_str = format_value(v)
            lines.append(f"[bold cyan]{k}[/bold cyan]:  {val_str}")

        self.query_one("#attr-content", Label).update("\n".join(lines))


class ManagePage(Container):
    DEFAULT_CSS = """
    ManagePage {
        padding: 0 1;
    }
    #top-controls {
        height: auto;
        padding: 1 0;
        margin-bottom: 1;
    }
    #top-controls Button {
        margin-right: 1;
    }
    #main-split {
        height: 1fr;
    }
    #output-panel {
        border: tall $panel;
        background: $surface;
        padding: 1;
        height: 12;
        margin-top: 1;
    }
    #output-label {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    Button.-success {
        background: $success;
    }
    Button.-warning {
        background: $warning;
    }
    Button.-error {
        background: $error;
    }
    """

    def __init__(self, state: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._state = state
        self._resource_map: dict[str, tuple[dict, dict]] = {}

    def compose(self) -> ComposeResult:
        with Horizontal(id="top-controls"):
            yield Button("➕  Add Resource", id="btn-add", variant="success")
            yield Button("🔍  Plan", id="btn-plan", variant="primary")
            yield Button("💰  Cost Estimate", id="btn-cost", variant="default")
            yield Button("🔄  Detect Drift", id="btn-drift", variant="warning")
            yield Button("🗑️  Destroy Selected", id="btn-destroy", variant="error")
            yield Button("⚡  Apply Now",        id="btn-apply-now", variant="success")

        with Horizontal(id="main-split"):
            yield ResourceTree("Resources", id="resource-tree")
            yield AttributePanel(id="attr-panel")

        yield Label("Output", id="output-label")
        yield RichLog(id="output-log", highlight=True, markup=True)

    def on_mount(self) -> None:
        self._populate_tree()

    def _populate_tree(self) -> None:
        tree = self.query_one("#resource-tree", ResourceTree)
        tree.clear()
        root = tree.root
        root.expand()

        resources = self._state.get("resources", [])
        type_nodes: dict[str, TreeNode] = {}

        for resource in resources:
            rtype = resource.get("type", "unknown")
            rname = resource.get("name", "unknown")

            if rtype not in type_nodes:
                icon = self._type_icon(rtype)
                node = root.add(f"{icon} {rtype}", expand=True)
                type_nodes[rtype] = node

            instances = resource.get("instances", [{}])
            attrs = instances[0].get("attributes", {}) if instances else {}
            leaf = type_nodes[rtype].add_leaf(f"  {rname}")
            key = str(id(leaf))
            self._resource_map[leaf.label.plain.strip()] = (resource, attrs)

    def _type_icon(self, rtype: str) -> str:
        icons = {
            "aws_instance": "🖥️",
            "aws_s3_bucket": "🪣",
            "aws_security_group": "🛡️",
            "aws_db_instance": "🗄️",
            "aws_vpc": "🌐",
            "aws_subnet": "📡",
            "aws_iam_role": "👤",
            "aws_lambda_function": "⚡",
            "google_compute_instance": "🖥️",
            "azurerm_virtual_machine": "🖥️",
        }
        return icons.get(rtype, "📦")

    @on(Tree.NodeSelected)
    def on_node_selected(self, event: Tree.NodeSelected) -> None:
        label = event.node.label.plain.strip()
        if label in self._resource_map:
            resource, attrs = self._resource_map[label]
            self.query_one("#attr-panel", AttributePanel).show_resource(resource, attrs)

    @on(Button.Pressed, "#btn-plan")
    def run_plan(self) -> None:
        log = self.query_one("#output-log", RichLog)
        log.clear()
        log.write("[bold green]▶ Running terraform plan...[/bold green]")
        self._run_real_plan(log)

    @work(thread=True)
    def _run_real_plan(self, log: RichLog) -> None:
        tf_dir = self.app._tf_dir

        # Check terraform binary exists
        which = subprocess.run(["which", "terraform"], capture_output=True, text=True)
        if which.returncode != 0:
            self.app.call_from_thread(
                log.write, "[bold red]✖ 'terraform' not found in PATH. Is it installed?[/bold red]"
            )
            return

        try:
            proc = subprocess.Popen(
                ["terraform", "plan", "-no-color"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=tf_dir,
            )
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.app.call_from_thread(log.write, stripped)
            proc.wait()

            if proc.returncode == 0:
                self.app.call_from_thread(
                    log.write, "\n[bold green]✅ Plan complete (no changes).[/bold green]"
                )
            elif proc.returncode == 2:
                self.app.call_from_thread(
                    log.write, "\n[bold yellow]⚠ Plan complete (changes detected).[/bold yellow]"
                )
            else:
                self.app.call_from_thread(
                    log.write, f"\n[bold red]✖ terraform plan exited with code {proc.returncode}[/bold red]"
                )
        except Exception as e:
            self.app.call_from_thread(log.write, f"[bold red]✖ Error: {e}[/bold red]")

    @on(Button.Pressed, "#btn-cost")
    def show_cost(self) -> None:
        log = self.query_one("#output-log", RichLog)
        log.clear()
        log.write("[bold cyan]💰 Running Infracost estimate...[/bold cyan]")
        self._run_infracost(log)

    @work(thread=True)
    def _run_infracost(self, log: RichLog) -> None:
        import shutil
        tf_dir = self.app._tf_dir

        # Resolve infracost binary — prefer config path, then PATH, then ~/.local/bin
        infracost_bin = (
            APP_CONFIG.get("infracost_path")
            or shutil.which("infracost")
            or str(Path.home() / ".local" / "bin" / "infracost")
        )
        if not Path(infracost_bin).exists() and not shutil.which(infracost_bin):
            self.app.call_from_thread(log.write, "[bold red]✖ Infracost not found.[/bold red]")
            self.app.call_from_thread(log.write, "")
            self.app.call_from_thread(log.write, "Run the setup script to install it automatically:")
            self.app.call_from_thread(log.write, "  [bold cyan]python setup.py[/bold cyan]")
            return

        # Check credentials exist
        creds_path = Path.home() / ".config" / "infracost" / "credentials.yml"
        if not creds_path.exists():
            self.app.call_from_thread(log.write, "[bold yellow]⚠ Infracost is not authenticated.[/bold yellow]")
            self.app.call_from_thread(log.write, "")
            self.app.call_from_thread(log.write, "Run the setup script to configure it:")
            self.app.call_from_thread(log.write, "  [bold cyan]python setup.py[/bold cyan]")
            self.app.call_from_thread(log.write, "")
            self.app.call_from_thread(log.write, "Or authenticate manually:")
            self.app.call_from_thread(log.write, "  [bold cyan]infracost auth login[/bold cyan]")
            return

        try:
            self.app.call_from_thread(log.write, "[dim]Fetching cloud pricing data...[/dim]")
            proc = subprocess.run(
                [infracost_bin, "breakdown", "--path", tf_dir, "--format", "json", "--no-color"],
                capture_output=True,
                text=True,
            )

            if proc.returncode != 0:
                self.app.call_from_thread(log.write, f"[bold red]✖ Infracost error:[/bold red]")
                for line in proc.stderr.splitlines():
                    if line.strip():
                        self.app.call_from_thread(log.write, line)
                return

            data = json.loads(proc.stdout)
            projects = data.get("projects", [])
            if not projects:
                self.app.call_from_thread(log.write, "[yellow]No projects found.[/yellow]")
                return

            breakdown = projects[0].get("breakdown", {})
            resources = breakdown.get("resources", [])

            # Header
            self.app.call_from_thread(log.write, "")
            self.app.call_from_thread(log.write, f"  {'Resource':<50} {'Monthly':>12}")
            self.app.call_from_thread(log.write, "  " + "─" * 64)

            total = 0.0
            for r in resources:
                name = r.get("name", "unknown")
                cost = r.get("monthlyCost")
                if cost is None:
                    cost_str = "[dim]usage-based[/dim]"
                else:
                    cost = float(cost)
                    total += cost
                    cost_str = f"[green]${cost:>10.2f}[/green]"
                self.app.call_from_thread(
                    log.write, f"  {name:<50} {cost_str}"
                )

            # Summary line
            self.app.call_from_thread(log.write, "  " + "─" * 64)
            summary = data.get("summary", {})
            unsupported = summary.get("totalUnsupportedResources", 0)
            self.app.call_from_thread(
                log.write,
                f"  [bold]{'TOTAL MONTHLY ESTIMATE':<50}[/bold] [bold green]${total:>10.2f}[/bold green]"
            )
            if unsupported:
                self.app.call_from_thread(
                    log.write,
                    f"  [dim]{unsupported} resource(s) not yet supported by Infracost pricing[/dim]"
                )
            self.app.call_from_thread(log.write, "")
            self.app.call_from_thread(log.write, "[bold green]✅ Estimate complete.[/bold green]")

        except json.JSONDecodeError:
            self.app.call_from_thread(log.write, "[bold red]✖ Failed to parse Infracost output.[/bold red]")
        except Exception as e:
            self.app.call_from_thread(log.write, f"[bold red]✖ Error: {e}[/bold red]")

    @on(Button.Pressed, "#btn-drift")
    def detect_drift(self) -> None:
        log = self.query_one("#output-log", RichLog)
        log.clear()
        log.write("[bold yellow]🔄 Detecting infrastructure drift...[/bold yellow]")
        log.write("[dim]Running: terraform plan -refresh-only -detailed-exitcode[/dim]")
        log.write("")
        self._run_drift_detection(log)

    @work(thread=True)
    def _run_drift_detection(self, log: RichLog) -> None:
        tf_dir = self.app._tf_dir

        # Check terraform binary
        which = subprocess.run(["which", "terraform"], capture_output=True, text=True)
        if which.returncode != 0:
            self.app.call_from_thread(log.write, "[bold red]✖ 'terraform' not found in PATH.[/bold red]")
            return

        try:
            # -refresh-only: only checks real infra vs state, no config changes
            # -detailed-exitcode: exit 0 = no drift, exit 2 = drift found, exit 1 = error
            proc = subprocess.Popen(
                [
                    "terraform", "plan",
                    "-refresh-only",
                    "-detailed-exitcode",
                    "-no-color",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=tf_dir,
            )

            stdout_lines = []
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    stdout_lines.append(stripped)
                    self.app.call_from_thread(log.write, stripped)

            proc.wait()
            stderr_out = proc.stderr.read().strip()

            self.app.call_from_thread(log.write, "")
            self.app.call_from_thread(log.write, "─" * 60)

            if proc.returncode == 0:
                # No drift at all
                self.app.call_from_thread(
                    log.write,
                    "[bold green]✅ No drift detected — infrastructure matches state.[/bold green]"
                )

            elif proc.returncode == 2:
                # Drift found — parse the output to summarise changed resources
                self.app.call_from_thread(
                    log.write,
                    "[bold yellow]⚠  Drift detected! Real infrastructure differs from state.[/bold yellow]"
                )
                self.app.call_from_thread(log.write, "")

                # Extract drifted resource addresses from plan output
                drifted = []
                for line in stdout_lines:
                    # Lines like: "  # aws_s3_bucket.my_bucket has changed"
                    if " has changed" in line or " has been deleted" in line or " has been created" in line:
                        # Strip leading whitespace and "# "
                        resource = line.strip().lstrip("# ").split(" ")[0]
                        if "." in resource:
                            status = "changed"
                            if "deleted" in line:
                                status = "deleted outside Terraform"
                            elif "created" in line:
                                status = "created outside Terraform"
                            drifted.append((resource, status))

                if drifted:
                    self.app.call_from_thread(log.write, "[bold]Drifted resources:[/bold]")
                    for resource, status in drifted:
                        icon = "🟡" if status == "changed" else "🔴"
                        self.app.call_from_thread(
                            log.write,
                            f"  {icon}  [cyan]{resource}[/cyan]  →  {status}"
                        )
                    self.app.call_from_thread(log.write, "")
                    self.app.call_from_thread(
                        log.write,
                        "[dim]To fix: run terraform apply -refresh-only to update state,[/dim]"
                    )
                    self.app.call_from_thread(
                        log.write,
                        "[dim]or re-apply your config to restore resources to desired state.[/dim]"
                    )
                else:
                    self.app.call_from_thread(
                        log.write,
                        "[dim]See full output above for details on what changed.[/dim]"
                    )

            else:
                # Actual error
                self.app.call_from_thread(
                    log.write,
                    f"[bold red]✖ terraform exited with code {proc.returncode}[/bold red]"
                )
                if stderr_out:
                    self.app.call_from_thread(log.write, "")
                    self.app.call_from_thread(log.write, "[red]Error output:[/red]")
                    for line in stderr_out.splitlines():
                        self.app.call_from_thread(log.write, f"  {line}")

        except Exception as e:
            self.app.call_from_thread(log.write, f"[bold red]✖ Error: {e}[/bold red]")

    @on(Button.Pressed, "#btn-add")
    def add_resource(self) -> None:
        log = self.query_one("#output-log", RichLog)
        tf_dir = self.app._tf_dir

        # ── wizard done callback ──────────────────────────────────────────
        def on_wizard_done(result: tuple[str, str, bool] | None) -> None:
            if result is None:
                log.clear()
                log.write("[dim]Add resource cancelled.[/dim]")
                return
            filepath, hcl, apply = result
            log.clear()
            log.write(f"[bold green]➕ Writing resource to {filepath}...[/bold green]")
            try:
                Path(filepath).write_text(hcl)
                log.write(f"[green]✔  File written: {filepath}[/green]")
                log.write("")
                if apply:
                    log.write("[bold yellow]🚀 Running terraform apply...[/bold yellow]")
                    self._apply_new_resource(filepath, log)
                else:
                    log.write("[dim]Running terraform plan to validate...[/dim]")
                    self._validate_new_resource(filepath, log)
            except Exception as e:
                log.write(f"[bold red]✖ Failed to write file: {e}[/bold red]")

        # ── AWS resource picker callback ──────────────────────────────────
        def on_resource_picked(rtype: str | None) -> None:
            if rtype is None:
                # Went back — re-show provider screen
                self.app.push_screen(ProviderSelectScreen(), on_provider_selected)
                return
            # If it is a resource with a full template, open the wizard
            # Otherwise open a minimal generic field wizard
            self.app.push_screen(AddResourceWizard(tf_dir, preselected=rtype), on_wizard_done)

        # ── provider selection callback ───────────────────────────────────
        def on_provider_selected(provider: str | None) -> None:
            if provider is None:
                log.clear()
                log.write("[dim]Add resource cancelled.[/dim]")
                return
            if provider == "aws":
                self.app.push_screen(AWSResourcePickerScreen(), on_resource_picked)

        self.app.push_screen(ProviderSelectScreen(), on_provider_selected)

    @work(thread=True)
    def _validate_new_resource(self, filepath: str, log: RichLog) -> None:
        """Run terraform plan after writing the new resource file."""
        tf_dir = self.app._tf_dir
        try:
            proc = subprocess.Popen(
                ["terraform", "plan", "-no-color"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=tf_dir,
            )
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.app.call_from_thread(log.write, stripped)
            proc.wait()
            if proc.returncode in (0, 2):
                self.app.call_from_thread(
                    log.write, "\n[bold green]✅ Resource validated. Review the plan above, then run terraform apply.[/bold green]"
                )
            else:
                self.app.call_from_thread(
                    log.write, f"\n[bold red]✖ Plan failed (exit {proc.returncode}). Check the file and fix any errors.[/bold red]"
                )
        except Exception as e:
            self.app.call_from_thread(log.write, f"[bold red]✖ {e}[/bold red]")

    @work(thread=True)
    def _apply_new_resource(self, filepath: str, log: RichLog) -> None:
        """Run terraform apply -auto-approve after writing the new resource file."""
        tf_dir = self.app._tf_dir
        try:
            # First run plan so user sees what will be created
            self.app.call_from_thread(log.write, "[dim]Planning changes...[/dim]")
            plan_proc = subprocess.Popen(
                ["terraform", "plan", "-no-color"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=tf_dir,
            )
            for line in plan_proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.app.call_from_thread(log.write, stripped)
            plan_proc.wait()

            if plan_proc.returncode not in (0, 2):
                self.app.call_from_thread(
                    log.write,
                    f"\n[bold red]✖ Plan failed (exit {plan_proc.returncode}). Fix errors before applying.[/bold red]"
                )
                return

            self.app.call_from_thread(log.write, "")
            self.app.call_from_thread(log.write, "─" * 60)
            self.app.call_from_thread(log.write, "[bold yellow]🚀 Applying changes...[/bold yellow]")
            self.app.call_from_thread(log.write, "")

            # Now apply
            apply_proc = subprocess.Popen(
                ["terraform", "apply", "-auto-approve", "-no-color"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=tf_dir,
            )
            for line in apply_proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.app.call_from_thread(log.write, stripped)
            apply_proc.wait()

            if apply_proc.returncode == 0:
                self.app.call_from_thread(
                    log.write, "\n[bold green]✅ Resource applied successfully![/bold green]"
                )
                # Reload the state so the new resource appears in the tree
                self.app.call_from_thread(self.app.action_reload_state)
            else:
                self.app.call_from_thread(
                    log.write,
                    f"\n[bold red]✖ Apply failed (exit {apply_proc.returncode}). Check the output above.[/bold red]"
                )
        except FileNotFoundError:
            self.app.call_from_thread(
                log.write, "[bold red]✖ 'terraform' not found in PATH.[/bold red]"
            )
        except Exception as e:
            self.app.call_from_thread(log.write, f"[bold red]✖ {e}[/bold red]")

    @on(Button.Pressed, "#btn-apply-now")
    def apply_now(self) -> None:
        log = self.query_one("#output-log", RichLog)
        log.clear()
        log.write("[bold green]⚡ Running terraform apply --auto-approve...[/bold green]")
        log.write("")
        self._run_apply_now(log)

    @work(thread=True)
    def _run_apply_now(self, log: RichLog) -> None:
        tf_dir = self.app._tf_dir
        which = subprocess.run(["which", "terraform"], capture_output=True, text=True)
        if which.returncode != 0:
            self.app.call_from_thread(log.write, "[bold red]✖ 'terraform' not found in PATH.[/bold red]")
            return
        try:
            proc = subprocess.Popen(
                ["terraform", "apply", "-auto-approve", "-no-color"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=tf_dir,
            )
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.app.call_from_thread(log.write, stripped)
            proc.wait()
            if proc.returncode == 0:
                self.app.call_from_thread(
                    log.write, "\n[bold green]✅ Apply complete![/bold green]"
                )
                self.app.call_from_thread(self.app.action_reload_state)
            else:
                self.app.call_from_thread(
                    log.write, f"\n[bold red]✖ Apply failed (exit {proc.returncode})[/bold red]"
                )
        except Exception as e:
            self.app.call_from_thread(log.write, f"[bold red]✖ {e}[/bold red]")

    @on(Button.Pressed, "#btn-destroy")
    def destroy_selected(self) -> None:
        log = self.query_one("#output-log", RichLog)
        tree = self.query_one("#resource-tree", ResourceTree)
        selected = tree.cursor_node
        if not selected or selected.allow_expand:
            log.clear()
            log.write("[red]✖ No leaf resource selected. Select a resource in the tree first.[/red]")
            return

        label = selected.label.plain.strip()
        parent = selected.parent
        rtype = parent.label.plain.strip() if parent else "unknown"
        rtype = " ".join(rtype.split()[1:]) if rtype else rtype
        resource_addr = f"{rtype}.{label}"

        def on_confirm(confirmed: bool) -> None:
            if confirmed:
                log.clear()
                log.write(f"[bold red]🗑️  Destroying {resource_addr}...[/bold red]")
                self._run_destroy(resource_addr, log)
            else:
                log.clear()
                log.write("[dim]Destroy cancelled.[/dim]")

        self.app.push_screen(ConfirmDestroyScreen(resource_addr), on_confirm)

    @work(thread=True)
    def _run_destroy(self, resource_addr: str, log: RichLog) -> None:
        tf_dir = self.app._tf_dir
        try:
            proc = subprocess.Popen(
                ["terraform", "destroy", "-target=" + resource_addr, "-auto-approve", "-no-color"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=tf_dir,
            )
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.app.call_from_thread(log.write, stripped)
            proc.wait()
            if proc.returncode == 0:
                self.app.call_from_thread(
                    log.write, "\n[bold green]✅ Resource destroyed successfully.[/bold green]"
                )
                self.app.call_from_thread(self.app.action_reload_state)
            else:
                self.app.call_from_thread(
                    log.write, f"\n[bold red]✖ Destroy failed (exit code {proc.returncode})[/bold red]"
                )
        except Exception as e:
            self.app.call_from_thread(log.write, f"[bold red]✖ Error: {e}[/bold red]")





# ─────────────────────────────────────────────
# Full AWS Resource Catalog
# ─────────────────────────────────────────────
AWS_RESOURCE_CATALOG: dict[str, list[dict]] = {
    "Compute": [
        {"type": "aws_instance",                        "description": "EC2 virtual machine"},
        {"type": "aws_launch_template",                 "description": "EC2 launch template"},
        {"type": "aws_launch_configuration",            "description": "EC2 launch configuration (legacy)"},
        {"type": "aws_autoscaling_group",               "description": "Auto Scaling group"},
        {"type": "aws_autoscaling_policy",              "description": "Auto Scaling scaling policy"},
        {"type": "aws_autoscaling_schedule",            "description": "Auto Scaling scheduled action"},
        {"type": "aws_spot_instance_request",           "description": "EC2 Spot instance request"},
        {"type": "aws_placement_group",                 "description": "EC2 placement group"},
        {"type": "aws_key_pair",                        "description": "EC2 SSH key pair"},
        {"type": "aws_ami",                             "description": "Amazon Machine Image"},
        {"type": "aws_ami_copy",                        "description": "Copy an AMI to another region"},
        {"type": "aws_ami_from_instance",               "description": "Create AMI from existing instance"},
        {"type": "aws_ebs_volume",                      "description": "EBS block storage volume"},
        {"type": "aws_ebs_snapshot",                    "description": "EBS volume snapshot"},
        {"type": "aws_ebs_snapshot_copy",               "description": "Copy EBS snapshot"},
        {"type": "aws_volume_attachment",               "description": "Attach EBS volume to instance"},
        {"type": "aws_eip",                             "description": "Elastic IP address"},
        {"type": "aws_eip_association",                 "description": "Associate EIP with instance"},
        {"type": "aws_dedicated_host",                  "description": "EC2 dedicated host"},
        {"type": "aws_capacity_reservation",            "description": "EC2 capacity reservation"},
    ],
    "Containers": [
        {"type": "aws_ecs_cluster",                     "description": "ECS container cluster"},
        {"type": "aws_ecs_service",                     "description": "ECS service (task runner)"},
        {"type": "aws_ecs_task_definition",             "description": "ECS task definition"},
        {"type": "aws_ecs_capacity_provider",           "description": "ECS capacity provider"},
        {"type": "aws_ecr_repository",                  "description": "ECR container image registry"},
        {"type": "aws_ecr_repository_policy",           "description": "ECR repository access policy"},
        {"type": "aws_ecr_lifecycle_policy",            "description": "ECR image lifecycle policy"},
        {"type": "aws_ecr_replication_configuration",   "description": "ECR cross-region replication"},
        {"type": "aws_eks_cluster",                     "description": "EKS Kubernetes cluster"},
        {"type": "aws_eks_node_group",                  "description": "EKS managed node group"},
        {"type": "aws_eks_fargate_profile",             "description": "EKS Fargate profile"},
        {"type": "aws_eks_addon",                       "description": "EKS cluster add-on"},
        {"type": "aws_eks_identity_provider_config",    "description": "EKS OIDC identity provider"},
    ],
    "Serverless": [
        {"type": "aws_lambda_function",                 "description": "Lambda serverless function"},
        {"type": "aws_lambda_alias",                    "description": "Lambda function alias"},
        {"type": "aws_lambda_event_source_mapping",     "description": "Lambda event source trigger"},
        {"type": "aws_lambda_function_url",             "description": "Lambda function URL endpoint"},
        {"type": "aws_lambda_layer_version",            "description": "Lambda layer (shared code)"},
        {"type": "aws_lambda_permission",               "description": "Lambda resource-based permission"},
        {"type": "aws_lambda_provisioned_concurrency_config", "description": "Lambda provisioned concurrency"},
        {"type": "aws_serverlessapplicationrepository_cloudformation_stack", "description": "SAR application stack"},
    ],
    "Storage": [
        {"type": "aws_s3_bucket",                       "description": "S3 object storage bucket"},
        {"type": "aws_s3_bucket_acl",                   "description": "S3 bucket ACL"},
        {"type": "aws_s3_bucket_cors_configuration",    "description": "S3 CORS configuration"},
        {"type": "aws_s3_bucket_lifecycle_configuration","description": "S3 lifecycle rules"},
        {"type": "aws_s3_bucket_logging",               "description": "S3 access logging"},
        {"type": "aws_s3_bucket_notification",          "description": "S3 event notifications"},
        {"type": "aws_s3_bucket_object",                "description": "S3 object (file upload)"},
        {"type": "aws_s3_bucket_policy",                "description": "S3 bucket resource policy"},
        {"type": "aws_s3_bucket_public_access_block",   "description": "S3 block public access settings"},
        {"type": "aws_s3_bucket_replication_configuration", "description": "S3 cross-region replication"},
        {"type": "aws_s3_bucket_server_side_encryption_configuration", "description": "S3 default encryption"},
        {"type": "aws_s3_bucket_versioning",            "description": "S3 bucket versioning"},
        {"type": "aws_s3_bucket_website_configuration", "description": "S3 static website hosting"},
        {"type": "aws_s3_object",                       "description": "S3 object (newer resource)"},
        {"type": "aws_efs_file_system",                 "description": "EFS elastic NFS file system"},
        {"type": "aws_efs_mount_target",                "description": "EFS mount target in subnet"},
        {"type": "aws_efs_access_point",                "description": "EFS application access point"},
        {"type": "aws_efs_backup_policy",               "description": "EFS backup policy"},
        {"type": "aws_fsx_lustre_file_system",          "description": "FSx for Lustre HPC file system"},
        {"type": "aws_fsx_windows_file_system",         "description": "FSx for Windows File Server"},
        {"type": "aws_fsx_ontap_file_system",           "description": "FSx for NetApp ONTAP"},
        {"type": "aws_glacier_vault",                   "description": "S3 Glacier archive vault"},
        {"type": "aws_storagegateway_gateway",          "description": "Storage Gateway appliance"},
    ],
    "Database": [
        {"type": "aws_db_instance",                     "description": "RDS managed relational database"},
        {"type": "aws_db_cluster",                      "description": "RDS Aurora cluster"},
        {"type": "aws_rds_cluster",                     "description": "Aurora Serverless cluster"},
        {"type": "aws_rds_cluster_instance",            "description": "Aurora cluster instance"},
        {"type": "aws_db_subnet_group",                 "description": "RDS subnet group"},
        {"type": "aws_db_parameter_group",              "description": "RDS database parameter group"},
        {"type": "aws_db_option_group",                 "description": "RDS database option group"},
        {"type": "aws_db_snapshot",                     "description": "RDS manual snapshot"},
        {"type": "aws_db_event_subscription",           "description": "RDS event notification"},
        {"type": "aws_dynamodb_table",                  "description": "DynamoDB NoSQL table"},
        {"type": "aws_dynamodb_global_table",           "description": "DynamoDB global (multi-region) table"},
        {"type": "aws_dynamodb_table_item",             "description": "DynamoDB table item"},
        {"type": "aws_elasticache_cluster",             "description": "ElastiCache Redis/Memcached cluster"},
        {"type": "aws_elasticache_replication_group",   "description": "ElastiCache Redis replication group"},
        {"type": "aws_elasticache_subnet_group",        "description": "ElastiCache subnet group"},
        {"type": "aws_elasticache_parameter_group",     "description": "ElastiCache parameter group"},
        {"type": "aws_redshift_cluster",                "description": "Redshift data warehouse cluster"},
        {"type": "aws_redshift_subnet_group",           "description": "Redshift subnet group"},
        {"type": "aws_redshift_parameter_group",        "description": "Redshift parameter group"},
        {"type": "aws_neptune_cluster",                 "description": "Neptune graph database cluster"},
        {"type": "aws_neptune_cluster_instance",        "description": "Neptune cluster instance"},
        {"type": "aws_docdb_cluster",                   "description": "DocumentDB (MongoDB-compatible) cluster"},
        {"type": "aws_docdb_cluster_instance",          "description": "DocumentDB cluster instance"},
        {"type": "aws_timestreaminfluxdb_db_instance",  "description": "Timestream InfluxDB instance"},
        {"type": "aws_memorydb_cluster",                "description": "MemoryDB for Redis cluster"},
        {"type": "aws_keyspaces_table",                 "description": "Keyspaces (Cassandra) table"},
        {"type": "aws_opensearch_domain",               "description": "OpenSearch Service domain"},
    ],
    "Networking": [
        {"type": "aws_vpc",                             "description": "Virtual Private Cloud"},
        {"type": "aws_subnet",                          "description": "VPC subnet"},
        {"type": "aws_internet_gateway",                "description": "VPC internet gateway"},
        {"type": "aws_nat_gateway",                     "description": "NAT gateway for private subnets"},
        {"type": "aws_route_table",                     "description": "VPC route table"},
        {"type": "aws_route",                           "description": "Individual VPC route"},
        {"type": "aws_route_table_association",         "description": "Associate route table with subnet"},
        {"type": "aws_security_group",                  "description": "EC2/VPC security group"},
        {"type": "aws_security_group_rule",             "description": "Individual security group rule"},
        {"type": "aws_vpc_peering_connection",          "description": "VPC peering connection"},
        {"type": "aws_vpc_endpoint",                    "description": "VPC endpoint for AWS services"},
        {"type": "aws_vpc_endpoint_service",            "description": "VPC endpoint service (PrivateLink)"},
        {"type": "aws_network_acl",                     "description": "VPC Network ACL"},
        {"type": "aws_network_acl_rule",                "description": "Network ACL rule"},
        {"type": "aws_vpn_gateway",                     "description": "VPN gateway"},
        {"type": "aws_vpn_connection",                  "description": "Site-to-site VPN connection"},
        {"type": "aws_customer_gateway",                "description": "Customer gateway for VPN"},
        {"type": "aws_dx_connection",                   "description": "AWS Direct Connect connection"},
        {"type": "aws_dx_gateway",                      "description": "Direct Connect gateway"},
        {"type": "aws_dx_virtual_interface",            "description": "Direct Connect virtual interface"},
        {"type": "aws_transit_gateway",                 "description": "Transit Gateway (hub routing)"},
        {"type": "aws_transit_gateway_vpc_attachment",  "description": "Transit Gateway VPC attachment"},
        {"type": "aws_transit_gateway_route_table",     "description": "Transit Gateway route table"},
        {"type": "aws_flow_log",                        "description": "VPC flow log"},
        {"type": "aws_network_interface",               "description": "Elastic Network Interface"},
        {"type": "aws_egress_only_internet_gateway",    "description": "Egress-only internet gateway (IPv6)"},
    ],
    "Load Balancing": [
        {"type": "aws_lb",                              "description": "Application/Network Load Balancer"},
        {"type": "aws_alb",                             "description": "Application Load Balancer (alias)"},
        {"type": "aws_lb_listener",                     "description": "ALB/NLB listener"},
        {"type": "aws_lb_listener_rule",                "description": "ALB listener routing rule"},
        {"type": "aws_lb_target_group",                 "description": "ALB/NLB target group"},
        {"type": "aws_lb_target_group_attachment",      "description": "Register target with target group"},
        {"type": "aws_elb",                             "description": "Classic Load Balancer (legacy)"},
        {"type": "aws_app_cookie_stickiness_policy",    "description": "ELB app cookie stickiness"},
        {"type": "aws_proxy_protocol_policy",           "description": "ELB proxy protocol policy"},
    ],
    "DNS & CDN": [
        {"type": "aws_route53_zone",                    "description": "Route 53 hosted DNS zone"},
        {"type": "aws_route53_record",                  "description": "Route 53 DNS record"},
        {"type": "aws_route53_health_check",            "description": "Route 53 health check"},
        {"type": "aws_route53_delegation_set",          "description": "Route 53 reusable delegation set"},
        {"type": "aws_route53_query_log",               "description": "Route 53 query logging"},
        {"type": "aws_route53_resolver_endpoint",       "description": "Route 53 Resolver endpoint"},
        {"type": "aws_route53_resolver_rule",           "description": "Route 53 Resolver forwarding rule"},
        {"type": "aws_cloudfront_distribution",         "description": "CloudFront CDN distribution"},
        {"type": "aws_cloudfront_cache_policy",         "description": "CloudFront cache policy"},
        {"type": "aws_cloudfront_origin_access_identity","description": "CloudFront OAI for S3"},
        {"type": "aws_cloudfront_origin_request_policy","description": "CloudFront origin request policy"},
        {"type": "aws_cloudfront_function",             "description": "CloudFront edge function"},
        {"type": "aws_cloudfront_realtime_log_config",  "description": "CloudFront real-time logs"},
        {"type": "aws_globalaccelerator_accelerator",   "description": "Global Accelerator"},
        {"type": "aws_globalaccelerator_endpoint_group","description": "Global Accelerator endpoint group"},
        {"type": "aws_globalaccelerator_listener",      "description": "Global Accelerator listener"},
    ],
    "IAM & Security": [
        {"type": "aws_iam_user",                        "description": "IAM user"},
        {"type": "aws_iam_user_policy",                 "description": "IAM inline user policy"},
        {"type": "aws_iam_user_policy_attachment",      "description": "Attach managed policy to user"},
        {"type": "aws_iam_user_login_profile",          "description": "IAM user console login profile"},
        {"type": "aws_iam_access_key",                  "description": "IAM user access key"},
        {"type": "aws_iam_group",                       "description": "IAM group"},
        {"type": "aws_iam_group_membership",            "description": "IAM group membership"},
        {"type": "aws_iam_group_policy",                "description": "IAM inline group policy"},
        {"type": "aws_iam_group_policy_attachment",     "description": "Attach managed policy to group"},
        {"type": "aws_iam_role",                        "description": "IAM role"},
        {"type": "aws_iam_role_policy",                 "description": "IAM inline role policy"},
        {"type": "aws_iam_role_policy_attachment",      "description": "Attach managed policy to role"},
        {"type": "aws_iam_policy",                      "description": "IAM managed policy"},
        {"type": "aws_iam_instance_profile",            "description": "IAM instance profile for EC2"},
        {"type": "aws_iam_openid_connect_provider",     "description": "IAM OIDC identity provider"},
        {"type": "aws_iam_saml_provider",               "description": "IAM SAML identity provider"},
        {"type": "aws_iam_server_certificate",          "description": "IAM SSL/TLS certificate"},
        {"type": "aws_iam_account_password_policy",     "description": "IAM account password policy"},
        {"type": "aws_iam_account_alias",               "description": "IAM account alias"},
        {"type": "aws_kms_key",                         "description": "KMS encryption key"},
        {"type": "aws_kms_alias",                       "description": "KMS key alias"},
        {"type": "aws_kms_grant",                       "description": "KMS key grant"},
        {"type": "aws_secretsmanager_secret",           "description": "Secrets Manager secret"},
        {"type": "aws_secretsmanager_secret_version",   "description": "Secrets Manager secret value"},
        {"type": "aws_secretsmanager_secret_rotation",  "description": "Secrets Manager rotation config"},
        {"type": "aws_ssm_parameter",                   "description": "SSM Parameter Store value"},
        {"type": "aws_ssm_document",                    "description": "SSM automation/run document"},
        {"type": "aws_acm_certificate",                 "description": "ACM SSL/TLS certificate"},
        {"type": "aws_acm_certificate_validation",      "description": "ACM certificate DNS validation"},
        {"type": "aws_wafv2_web_acl",                   "description": "WAFv2 Web ACL"},
        {"type": "aws_wafv2_ip_set",                    "description": "WAFv2 IP set"},
        {"type": "aws_wafv2_regex_pattern_set",         "description": "WAFv2 regex pattern set"},
        {"type": "aws_wafv2_rule_group",                "description": "WAFv2 rule group"},
        {"type": "aws_shield_protection",               "description": "AWS Shield DDoS protection"},
        {"type": "aws_guardduty_detector",              "description": "GuardDuty threat detection"},
        {"type": "aws_guardduty_member",                "description": "GuardDuty member account"},
        {"type": "aws_inspector2_enabler",              "description": "Inspector v2 vulnerability scanning"},
        {"type": "aws_macie2_account",                  "description": "Macie data security/discovery"},
        {"type": "aws_securityhub_account",             "description": "Security Hub aggregation"},
        {"type": "aws_detective_graph",                 "description": "Detective security investigation"},
        {"type": "aws_cognito_user_pool",               "description": "Cognito user pool"},
        {"type": "aws_cognito_user_pool_client",        "description": "Cognito app client"},
        {"type": "aws_cognito_identity_pool",           "description": "Cognito identity pool (federated)"},
    ],
    "Messaging & Queuing": [
        {"type": "aws_sqs_queue",                       "description": "SQS message queue"},
        {"type": "aws_sqs_queue_policy",                "description": "SQS queue access policy"},
        {"type": "aws_sqs_queue_redrive_policy",        "description": "SQS dead-letter queue policy"},
        {"type": "aws_sns_topic",                       "description": "SNS notification topic"},
        {"type": "aws_sns_topic_subscription",          "description": "SNS topic subscription"},
        {"type": "aws_sns_topic_policy",                "description": "SNS topic access policy"},
        {"type": "aws_mq_broker",                       "description": "Amazon MQ message broker"},
        {"type": "aws_mq_configuration",                "description": "Amazon MQ broker configuration"},
        {"type": "aws_kinesis_stream",                  "description": "Kinesis data stream"},
        {"type": "aws_kinesis_firehose_delivery_stream","description": "Kinesis Firehose delivery stream"},
        {"type": "aws_kinesis_analytics_application",   "description": "Kinesis Analytics (SQL) application"},
        {"type": "aws_kinesisanalyticsv2_application",  "description": "Kinesis Analytics v2 (Flink) app"},
        {"type": "aws_kafka_cluster",                   "description": "MSK Apache Kafka cluster"},
        {"type": "aws_msk_cluster",                     "description": "MSK cluster (alias)"},
        {"type": "aws_msk_configuration",               "description": "MSK broker configuration"},
        {"type": "aws_eventbridge_bus",                 "description": "EventBridge custom event bus"},
        {"type": "aws_cloudwatch_event_bus",            "description": "CloudWatch Events bus (legacy)"},
        {"type": "aws_cloudwatch_event_rule",           "description": "EventBridge/CloudWatch event rule"},
        {"type": "aws_cloudwatch_event_target",         "description": "EventBridge event target"},
        {"type": "aws_pipes_pipe",                      "description": "EventBridge Pipes event pipeline"},
    ],
    "Monitoring & Logging": [
        {"type": "aws_cloudwatch_metric_alarm",         "description": "CloudWatch metric alarm"},
        {"type": "aws_cloudwatch_composite_alarm",      "description": "CloudWatch composite alarm"},
        {"type": "aws_cloudwatch_dashboard",            "description": "CloudWatch dashboard"},
        {"type": "aws_cloudwatch_log_group",            "description": "CloudWatch Logs log group"},
        {"type": "aws_cloudwatch_log_stream",           "description": "CloudWatch Logs log stream"},
        {"type": "aws_cloudwatch_log_metric_filter",    "description": "CloudWatch Logs metric filter"},
        {"type": "aws_cloudwatch_log_subscription_filter","description": "CloudWatch Logs subscription"},
        {"type": "aws_cloudwatch_log_destination",      "description": "CloudWatch Logs destination"},
        {"type": "aws_cloudwatch_log_resource_policy",  "description": "CloudWatch Logs resource policy"},
        {"type": "aws_cloudwatch_metric_stream",        "description": "CloudWatch metric stream"},
        {"type": "aws_xray_group",                      "description": "X-Ray trace group"},
        {"type": "aws_xray_sampling_rule",              "description": "X-Ray sampling rule"},
        {"type": "aws_cloudtrail",                      "description": "CloudTrail audit log trail"},
        {"type": "aws_cloudtrail_event_data_store",     "description": "CloudTrail Lake event data store"},
        {"type": "aws_config_config_rule",              "description": "AWS Config compliance rule"},
        {"type": "aws_config_configuration_recorder",   "description": "AWS Config recorder"},
        {"type": "aws_config_delivery_channel",         "description": "AWS Config delivery channel"},
        {"type": "aws_config_conformance_pack",         "description": "AWS Config conformance pack"},
    ],
    "API & Integration": [
        {"type": "aws_api_gateway_rest_api",            "description": "API Gateway REST API"},
        {"type": "aws_api_gateway_resource",            "description": "API Gateway resource path"},
        {"type": "aws_api_gateway_method",              "description": "API Gateway HTTP method"},
        {"type": "aws_api_gateway_integration",         "description": "API Gateway backend integration"},
        {"type": "aws_api_gateway_deployment",          "description": "API Gateway deployment"},
        {"type": "aws_api_gateway_stage",               "description": "API Gateway stage (env)"},
        {"type": "aws_api_gateway_authorizer",          "description": "API Gateway Lambda/Cognito auth"},
        {"type": "aws_api_gateway_domain_name",         "description": "API Gateway custom domain"},
        {"type": "aws_api_gateway_usage_plan",          "description": "API Gateway usage plan"},
        {"type": "aws_api_gateway_api_key",             "description": "API Gateway API key"},
        {"type": "aws_apigatewayv2_api",                "description": "API Gateway v2 (HTTP/WebSocket API)"},
        {"type": "aws_apigatewayv2_stage",              "description": "API Gateway v2 stage"},
        {"type": "aws_apigatewayv2_route",              "description": "API Gateway v2 route"},
        {"type": "aws_apigatewayv2_integration",        "description": "API Gateway v2 integration"},
        {"type": "aws_apigatewayv2_authorizer",         "description": "API Gateway v2 authorizer"},
        {"type": "aws_apigatewayv2_domain_name",        "description": "API Gateway v2 custom domain"},
        {"type": "aws_appsync_graphql_api",             "description": "AppSync GraphQL API"},
        {"type": "aws_appsync_datasource",              "description": "AppSync data source"},
        {"type": "aws_appsync_resolver",                "description": "AppSync resolver"},
        {"type": "aws_sfn_state_machine",               "description": "Step Functions state machine"},
        {"type": "aws_sfn_activity",                    "description": "Step Functions activity"},
    ],
    "DevOps & CI/CD": [
        {"type": "aws_codebuild_project",               "description": "CodeBuild CI build project"},
        {"type": "aws_codebuild_report_group",          "description": "CodeBuild test report group"},
        {"type": "aws_codecommit_repository",           "description": "CodeCommit Git repository"},
        {"type": "aws_codedeploy_app",                  "description": "CodeDeploy application"},
        {"type": "aws_codedeploy_deployment_config",    "description": "CodeDeploy deployment config"},
        {"type": "aws_codedeploy_deployment_group",     "description": "CodeDeploy deployment group"},
        {"type": "aws_codepipeline",                    "description": "CodePipeline CI/CD pipeline"},
        {"type": "aws_codepipeline_webhook",            "description": "CodePipeline webhook trigger"},
        {"type": "aws_codeartifact_domain",             "description": "CodeArtifact artifact domain"},
        {"type": "aws_codeartifact_repository",         "description": "CodeArtifact package repository"},
        {"type": "aws_codestar_connections_connection",  "description": "CodeStar GitHub/GitLab connection"},
        {"type": "aws_codestar_notifications_notification_rule", "description": "CodeStar notification rule"},
        {"type": "aws_cloudformation_stack",            "description": "CloudFormation stack"},
        {"type": "aws_cloudformation_stack_set",        "description": "CloudFormation StackSet"},
        {"type": "aws_service_catalog_portfolio",       "description": "Service Catalog portfolio"},
        {"type": "aws_service_catalog_product",         "description": "Service Catalog product"},
    ],
    "Machine Learning": [
        {"type": "aws_sagemaker_domain",                "description": "SageMaker Studio domain"},
        {"type": "aws_sagemaker_model",                 "description": "SageMaker ML model"},
        {"type": "aws_sagemaker_endpoint",              "description": "SageMaker inference endpoint"},
        {"type": "aws_sagemaker_endpoint_configuration","description": "SageMaker endpoint config"},
        {"type": "aws_sagemaker_notebook_instance",     "description": "SageMaker Jupyter notebook"},
        {"type": "aws_sagemaker_training_job",          "description": "SageMaker training job"},
        {"type": "aws_sagemaker_feature_group",         "description": "SageMaker Feature Store group"},
        {"type": "aws_sagemaker_pipeline",              "description": "SageMaker ML pipeline"},
        {"type": "aws_bedrock_model_invocation_logging_configuration", "description": "Bedrock model logging"},
        {"type": "aws_bedrockagent_agent",              "description": "Bedrock Agent"},
        {"type": "aws_bedrockagent_knowledge_base",     "description": "Bedrock knowledge base"},
        {"type": "aws_rekognition_collection",          "description": "Rekognition image collection"},
        {"type": "aws_lexv2models_bot",                 "description": "Lex v2 conversational bot"},
        {"type": "aws_comprehend_entity_recognizer",    "description": "Comprehend entity recognizer"},
        {"type": "aws_translate_parallel_data",         "description": "Translate parallel data"},
    ],
    "Data & Analytics": [
        {"type": "aws_glue_catalog_database",           "description": "Glue Data Catalog database"},
        {"type": "aws_glue_catalog_table",              "description": "Glue Data Catalog table"},
        {"type": "aws_glue_job",                        "description": "Glue ETL job"},
        {"type": "aws_glue_crawler",                    "description": "Glue data crawler"},
        {"type": "aws_glue_connection",                 "description": "Glue data store connection"},
        {"type": "aws_glue_trigger",                    "description": "Glue workflow trigger"},
        {"type": "aws_glue_workflow",                   "description": "Glue orchestration workflow"},
        {"type": "aws_athena_database",                 "description": "Athena query database"},
        {"type": "aws_athena_workgroup",                "description": "Athena query workgroup"},
        {"type": "aws_athena_named_query",              "description": "Athena saved query"},
        {"type": "aws_emr_cluster",                     "description": "EMR Hadoop/Spark cluster"},
        {"type": "aws_emr_serverless_application",      "description": "EMR Serverless application"},
        {"type": "aws_lakeformation_resource",          "description": "Lake Formation data lake resource"},
        {"type": "aws_lakeformation_permissions",       "description": "Lake Formation permissions"},
        {"type": "aws_quicksight_user",                 "description": "QuickSight BI user"},
        {"type": "aws_quicksight_data_source",          "description": "QuickSight data source"},
        {"type": "aws_datapipeline_pipeline",           "description": "Data Pipeline workflow"},
    ],
    "IoT": [
        {"type": "aws_iot_thing",                       "description": "IoT device thing"},
        {"type": "aws_iot_thing_type",                  "description": "IoT thing type"},
        {"type": "aws_iot_certificate",                 "description": "IoT device certificate"},
        {"type": "aws_iot_policy",                      "description": "IoT device policy"},
        {"type": "aws_iot_topic_rule",                  "description": "IoT message routing rule"},
        {"type": "aws_iot_role_alias",                  "description": "IoT role alias"},
        {"type": "aws_iotevents_detector_model",        "description": "IoT Events detector model"},
        {"type": "aws_iotanalytics_channel",            "description": "IoT Analytics channel"},
    ],
    "Application Services": [
        {"type": "aws_elastic_beanstalk_application",   "description": "Elastic Beanstalk application"},
        {"type": "aws_elastic_beanstalk_environment",   "description": "Elastic Beanstalk environment"},
        {"type": "aws_lightsail_instance",              "description": "Lightsail VPS instance"},
        {"type": "aws_lightsail_static_ip",             "description": "Lightsail static IP"},
        {"type": "aws_lightsail_domain",                "description": "Lightsail DNS domain"},
        {"type": "aws_amplify_app",                     "description": "Amplify full-stack app"},
        {"type": "aws_amplify_branch",                  "description": "Amplify app branch"},
        {"type": "aws_apprunner_service",               "description": "App Runner containerized service"},
        {"type": "aws_apprunner_auto_scaling_configuration_version", "description": "App Runner autoscaling"},
        {"type": "aws_batch_job_definition",            "description": "Batch job definition"},
        {"type": "aws_batch_job_queue",                 "description": "Batch job queue"},
        {"type": "aws_batch_compute_environment",       "description": "Batch compute environment"},
    ],
    "Cost & Billing": [
        {"type": "aws_budgets_budget",                  "description": "AWS budget with alerts"},
        {"type": "aws_ce_cost_category",                "description": "Cost Explorer cost category"},
        {"type": "aws_cur_report_definition",           "description": "Cost & Usage Report definition"},
        {"type": "aws_savingsplans_savings_plan",        "description": "Savings Plan commitment"},
    ],
    "Migration": [
        {"type": "aws_dms_replication_instance",        "description": "DMS database migration instance"},
        {"type": "aws_dms_endpoint",                    "description": "DMS source/target endpoint"},
        {"type": "aws_dms_replication_task",            "description": "DMS migration replication task"},
        {"type": "aws_datasync_agent",                  "description": "DataSync transfer agent"},
        {"type": "aws_datasync_task",                   "description": "DataSync transfer task"},
        {"type": "aws_migration_hub_config",            "description": "Migration Hub home region config"},
    ],
    "Management": [
        {"type": "aws_organizations_organization",      "description": "AWS Organizations root"},
        {"type": "aws_organizations_account",           "description": "AWS Organizations member account"},
        {"type": "aws_organizations_policy",            "description": "Organizations SCP policy"},
        {"type": "aws_organizations_policy_attachment", "description": "Attach SCP to OU/account"},
        {"type": "aws_ram_resource_share",              "description": "RAM cross-account resource share"},
        {"type": "aws_ram_resource_association",        "description": "RAM resource association"},
        {"type": "aws_resourcegroups_group",            "description": "Resource Groups tag-based group"},
        {"type": "aws_ssm_maintenance_window",          "description": "SSM maintenance window"},
        {"type": "aws_ssm_patch_baseline",              "description": "SSM patch management baseline"},
        {"type": "aws_service_quotas_service_quota",    "description": "Service Quotas limit request"},
        {"type": "aws_account_alternate_contact",       "description": "Account alternate contact"},
        {"type": "aws_iam_service_linked_role",         "description": "IAM service-linked role"},
    ],
}

# Flatten catalog for search, deduplicating by type (keep first occurrence)
_seen_types: set[str] = set()
ALL_AWS_RESOURCES: list[dict] = []
for _cat, _resources in AWS_RESOURCE_CATALOG.items():
    for _r in _resources:
        if _r["type"] not in _seen_types:
            _seen_types.add(_r["type"])
            ALL_AWS_RESOURCES.append({"type": _r["type"], "description": _r["description"], "category": _cat})


# ─────────────────────────────────────────────
# Provider Selection Screen
# ─────────────────────────────────────────────
def _cat_id(cat: str) -> str:
    """Convert category name to a valid Textual widget ID."""
    return "cat-" + cat.replace(" ", "_").replace("&", "and").replace("/", "_")


PROVIDERS = [
    {"id": "aws",        "name": "Amazon Web Services",  "icon": "🟠", "supported": True},
    {"id": "azure",      "name": "Microsoft Azure",       "icon": "🔵", "supported": False},
    {"id": "gcp",        "name": "Google Cloud Platform", "icon": "🔴", "supported": False},
    {"id": "oracle",     "name": "Oracle Cloud",          "icon": "🟤", "supported": False},
    {"id": "docker",     "name": "Docker",                "icon": "🐳", "supported": False},
    {"id": "kubernetes", "name": "Kubernetes",            "icon": "☸️",  "supported": False},
]


class ProviderSelectScreen(ModalScreen[str | None]):
    DEFAULT_CSS = """
    ProviderSelectScreen {
        align: center middle;
    }
    #provider-container {
        width: 72;
        height: auto;
        border: tall $accent;
        background: $surface;
        padding: 0;
    }
    #provider-header {
        background: $accent;
        color: $background;
        padding: 0 2;
        height: 3;
        content-align: left middle;
        text-style: bold;
    }
    #provider-body {
        padding: 1 2;
    }
    #provider-subtitle {
        color: $text-muted;
        margin-bottom: 1;
    }
    .provider-btn {
        width: 1fr;
        height: 4;
        margin-bottom: 1;
        text-align: left;
    }
    .provider-btn-unsupported {
        width: 1fr;
        height: 4;
        margin-bottom: 1;
        text-align: left;
        opacity: 60%;
    }
    #provider-cancel-row {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="provider-container"):
            yield Label("➕  Add Resource  —  Select Provider", id="provider-header")
            with Vertical(id="provider-body"):
                yield Label("Choose the cloud provider for your new resource:", id="provider-subtitle")
                for p in PROVIDERS:
                    label = f"{p['icon']}  {p['name']}"
                    if not p["supported"]:
                        label += "  [dim](coming soon)[/dim]"
                    yield Button(
                        label,
                        id=f"provider-{p['id']}",
                        variant="primary" if p["supported"] else "default",
                        classes="provider-btn" if p["supported"] else "provider-btn-unsupported",
                    )
                with Horizontal(id="provider-cancel-row"):
                    yield Button("Cancel", id="provider-cancel", variant="default")

    @on(Button.Pressed)
    def handle_press(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "provider-cancel":
            self.dismiss(None)
            return
        if not btn_id.startswith("provider-"):
            return
        provider_id = btn_id[len("provider-"):]
        provider = next((p for p in PROVIDERS if p["id"] == provider_id), None)
        if not provider:
            return
        if not provider["supported"]:
            self.notify(
                f"{provider['name']} support coming soon! 🚧",
                severity="warning",
                timeout=3,
            )
            return
        self.dismiss(provider_id)
        event.stop()

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


# ─────────────────────────────────────────────
# AWS Resource Picker Screen
# ─────────────────────────────────────────────
class AWSResourcePickerScreen(ModalScreen[str | None]):
    """Full searchable AWS resource catalog grouped by category."""

    DEFAULT_CSS = """
    AWSResourcePickerScreen {
        align: center middle;
    }
    #picker-container {
        width: 96;
        height: 44;
        border: tall $accent;
        background: $surface;
        padding: 0;
    }
    #picker-header {
        background: $accent;
        color: $background;
        padding: 0 2;
        height: 3;
        content-align: left middle;
        text-style: bold;
    }
    #picker-search {
        margin: 1 2 0 2;
    }
    #picker-stats {
        color: $text-muted;
        margin: 0 2;
        height: 1;
    }
    #picker-split {
        height: 1fr;
        margin: 1 0 0 0;
    }
    #category-list {
        width: 28;
        border-right: solid $panel;
        overflow-y: auto;
    }
    .cat-btn {
        width: 1fr;
        height: 3;
        text-align: left;
        background: $surface;
        border: none;
        margin: 0;
    }
    .cat-btn.--active {
        background: $accent 30%;
        color: $accent;
        text-style: bold;
    }
    #resource-list {
        width: 1fr;
        overflow-y: auto;
        padding: 0 1;
    }
    .resource-btn {
        width: 1fr;
        height: 3;
        text-align: left;
        background: $surface;
        border: none;
        margin-bottom: 0;
    }
    .resource-btn:hover {
        background: $accent 20%;
    }
    #picker-footer {
        height: 4;
        padding: 1 2;
        border-top: solid $panel;
        align: right middle;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._active_category = "All"
        self._search_query = ""

    def compose(self) -> ComposeResult:
        total = len(ALL_AWS_RESOURCES)
        with Vertical(id="picker-container"):
            yield Label(
                f"🟠  AWS Resource Catalog  —  {total} resources available",
                id="picker-header"
            )
            yield Input(placeholder="🔍  Search resources...", id="picker-search")
            yield Label(f"Showing all {total} resources across {len(AWS_RESOURCE_CATALOG)} categories", id="picker-stats")
            with Horizontal(id="picker-split"):
                # Left: category list
                with ScrollableContainer(id="category-list"):
                    yield Button("All", id="cat-All", classes="cat-btn --active")
                    for cat in AWS_RESOURCE_CATALOG:
                        count = len(AWS_RESOURCE_CATALOG[cat])
                        yield Button(f"{cat} ({count})", id=_cat_id(cat), classes="cat-btn")
                # Right: resource list
                with ScrollableContainer(id="resource-list"):
                    yield from self._resource_buttons(ALL_AWS_RESOURCES)
            with Horizontal(id="picker-footer"):
                yield Button("← Back", id="picker-back", variant="default")

    def _resource_buttons(self, resources: list[dict]):
        for r in resources:
            yield Button(
                f"[bold]{r['type']}[/bold]\n[dim]{r['description']}[/dim]",
                name=r['type'],        # store type in name, no id (avoids duplicate ID errors)
                classes="resource-btn",
            )

    def _update_resource_list(self) -> None:
        # Filter by search and category
        results = ALL_AWS_RESOURCES
        if self._search_query:
            q = self._search_query.lower()
            results = [
                r for r in results
                if q in r["type"] or q in r["description"].lower() or q in r["category"].lower()
            ]
        if self._active_category != "All":
            results = [r for r in results if r["category"] == self._active_category]

        # Update stats label
        try:
            self.query_one("#picker-stats", Label).update(
                f"Showing {len(results)} of {len(ALL_AWS_RESOURCES)} resources"
                + (f" in [bold]{self._active_category}[/bold]" if self._active_category != "All" else "")
            )
        except Exception:
            pass

        # Rebuild resource list
        try:
            container = self.query_one("#resource-list", ScrollableContainer)
            container.remove_children()
            if results:
                container.mount(*list(self._resource_buttons(results)))
            else:
                container.mount(Label("[dim]No resources match your search.[/dim]"))
        except Exception:
            pass

    @on(Input.Changed, "#picker-search")
    def on_search(self, event: Input.Changed) -> None:
        self._search_query = event.value
        self._update_resource_list()

    @on(Button.Pressed)
    def on_button(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "picker-back":
            self.dismiss(None)
            return

        # Category selection
        if btn_id.startswith("cat-"):
            # Reverse slug back to original category name
            slug = btn_id[4:]
            if slug == "All":
                cat = "All"
            else:
                cat = next(
                    (c for c in AWS_RESOURCE_CATALOG if _cat_id(c) == btn_id),
                    slug
                )
            self._active_category = cat
            # Update active styling
            for c in list(AWS_RESOURCE_CATALOG.keys()) + ["All"]:
                try:
                    b = self.query_one(f"#cat-{c}", Button)
                    if c == cat:
                        b.add_class("--active")
                    else:
                        b.remove_class("--active")
                except Exception:
                    pass
            self._update_resource_list()
            event.stop()
            return

        # Resource selection — type stored in button.name (no id to avoid duplicates)
        if event.button.name and not btn_id.startswith("cat-") and btn_id != "picker-back":
            rtype = event.button.name
            self.dismiss(rtype)
            event.stop()
            return

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


# ─────────────────────────────────────────────
# Resource Templates
# ─────────────────────────────────────────────
# Each entry: { "fields": [{"name", "label", "placeholder", "required", "default"}] }
RESOURCE_TEMPLATES: dict[str, dict] = {
    "aws_s3_bucket": {
        "description": "S3 object storage bucket",
        "fields": [
            {"name": "resource_name", "label": "Resource name (TF identifier)", "placeholder": "my_bucket", "required": True, "default": ""},
            {"name": "bucket",        "label": "Bucket name (globally unique)",  "placeholder": "my-unique-bucket-name", "required": True, "default": ""},
            {"name": "tags_name",     "label": "Tag: Name",                       "placeholder": "MyBucket", "required": False, "default": ""},
        ],
        "template": '''resource "aws_s3_bucket" "{resource_name}" {{
  bucket = "{bucket}"{tags_block}
}}
''',
    },
    "aws_instance": {
        "description": "EC2 virtual machine",
        "fields": [
            {"name": "resource_name",   "label": "Resource name (TF identifier)", "placeholder": "web_server",            "required": True,  "default": ""},
            {"name": "ami",             "label": "AMI ID",                         "placeholder": "ami-0c55b159cbfafe1f0", "required": True,  "default": ""},
            {"name": "instance_type",   "label": "Instance type",                  "placeholder": "t3.micro",              "required": True,  "default": "t3.micro"},
            {"name": "tags_name",       "label": "Tag: Name",                      "placeholder": "WebServer",             "required": False, "default": ""},
        ],
        "template": '''resource "aws_instance" "{resource_name}" {{
  ami           = "{ami}"
  instance_type = "{instance_type}"{tags_block}
}}
''',
    },
    "aws_vpc": {
        "description": "Virtual Private Cloud network",
        "fields": [
            {"name": "resource_name",          "label": "Resource name (TF identifier)", "placeholder": "main",         "required": True,  "default": "main"},
            {"name": "cidr_block",             "label": "CIDR block",                    "placeholder": "10.0.0.0/16",  "required": True,  "default": "10.0.0.0/16"},
            {"name": "enable_dns_hostnames",   "label": "Enable DNS hostnames (true/false)", "placeholder": "true",    "required": False, "default": "true"},
            {"name": "tags_name",              "label": "Tag: Name",                     "placeholder": "MainVPC",      "required": False, "default": ""},
        ],
        "template": '''resource "aws_vpc" "{resource_name}" {{
  cidr_block           = "{cidr_block}"
  enable_dns_hostnames = {enable_dns_hostnames}{tags_block}
}}
''',
    },
    "aws_subnet": {
        "description": "Subnet within a VPC",
        "fields": [
            {"name": "resource_name",       "label": "Resource name (TF identifier)", "placeholder": "public_subnet_1",   "required": True,  "default": ""},
            {"name": "vpc_id",              "label": "VPC ID or reference",           "placeholder": "aws_vpc.main.id",   "required": True,  "default": ""},
            {"name": "cidr_block",          "label": "CIDR block",                    "placeholder": "10.0.1.0/24",       "required": True,  "default": ""},
            {"name": "availability_zone",   "label": "Availability zone",             "placeholder": "us-east-1a",        "required": False, "default": ""},
            {"name": "tags_name",           "label": "Tag: Name",                     "placeholder": "PublicSubnet1",     "required": False, "default": ""},
        ],
        "template": '''resource "aws_subnet" "{resource_name}" {{
  vpc_id            = {vpc_id}
  cidr_block        = "{cidr_block}"{az_block}{tags_block}
}}
''',
    },
    "aws_security_group": {
        "description": "EC2 security group (firewall rules)",
        "fields": [
            {"name": "resource_name", "label": "Resource name (TF identifier)", "placeholder": "web_sg",                 "required": True,  "default": ""},
            {"name": "name",          "label": "Security group name",            "placeholder": "web-security-group",     "required": True,  "default": ""},
            {"name": "description",   "label": "Description",                    "placeholder": "Security group for web", "required": True,  "default": ""},
            {"name": "vpc_id",        "label": "VPC ID or reference",            "placeholder": "aws_vpc.main.id",        "required": False, "default": ""},
            {"name": "tags_name",     "label": "Tag: Name",                      "placeholder": "WebSG",                  "required": False, "default": ""},
        ],
        "template": '''resource "aws_security_group" "{resource_name}" {{
  name        = "{name}"
  description = "{description}"{vpc_block}{tags_block}
}}
''',
    },
    "aws_db_instance": {
        "description": "RDS managed database",
        "fields": [
            {"name": "resource_name",      "label": "Resource name (TF identifier)", "placeholder": "main_db",       "required": True,  "default": ""},
            {"name": "identifier",         "label": "DB identifier",                  "placeholder": "main-db-prod",  "required": True,  "default": ""},
            {"name": "engine",             "label": "Engine",                         "placeholder": "postgres",      "required": True,  "default": "postgres"},
            {"name": "engine_version",     "label": "Engine version",                 "placeholder": "14",            "required": True,  "default": "14"},
            {"name": "instance_class",     "label": "Instance class",                 "placeholder": "db.t3.micro",   "required": True,  "default": "db.t3.micro"},
            {"name": "allocated_storage",  "label": "Allocated storage (GB)",         "placeholder": "20",            "required": True,  "default": "20"},
            {"name": "db_name",            "label": "Database name",                  "placeholder": "mydb",          "required": True,  "default": ""},
            {"name": "username",           "label": "Master username",                "placeholder": "admin",         "required": True,  "default": "admin"},
            {"name": "password",           "label": "Master password",                "placeholder": "changeme123",   "required": True,  "default": ""},
        ],
        "template": '''resource "aws_db_instance" "{resource_name}" {{
  identifier        = "{identifier}"
  engine            = "{engine}"
  engine_version    = "{engine_version}"
  instance_class    = "{instance_class}"
  allocated_storage = {allocated_storage}
  db_name           = "{db_name}"
  username          = "{username}"
  password          = "{password}"
  skip_final_snapshot = true
}}
''',
    },
    "aws_iam_role": {
        "description": "IAM role for AWS service permissions",
        "fields": [
            {"name": "resource_name", "label": "Resource name (TF identifier)", "placeholder": "lambda_role",        "required": True,  "default": ""},
            {"name": "name",          "label": "IAM role name",                  "placeholder": "lambda-exec-role",   "required": True,  "default": ""},
            {"name": "service",       "label": "AWS service principal",           "placeholder": "lambda.amazonaws.com","required": True, "default": "lambda.amazonaws.com"},
            {"name": "tags_name",     "label": "Tag: Name",                      "placeholder": "LambdaRole",         "required": False, "default": ""},
        ],
        "template": '''resource "aws_iam_role" "{resource_name}" {{
  name = "{name}"

  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [{{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = {{ Service = "{service}" }}
    }}]
  }}){tags_block}
}}
''',
    },
    "aws_lambda_function": {
        "description": "Serverless Lambda function",
        "fields": [
            {"name": "resource_name",  "label": "Resource name (TF identifier)", "placeholder": "my_lambda",          "required": True,  "default": ""},
            {"name": "function_name",  "label": "Function name",                  "placeholder": "my-lambda-function", "required": True,  "default": ""},
            {"name": "runtime",        "label": "Runtime",                         "placeholder": "python3.11",         "required": True,  "default": "python3.11"},
            {"name": "handler",        "label": "Handler",                         "placeholder": "index.handler",      "required": True,  "default": "index.handler"},
            {"name": "role",           "label": "IAM role ARN or reference",       "placeholder": "aws_iam_role.lambda_role.arn", "required": True, "default": ""},
            {"name": "filename",       "label": "ZIP filename",                    "placeholder": "lambda.zip",         "required": True,  "default": "lambda.zip"},
        ],
        "template": '''resource "aws_lambda_function" "{resource_name}" {{
  function_name = "{function_name}"
  runtime       = "{runtime}"
  handler       = "{handler}"
  role          = {role}
  filename      = "{filename}"
}}
''',
    },
}


def _build_tf_block(rtype: str, values: dict[str, str]) -> str:
    """Render a Terraform resource block from template + user values."""
    tmpl = RESOURCE_TEMPLATES[rtype]["template"]

    # Build optional tags block
    tags_name = values.get("tags_name", "").strip()
    if tags_name:
        values["tags_block"] = f'\n\n  tags = {{\n    Name = "{tags_name}"\n  }}'
    else:
        values["tags_block"] = ""

    # Optional blocks for specific resources
    az = values.get("availability_zone", "").strip()
    values["az_block"] = f'\n  availability_zone = "{az}"' if az else ""

    vpc = values.get("vpc_id", "").strip()
    values["vpc_block"] = f'\n  vpc_id = {vpc}' if vpc else ""

    dns = values.get("enable_dns_hostnames", "true").strip() or "true"
    values["enable_dns_hostnames"] = dns

    return tmpl.format(**values)


# ─────────────────────────────────────────────
# Add Resource Wizard  (3-step modal)
# ─────────────────────────────────────────────
class AddResourceWizard(ModalScreen[tuple[str, str, bool] | None]):
    """
    3-step wizard:
      Step 1 — pick resource type (searchable list)
      Step 2 — fill required/optional fields
      Step 3 — preview generated HCL and confirm write
    Returns (filename, hcl_content) or None on cancel.
    """

    DEFAULT_CSS = """
    AddResourceWizard {
        align: center middle;
    }
    #wizard-container {
        width: 90;
        height: 38;
        border: tall $accent;
        background: $surface;
        padding: 0;
    }
    #wizard-header {
        background: $accent;
        color: $background;
        padding: 0 2;
        height: 3;
        content-align: left middle;
        text-style: bold;
    }
    #wizard-body {
        padding: 1 2;
        height: 1fr;
    }
    #wizard-footer {
        height: 4;
        padding: 1 2;
        border-top: solid $panel;
        align: right middle;
    }
    #wizard-footer Button {
        margin-left: 1;
    }
    #btn-wiz-apply {
        display: none;
    }
    #btn-wiz-apply:enabled {
        display: block;
    }
    /* Step 1 */
    #search-input {
        margin-bottom: 1;
        width: 1fr;
    }
    #type-list {
        height: 1fr;
        border: solid $panel;
        overflow-y: auto;
    }
    .type-item {
        width: 1fr;
        height: 3;
        background: $surface;
        border: none;
        text-align: left;
        margin: 0;
    }
    .type-item:hover {
        background: $accent 20%;
    }
    .type-item.--selected {
        background: $accent;
        color: $background;
        text-style: bold;
    }
    /* Step 2 */
    .field-label {
        color: $accent;
        margin-top: 1;
    }
    .field-required {
        color: $error;
    }
    .field-input {
        margin-bottom: 0;
        width: 1fr;
    }
    /* Step 3 */
    #preview-area {
        height: 1fr;
        border: solid $panel;
        overflow-y: auto;
        padding: 1;
    }
    #filename-input {
        width: 1fr;
        margin-top: 1;
    }
    """

    def __init__(self, tf_dir: str, preselected: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tf_dir        = tf_dir
        self._field_inputs: dict[str, Input] = {}
        # If a resource type is preselected (from AWS picker), skip step 1
        if preselected:
            self._selected_type = preselected
            self._step = 2
        else:
            self._selected_type = ""
            self._step = 1

    # ── compose ──────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        if self._step == 2:
            header_text = f"➕  Configure  [cyan]{self._selected_type}[/cyan]"
        else:
            header_text = "➕  Add Resource  —  Step 1 of 3: Choose resource type"
        with Vertical(id="wizard-container"):
            yield Label(header_text, id="wizard-header")
            with ScrollableContainer(id="wizard-body"):
                if self._step == 2:
                    yield from self._compose_step2()
                else:
                    yield from self._compose_step1()
            with Horizontal(id="wizard-footer"):
                yield Button("← Back",          id="btn-wiz-cancel", variant="default")
                yield Button("Next →",           id="btn-wiz-next",   variant="primary")
                yield Button("🚀  Write & Apply", id="btn-wiz-apply",  variant="warning",
                             disabled=(self._step != 3))

    def _compose_step1(self) -> ComposeResult:
        yield Input(placeholder="Search resource type...", id="search-input")
        with ScrollableContainer(id="type-list"):
            for rtype, meta in RESOURCE_TEMPLATES.items():
                yield Button(
                    f"{rtype}  —  {meta['description']}",
                    id=f"type-{rtype}",
                    classes="type-item",
                    variant="default",
                )

    def _get_fields(self) -> list[dict]:
        """Return fields for selected type — template fields if available, else generic."""
        if self._selected_type in RESOURCE_TEMPLATES:
            return RESOURCE_TEMPLATES[self._selected_type]["fields"]
        # Generic fields for any resource not in the template library
        return [
            {"name": "resource_name", "label": "Resource name (TF identifier)",
             "placeholder": "my_resource", "required": True, "default": ""},
        ]

    def _compose_step2(self) -> ComposeResult:
        self._field_inputs = {}
        fields = self._get_fields()
        # Show resource info banner if not in templates
        if self._selected_type not in RESOURCE_TEMPLATES:
            res_info = next((r for r in ALL_AWS_RESOURCES if r["type"] == self._selected_type), None)
            desc = res_info["description"] if res_info else ""
            yield Label(
                f"[bold cyan]{self._selected_type}[/bold cyan]  —  {desc}",
                classes="field-label"
            )
            yield Label(
                "[yellow]ℹ  This resource uses a generic template. Edit the generated HCL in step 3.[/yellow]",
                classes="field-label"
            )
            yield Label("", classes="field-label")  # spacer
        for field in fields:
            req = "[bold red]*[/bold red] " if field["required"] else ""
            yield Label(f"{req}{field['label']}", classes="field-label")
            inp = Input(
                value=field["default"],
                placeholder=field["placeholder"],
                id=f"field-{field['name']}",
                classes="field-input",
            )
            self._field_inputs[field["name"]] = inp
            yield inp

    def _compose_step3(self, hcl: str, filename: str) -> ComposeResult:
        yield Label("📄  Generated Terraform HCL:", classes="field-label")
        yield TextArea(hcl, id="preview-area", read_only=True, language="css")
        yield Label("💾  Save to filename:", classes="field-label")
        yield Input(value=filename, id="filename-input")

    # ── step navigation ───────────────────────────────────────────────────
    def _go_to_step(self, step: int, hcl: str = "", filename: str = "") -> None:
        self._step = step
        header = self.query_one("#wizard-header", Label)
        body   = self.query_one("#wizard-body",   ScrollableContainer)

        body.remove_children()

        if step == 1:
            header.update("➕  Add Resource  —  Step 1 of 3: Choose resource type")
            body.mount(*list(self._compose_step1()))
        elif step == 2:
            header.update(f"➕  Add Resource  —  Step 2 of 3: Configure  [cyan]{self._selected_type}[/cyan]")
            body.mount(*list(self._compose_step2()))
        elif step == 3:
            header.update("➕  Add Resource  —  Step 3 of 3: Preview & Save")
            body.mount(*list(self._compose_step3(hcl, filename)))

        # Update footer buttons
        next_btn  = self.query_one("#btn-wiz-next",  Button)
        apply_btn = self.query_one("#btn-wiz-apply", Button)
        if step == 3:
            next_btn.label    = "💾  Write File"
            next_btn.variant  = "success"
            apply_btn.disabled = False
        else:
            next_btn.label    = "Next →"
            next_btn.variant  = "primary"
            apply_btn.disabled = True

    # ── search filter ─────────────────────────────────────────────────────
    @on(Input.Changed, "#search-input")
    def filter_types(self, event: Input.Changed) -> None:
        query = event.value.lower()
        for rtype in RESOURCE_TEMPLATES:
            try:
                item = self.query_one(f"#type-{rtype}", Button)
                if query in rtype or query in RESOURCE_TEMPLATES[rtype]["description"].lower():
                    item.display = True
                else:
                    item.display = False
            except Exception:
                pass

    # ── type selection (click on a row) ──────────────────────────────────
    @on(Button.Pressed)
    def select_type(self, event: Button.Pressed) -> None:
        if self._step != 1:
            return
        btn_id = event.button.id or ""
        if not btn_id.startswith("type-"):
            return
        rtype = btn_id[len("type-"):]
        if rtype not in RESOURCE_TEMPLATES:
            return
        # Deselect all, highlight selected
        for rt in RESOURCE_TEMPLATES:
            try:
                self.query_one(f"#type-{rt}", Button).remove_class("--selected")
            except Exception:
                pass
        event.button.add_class("--selected")
        self._selected_type = rtype
        event.stop()

    # ── next / write button ───────────────────────────────────────────────
    @on(Button.Pressed, "#btn-wiz-next")
    def next_step(self) -> None:
        if self._step == 1:
            if not self._selected_type:
                self.notify("Please select a resource type first.", severity="warning")
                return
            self._go_to_step(2)

        elif self._step == 2:
            # Collect field values
            values: dict[str, str] = {}
            fields = self._get_fields()
            missing = []
            for field in fields:
                try:
                    inp = self.query_one(f"#field-{field['name']}", Input)
                    val = inp.value.strip()
                except Exception:
                    val = field["default"]
                if field["required"] and not val:
                    missing.append(field["label"])
                values[field["name"]] = val or field["default"]

            if missing:
                self.notify(f"Required: {', '.join(missing)}", severity="error")
                return

            self._collected_values = values

            # Generate HCL — use template if available, else generic scaffold
            if self._selected_type in RESOURCE_TEMPLATES:
                hcl = _build_tf_block(self._selected_type, values)
            else:
                rname = values.get("resource_name", "my_resource")
                hcl = (
                    f'''resource "{self._selected_type}" "{rname}" {{\n'''
                    f'''  # TODO: fill in required arguments\n'''
                    f'''  # Docs: https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/{self._selected_type.replace("aws_", "")}\n'''
                    f'''}}\n'''
                )

            filename = f"{values.get('resource_name', 'resource')}_{self._selected_type}.tf"
            self._generated_hcl = hcl
            self._go_to_step(3, hcl, filename)

        elif self._step == 3:
            self._write_and_dismiss(apply=False)

    @on(Button.Pressed, "#btn-wiz-apply")
    def write_and_apply(self) -> None:
        if self._step == 3:
            self._write_and_dismiss(apply=True)

    def _write_and_dismiss(self, apply: bool) -> None:
        try:
            filename_input = self.query_one("#filename-input", Input)
            filename = filename_input.value.strip() or "new_resource.tf"
            if not filename.endswith(".tf"):
                filename += ".tf"
            filepath = Path(self._tf_dir) / filename
            hcl = self.query_one("#preview-area", TextArea).text
            self.dismiss((str(filepath), hcl, apply))
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    @on(Button.Pressed, "#btn-wiz-cancel")
    def cancel(self) -> None:
        if self._step > 1:
            self._go_to_step(self._step - 1)
            cancel_btn = self.query_one("#btn-wiz-cancel", Button)
            cancel_btn.label = "Cancel" if self._step == 1 else "← Back"
        else:
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


# ─────────────────────────────────────────────
# Confirmation Modal
# ─────────────────────────────────────────────
class ConfirmDestroyScreen(ModalScreen[bool]):
    DEFAULT_CSS = """
    ConfirmDestroyScreen {
        align: center middle;
    }
    #dialog {
        width: 64;
        height: auto;
        border: tall $error;
        background: $surface;
        padding: 2 4;
    }
    #dialog-title {
        text-style: bold;
        color: $error;
        margin-bottom: 1;
    }
    .dialog-body {
        color: $text-muted;
        margin-bottom: 2;
    }
    #dialog-addr {
        text-style: bold italic;
        color: $warning;
        margin-bottom: 2;
    }
    #btn-row {
        height: auto;
        align: right middle;
    }
    #btn-cancel {
        margin-right: 2;
    }
    """

    def __init__(self, resource_addr: str) -> None:
        super().__init__()
        self._addr = resource_addr

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("⚠️  Confirm Destroy", id="dialog-title")
            yield Label("You are about to permanently destroy:", classes="dialog-body")
            yield Label(self._addr, id="dialog-addr")
            yield Label("This will run terraform destroy -target and cannot be undone.", classes="dialog-body")
            with Horizontal(id="btn-row"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Destroy", id="btn-confirm", variant="error")

    @on(Button.Pressed, "#btn-confirm")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn-cancel")
    def cancel(self) -> None:
        self.dismiss(False)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)

# ─────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────
class InsightTF(App):
    TITLE = "Insight-TF"
    SUB_TITLE = "Terraform TUI Dashboard"

    CSS = """
    Screen {
        background: $background;
    }
    TabbedContent {
        height: 1fr;
    }
    TabPane {
        padding: 0;
    }
    #tab-overview {
        padding: 0;
    }
    #tab-manage {
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("1", "switch_tab('overview')", "Overview", show=True),
        Binding("2", "switch_tab('manage')", "Manage", show=True),
        Binding("r", "reload_state", "Reload State", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, state_path: str = "terraform.tfstate") -> None:
        super().__init__()
        self._state_path = state_path
        self._state = load_state(state_path)
        self._tf_dir = str(Path(state_path).parent.resolve()) if Path(state_path).exists() else str(Path.cwd())

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="overview"):
            with TabPane("📊  Overview", id="overview"):
                yield OverviewPage(self._state, id="overview-page")
            with TabPane("⚙️   Manage", id="manage"):
                yield ManagePage(self._state, id="manage-page")
        yield Footer()

    def action_switch_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    def action_reload_state(self) -> None:
        """Reload state file and refresh both pages."""
        self._state = load_state(self._state_path)
        self.call_after_refresh(self._rebuild_pages)

    def _rebuild_pages(self) -> None:
        """Tear down and remount both pages with fresh state."""
        # Rebuild manage page first (most important after destroy)
        try:
            manage = self.query_one("#manage-page", ManagePage)
            manage._state = self._state
            manage.query_one("#resource-tree", ResourceTree).clear()
            manage._resource_map = {}
            manage._populate_tree()
            manage.query_one("#attr-panel", AttributePanel).query_one("#attr-title", Label).update("Select a resource →")
            manage.query_one("#attr-panel", AttributePanel).query_one("#attr-content", Label).update("")
        except Exception:
            pass

        # Rebuild overview stats
        try:
            overview = self.query_one("#overview-page", OverviewPage)
            overview.remove()
            self.query_one("#overview", TabPane).mount(
                OverviewPage(self._state, id="overview-page")
            )
        except Exception:
            pass

        self.notify("✅ State refreshed", severity="information")


if __name__ == "__main__":
    import sys

    state_path = sys.argv[1] if len(sys.argv) > 1 else "terraform.tfstate"
    app = InsightTF(state_path)
    app.run()