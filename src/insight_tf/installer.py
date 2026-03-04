#!/usr/bin/env python3
"""
TerraLens Setup Script
Automatically installs and configures Infracost.
"""

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


# ── Terminal Colours ─────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"

def ok(msg):   print(f"  {GREEN}✔{RESET}  {msg}")
def info(msg): print(f"  {CYAN}→{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET}  {msg}")
def err(msg):  print(f"  {RED}✖{RESET}  {msg}")

def header(msg):
    print(f"\n{BOLD}{CYAN}{msg}{RESET}")
    print(f"  {'─' * (len(msg) + 2)}")


def run(cmd, **kwargs):
    return subprocess.run(cmd, **kwargs)


def run_check(cmd):
    return run(cmd, capture_output=True, text=True)


# ──────────────────────────────────────────────────────────────────
# Step 1: Terraform Check
# ──────────────────────────────────────────────────────────────────
def check_terraform():
    header("Checking Terraform")
    if shutil.which("terraform"):
        result = run_check(["terraform", "version"])
        ver = result.stdout.splitlines()[0]
        ok(f"Terraform found: {ver}")
    else:
        warn("Terraform not found in PATH.")
        warn("Install from: https://developer.hashicorp.com/terraform/install")


# ──────────────────────────────────────────────────────────────────
# Step 2: Infracost Installation
# ──────────────────────────────────────────────────────────────────
def install_infracost():
    header("Installing Infracost")

    if shutil.which("infracost"):
        result = run_check(["infracost", "--version"])
        ok(f"Infracost already installed: {result.stdout.strip()}")
        return True

    return _install_infracost_binary()


def _get_latest_version():
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/infracost/infracost/releases/latest",
            headers={"User-Agent": "terralens"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return data["tag_name"]
    except Exception:
        return "v0.10.43"


def _install_infracost_binary():
    system = platform.system().lower()
    machine = platform.machine().lower()

    arch_map = {
        "x86_64": "amd64",
        "amd64":  "amd64",
        "aarch64": "arm64",
        "arm64":  "arm64",
    }

    arch = arch_map.get(machine, machine)
    os_name = {"darwin": "darwin", "linux": "linux"}.get(system)

    if not os_name:
        warn("Unsupported OS for auto-install.")
        warn("Install manually: https://www.infracost.io/docs/")
        return False

    version = _get_latest_version()
    archive_name = f"infracost-{os_name}-{arch}.tar.gz"
    url = f"https://github.com/infracost/infracost/releases/download/{version}/{archive_name}"

    info(f"Downloading Infracost {version}...")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / archive_name
            urllib.request.urlretrieve(url, archive_path)

            extracted = Path(tmp) / "infracost"

            import tarfile
            with tarfile.open(archive_path, "r:gz") as tf:
                found = False
                for member in tf.getmembers():
                    if member.isfile():
                        filename = member.name.split("/")[-1]
                        if filename.startswith("infracost"):
                            f = tf.extractfile(member)
                            if f:
                                extracted.write_bytes(f.read())
                                found = True
                                break

                if not found:
                    err("Binary not found in archive.")
                    return False

            extracted.chmod(extracted.stat().st_mode | stat.S_IEXEC)

            install_dir = Path.home() / ".local" / "bin"
            install_dir.mkdir(parents=True, exist_ok=True)

            target = install_dir / "infracost"
            shutil.copy2(extracted, target)
            target.chmod(target.stat().st_mode | stat.S_IEXEC)

            ok(f"Infracost {version} installed to {target}")
            _ensure_path(install_dir)
            return True

    except Exception as e:
        err(f"Installation failed: {e}")
        return False


def _ensure_path(bin_dir: Path):
    if str(bin_dir) in os.environ.get("PATH", ""):
        return

    rc = Path.home() / ".bashrc"
    export_line = f'\nexport PATH="$PATH:{bin_dir}"\n'

    if rc.exists():
        content = rc.read_text()
        if str(bin_dir) not in content:
            rc.write_text(content + export_line)
            warn(f"Added {bin_dir} to PATH in ~/.bashrc — restart your terminal.")


# ──────────────────────────────────────────────────────────────────
# Step 3: Configure Infracost Auth
# ──────────────────────────────────────────────────────────────────
def configure_infracost():
    header("Configuring Infracost")

    if not shutil.which("infracost"):
        warn("Infracost not found in PATH. Skipping auth.")
        warn("You may need to restart your terminal and re-run this script.")
        return

    creds = Path.home() / ".config" / "infracost" / "credentials.yml"
    if creds.exists():
        ok("Already authenticated.")
        return

    print()
    print("  Infracost requires a free API key.")
    print("  Sign up at https://www.infracost.io/docs/ (no credit card required).")
    print()

    choice = input("  Authenticate now? (y/n): ").strip().lower()

    if choice == "y":
        result = run(["infracost", "auth", "login"])
        if result.returncode == 0:
            ok("Authenticated successfully.")
        else:
            warn("Auth failed. Run manually: infracost auth login")
    else:
        warn("Skipped. Run manually when ready: infracost auth login")


# ──────────────────────────────────────────────────────────────────
# Step 4: Write Config
# ──────────────────────────────────────────────────────────────────
def write_config():
    header("Writing app configuration")

    config = {
        "infracost_path": shutil.which("infracost"),
        "terraform_path": shutil.which("terraform"),
        "setup_complete": True
    }

    config_path = Path(__file__).parent / ".insight-tf.json"
    config_path.write_text(json.dumps(config, indent=2))
    ok(f"Config written to {config_path}")


# ──────────────────────────────────────────────────────────────────
# Step 5: Summary
# ──────────────────────────────────────────────────────────────────
def print_summary():
    tf_ok        = bool(shutil.which("terraform"))
    infracost_ok = bool(shutil.which("infracost"))

    print(f"\n{'─' * 50}")
    print("  Setup Summary")
    print(f"{'─' * 50}")
    print(f"  {'✔' if tf_ok        else '⚠'} Terraform")
    print(f"  {'✔' if infracost_ok else '⚠'} Infracost")
    print(f"{'─' * 50}\n")

    if tf_ok and infracost_ok:
        ok("All set! Run: terralens")
    else:
        warn("Setup completed with warnings. Check above for details.")
    print()


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n╔══════════════════════════════════╗")
    print("║        TerraLens Setup           ║")
    print("╚══════════════════════════════════╝")

    check_terraform()
    success = install_infracost()
    if success:
        configure_infracost()
    write_config()
    print_summary()
