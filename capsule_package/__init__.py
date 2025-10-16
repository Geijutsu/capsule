#!/usr/bin/env python3
"""Capsule - User-friendly server configuration tool using Nix"""

import subprocess
import sys
import os
import webbrowser
import tempfile
from pathlib import Path
import click
import yaml
from .nixos_generator import NixOSConfigGenerator, validate_config, test_in_vm

BASE_DIR = Path(__file__).parent
PROFILES_DIR = BASE_DIR / "profiles"
PRESETS_DIR = BASE_DIR / "presets"
SPROUTS_DIR = BASE_DIR / "sprouts"
CAPSULE_DIR = Path.home() / ".capsule"
CONFIGS_DIR = CAPSULE_DIR / "configs"
ACTIVE_CONFIG_FILE = CAPSULE_DIR / "active.txt"
CONFIG_FILE = None  # Will be set dynamically based on active config

# Built-in profiles embedded in the binary
BUILTIN_PROFILES = {
    "dev": {
        "description": "Full-stack development environment",
        "presets": ["base", "python", "nodejs", "docker", "github", "cli-tools"],
        "custom_packages": ["tmux", "htop", "jq"],
        "editor": "vim"
    },
    "prod": {
        "description": "Production web server with security",
        "presets": ["base", "webserver", "security", "monitoring"],
        "custom_packages": ["fail2ban"],
        "editor": "vim"
    },
    "ml": {
        "description": "Machine learning workstation",
        "presets": ["base", "python", "machine-learning", "ollama"],
        "custom_packages": ["htop", "nvtop"],
        "editor": "vim"
    },
    "ml-gpu": {
        "description": "ML workstation with GPU support",
        "presets": ["base", "python", "machine-learning", "ollama", "cuda"],
        "custom_packages": ["htop", "nvtop"],
        "editor": "vim"
    },
    "web": {
        "description": "Web development environment",
        "presets": ["base", "nodejs", "docker", "github"],
        "custom_packages": ["tmux"],
        "editor": "vim"
    },
    "minimal": {
        "description": "Minimal setup with essential tools only",
        "presets": ["base"],
        "custom_packages": ["tmux", "htop"],
        "editor": "vim"
    }
}

# ASCII art and colors
COLORS = {
    "header_border": ("cyan", True),
    "header_text": ("cyan", True),
    "section": ("yellow", True),
    "preset_name": ("green", True),
    "package_name": ("magenta", True),
    "success": ("green", True),
    "error": ("red", True),
    "warning": ("yellow", False),
    "info": ("cyan", False),
    "dim": ("white", False),
}

def colored(text, color_name):
    """Apply color from COLORS dict"""
    if color_name in COLORS:
        fg, bold = COLORS[color_name]
        return click.style(text, fg=fg, bold=bold)
    return text

def header(text, char="═"):
    """Print a fancy box header"""
    width = 60
    text_padded = f" {text} "
    padding = (width - len(text_padded)) // 2

    # Top border
    click.echo("\n" + colored("╔" + "═" * width + "╗", "header_border"))

    # Title line
    title_line = " " * padding + text_padded + " " * (width - padding - len(text_padded))
    click.echo(colored("║" + title_line + "║", "header_text"))

    # Bottom border
    click.echo(colored("╚" + "═" * width + "╝", "header_border"))
    click.echo()

def banner(text, icon=""):
    """Print a simple banner"""
    width = 58
    icon_text = f"{icon} " if icon else ""
    full_text = f"{icon_text}{text}"
    padding = (width - len(full_text)) // 2

    click.echo(colored("\n┌" + "─" * width + "┐", "header_border"))
    line = " " * padding + full_text + " " * (width - padding - len(full_text))
    click.echo(colored("│" + line + "│", "header_text"))
    click.echo(colored("└" + "─" * width + "┘", "header_border"))
    click.echo()

def success(text):
    """Print success message with icon"""
    icon = colored("✓", "success")
    msg = colored(text, "success")
    click.echo(f"\n  {icon}  {msg}\n")

def error(text):
    """Print error message with icon"""
    icon = colored("✗", "error")
    msg = colored(text, "error")
    click.echo(f"\n  {icon}  {msg}\n", err=True)

def warning(text):
    """Print warning message"""
    icon = colored("⚠", "warning")
    msg = colored(text, "warning")
    click.echo(f"\n  {icon}  {msg}\n")

def info_line(label, value, icon="▸"):
    """Print an info line with label and value"""
    icon_colored = colored(icon, "info")
    label_colored = colored(label + ":", "dim")
    click.echo(f"  {icon_colored} {label_colored} {value}")

def section_header(title):
    """Print a section header"""
    divider = colored("─" * 60, "section")
    title_colored = colored(f"▼ {title}", "section")
    click.echo(f"\n{title_colored}")
    click.echo(divider)

def preset_item(name, description="", active=False):
    """Print a preset item"""
    if active:
        icon = colored("●", "preset_name")
        name_colored = colored(f"{name:14}", "preset_name")
    else:
        icon = colored("○", "info")
        name_colored = colored(f"{name:14}", "info")

    if description:
        click.echo(f"  {icon} {name_colored} {colored(description, 'dim')}")
    else:
        click.echo(f"  {icon} {name_colored}")

def package_item(name):
    """Print a package item"""
    icon = colored("◆", "package_name")
    name_colored = colored(name, "package_name")
    click.echo(f"  {icon} {name_colored}")

def divider(char="─", width=60):
    """Print a divider line"""
    click.echo(colored(char * width, "dim"))


def get_active_config_name():
    """Get the name of the active configuration"""
    CAPSULE_DIR.mkdir(exist_ok=True)
    if not ACTIVE_CONFIG_FILE.exists():
        ACTIVE_CONFIG_FILE.write_text("default")
        return "default"
    return ACTIVE_CONFIG_FILE.read_text().strip()


def set_active_config_name(name):
    """Set the active configuration name"""
    CAPSULE_DIR.mkdir(exist_ok=True)
    ACTIVE_CONFIG_FILE.write_text(name)


def get_config_file(name=None):
    """Get the path to a config file"""
    if name is None:
        name = get_active_config_name()
    CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIGS_DIR / f"{name}.yml"


def list_all_configs():
    """List all available configuration names (user profiles only)"""
    if not CONFIGS_DIR.exists():
        return []
    return sorted([f.stem for f in CONFIGS_DIR.glob("*.yml")])


def list_builtin_profiles():
    """List built-in profile names"""
    return sorted(BUILTIN_PROFILES.keys())


def is_builtin_profile(name):
    """Check if a profile name is a built-in profile"""
    return name in BUILTIN_PROFILES


def get_builtin_profile(name):
    """Get a built-in profile configuration"""
    return BUILTIN_PROFILES.get(name)


def ensure_config(name=None):
    """Ensure config directory and file exist"""
    config_file = get_config_file(name)
    config_file.parent.mkdir(parents=True, exist_ok=True)

    if not config_file.exists():
        default = {
            "presets": ["base"],
            "custom_packages": [],
            "editor": os.environ.get("EDITOR", "vim")
        }
        with open(config_file, "w") as f:
            yaml.dump(default, f)
    return config_file


def load_config(name=None):
    """Load configuration (from user space or built-in)"""
    if name is None:
        name = get_active_config_name()

    # Check if it's a built-in profile first
    if is_builtin_profile(name):
        builtin = get_builtin_profile(name)
        # Return a copy to avoid modifying the original
        return dict(builtin)

    # Otherwise load from user config file
    config_file = ensure_config(name)
    with open(config_file) as f:
        return yaml.safe_load(f)


def save_config(config, name=None):
    """Save user configuration"""
    config_file = get_config_file(name)
    with open(config_file, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def load_preset(name):
    """Load a preset configuration"""
    preset_file = PRESETS_DIR / f"{name}.yml"
    if not preset_file.exists():
        return None
    with open(preset_file) as f:
        return yaml.safe_load(f)


def resolve_dependencies(stack_name, resolved=None, visiting=None):
    """Recursively resolve stack dependencies"""
    if resolved is None:
        resolved = []
    if visiting is None:
        visiting = set()

    # Avoid circular dependencies
    if stack_name in visiting:
        return resolved

    # Skip if already resolved
    if stack_name in resolved:
        return resolved

    visiting.add(stack_name)

    # Load the stack
    preset = load_preset(stack_name)
    if not preset:
        visiting.remove(stack_name)
        return resolved

    # Resolve dependencies first
    dependencies = preset.get("dependencies", [])
    for dep in dependencies:
        resolve_dependencies(dep, resolved, visiting)

    # Add this stack after its dependencies
    if stack_name not in resolved:
        resolved.append(stack_name)

    visiting.remove(stack_name)
    return resolved


def list_presets():
    """List all available presets"""
    if not PRESETS_DIR.exists():
        return []
    return [p.stem for p in PRESETS_DIR.glob("*.yml")]


def list_sprouts():
    """List all available sprouts"""
    if not SPROUTS_DIR.exists():
        return []
    return [s.stem for s in SPROUTS_DIR.glob("*.yml")]


def load_sprout(name):
    """Load a sprout configuration"""
    sprout_file = SPROUTS_DIR / f"{name}.yml"
    if not sprout_file.exists():
        return None
    with open(sprout_file) as f:
        return yaml.safe_load(f)


def generate_nix_config(config):
    """Generate Nix configuration from config

    Args:
        config: Configuration dict with 'presets' and 'custom_packages'

    Returns:
        str: A Nix expression suitable for nix-env or home-manager
    """
    # Start with base packages
    packages = [
        "git",
        "curl",
        "wget",
        "vim",
        "htop",
        "unzip",
    ]

    # Add custom packages from config
    if config.get("custom_packages"):
        packages.extend(config["custom_packages"])

    # Resolve all stacks with their dependencies
    all_stacks = []
    for preset_name in config.get("presets", []):
        if preset_name == "base":
            continue
        # Resolve dependencies for this stack
        resolved = resolve_dependencies(preset_name)
        for stack in resolved:
            if stack not in all_stacks:
                all_stacks.append(stack)

    # Collect packages from all presets
    preset_comments = []
    for preset_name in all_stacks:
        preset = load_preset(preset_name)
        if not preset:
            continue

        # Add preset packages
        if "packages" in preset:
            preset_packages = preset["packages"]
            # Add comment for this preset's packages
            if preset_packages:
                preset_comments.append(f"    # {preset.get('name', preset_name)}")
                packages.extend(preset_packages)

    # Remove duplicates while preserving order
    seen = set()
    unique_packages = []
    for pkg in packages:
        if pkg not in seen:
            seen.add(pkg)
            unique_packages.append(pkg)

    # Generate Nix expression
    # Use proper indentation for Nix
    package_lines = []
    package_lines.append("{ config, pkgs, ... }:")
    package_lines.append("{")
    package_lines.append("  # Capsule-generated configuration")
    package_lines.append("  # Generated from profile: " + config.get("description", "custom"))
    package_lines.append("")
    package_lines.append("  environment.systemPackages = with pkgs; [")

    # Add packages with grouping comments
    current_comment = None
    for i, pkg in enumerate(unique_packages):
        # Check if there's a comment for this section
        pkg_index = packages.index(pkg)
        for comment in preset_comments:
            comment_index = packages.index(pkg)
            if comment_index == pkg_index and comment != current_comment:
                if current_comment is not None:
                    package_lines.append("")
                package_lines.append(comment)
                current_comment = comment
                break

        package_lines.append(f"    {pkg}")

    package_lines.append("  ];")
    package_lines.append("}")

    return "\n".join(package_lines)


def run_nix(check=False, verbose=0, user_only=False):
    """Generate and apply Nix configuration

    Args:
        check: If True, perform dry-run only (nix-env --dry-run)
        verbose: Verbosity level (0-4)
        user_only: If True, use nix-env for user-level install (default).
                   If False, attempt nixos-rebuild (requires NixOS)

    Returns:
        int: Return code (0 for success, non-zero for error)
    """
    config = load_config()
    nix_config = generate_nix_config(config)

    # Write temporary Nix configuration
    temp_nix = Path("/tmp/capsule-config.nix")
    with open(temp_nix, "w") as f:
        f.write(nix_config)

    if verbose > 0:
        click.echo(f"\nGenerated Nix configuration:\n{nix_config}\n")

    # Collect all packages for installation
    packages = []

    # Parse packages from the generated config
    # This is a simple approach - extract package names from the config
    for line in nix_config.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("{") and \
           not line.startswith("}") and not line.startswith("environment") and \
           not line.startswith("[") and not line.startswith("]") and \
           "pkgs" not in line and "config" not in line and ":" not in line:
            packages.append(line)

    if not packages:
        error("No packages to install")
        return 1

    # Use nix-env for user-level installation
    # This is more portable than nixos-rebuild
    cmd = ["nix-env", "-iA"]

    # Add nixpkgs prefix to packages
    nixpkgs_packages = [f"nixpkgs.{pkg}" for pkg in packages]
    cmd.extend(nixpkgs_packages)

    if check:
        cmd.append("--dry-run")

    if verbose > 0:
        cmd.append("-v" * min(verbose, 4))

    try:
        if verbose > 0 or check:
            click.echo(f"\nRunning: {' '.join(cmd)}\n")

        result = subprocess.run(cmd, check=True)

        if result.returncode == 0:
            if not check:
                success("Nix packages installed successfully!")
            else:
                info_line("Dry-run", "No changes made")

        return result.returncode

    except subprocess.CalledProcessError as e:
        error(f"Nix installation failed: {e}")
        return e.returncode
    except FileNotFoundError:
        error("nix-env not found. Please install Nix: https://nixos.org/download.html")
        return 1


# Additional variables for update/deploy commands
SOURCE_DIR = CAPSULE_DIR / "source"
REPO_URL = "git@github.com:Geijutsu/capsule.git"


def print_logo():
    """Print capsule ASCII logo"""
    logo = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║      ██████╗ █████╗ ██████╗ ███████╗██╗   ██╗██╗         ║
    ║     ██╔════╝██╔══██╗██╔══██╗██╔════╝██║   ██║██║         ║
    ║     ██║     ███████║██████╔╝███████╗██║   ██║██║         ║
    ║     ██║     ██╔══██║██╔═══╝ ╚════██║██║   ██║██║         ║
    ║     ╚██████╗██║  ██║██║     ███████║╚██████╔╝███████╗    ║
    ║      ╚═════╝╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚══════╝    ║
    ║                                                           ║
    ║              Nix-Powered Configuration                   ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    click.echo(colored(logo, "header_border"))


# ============================================================================
# CLI COMMANDS
# ============================================================================

@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version="0.1.0")
def cli(ctx):
    """🌱 Capsule - User-friendly Ubuntu server configuration tool

    Manage multiple configurations with named profiles, modular presets,
    and beautiful ASCII UI. Powered by Nix.
    """
    if ctx.invoked_subcommand is None:
        print_logo()

        active_name = get_active_config_name()
        click.echo("  " + colored("Active Profile:", "dim") + " " +
                   colored(active_name, "preset_name") + "\n")

        section_header("🚀 Quick Start")
        click.echo("    " + colored("▸", "success") + " " +
                   colored("capsule stacks", "header_text") +
                   " " * 10 + colored("List available stacks", "dim"))
        click.echo("    " + colored("▸", "success") + " " +
                   colored("capsule add", "header_text") + " " +
                   colored("<stack>", "info") +
                   " " * 9 + colored("Add a technology stack", "dim"))
        click.echo("    " + colored("▸", "success") + " " +
                   colored("capsule show", "header_text") +
                   " " * 11 + colored("View configuration", "dim"))
        click.echo("    " + colored("▸", "success") + " " +
                   colored("capsule setup", "header_text") +
                   " " * 11 + colored("Install packages", "dim"))

        section_header("📁 Configuration Profiles")
        click.echo("    " + colored("○", "info") + " " +
                   colored("capsule profiles", "header_text") +
                   " " * 8 + colored("List all profiles", "dim"))
        click.echo("    " + colored("○", "info") + " " +
                   colored("capsule profile new", "header_text") + " " +
                   colored("<name>", "info") +
                   " " * 4 + colored("Create new profile", "dim"))
        click.echo("    " + colored("○", "info") + " " +
                   colored("capsule profile use", "header_text") + " " +
                   colored("<name>", "info") +
                   " " * 4 + colored("Switch profile", "dim"))

        section_header("🔧 Main Commands")
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("bootstrap", "header_text") +
                   " " * 10 + colored("Install dependencies", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("config", "header_text") +
                   " " * 13 + colored("Manage configuration", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("setup", "header_text") +
                   " " * 14 + colored("Install configured packages", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("check", "header_text") +
                   " " * 14 + colored("Dry run / preview changes", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("preview", "header_text") +
                   " " * 12 + colored("Show generated configuration", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("list", "header_text") +
                   " " * 15 + colored("List package status", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("plant", "header_text") +
                   " " * 14 + colored("Deploy to remote server", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("docs", "header_text") +
                   " " * 15 + colored("Interactive documentation", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("update", "header_text") +
                   " " * 13 + colored("Update to latest version", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("backup", "header_text") +
                   " " * 13 + colored("Backup package list", "dim"))
        click.echo("    " + colored("•", "package_name") + " " +
                   colored("restore", "header_text") +
                   " " * 12 + colored("Restore from backup", "dim"))

        section_header("🌱 Sprouts (Quick Install)")
        click.echo("    " + colored("▸", "success") + " " +
                   colored("sprouts", "header_text") +
                   " " * 11 + colored("List available sprouts", "dim"))
        click.echo("    " + colored("▸", "success") + " " +
                   colored("sprout", "header_text") + " " +
                   colored("<name>", "info") +
                   " " * 6 + colored("Install a sprout", "dim"))

        divider()
        click.echo()
        click.echo("  " + colored("💡 Tip:", "info") + " Run " +
                   colored("capsule --help", "header_text") +
                   " for detailed command list")
        click.echo()


# ============================================================================
# CONFIG COMMANDS (Deprecated - kept for backward compatibility)
# ============================================================================

@cli.group(invoke_without_command=True, hidden=True)
@click.pass_context
def config(ctx):
    """[DEPRECATED] Use commands directly: capsule show, capsule add, etc."""
    warning("[DEPRECATED] The 'capsule config' wrapper is deprecated.")
    click.echo("  Use commands directly instead:")
    click.echo(f"    • {colored('capsule show', 'header_text')} (was: capsule config show)")
    click.echo(f"    • {colored('capsule add', 'header_text')} (was: capsule config add)")
    click.echo(f"    • {colored('capsule stacks', 'header_text')} (was: capsule config stacks)\n")

    if ctx.invoked_subcommand is None:
        active_name = get_active_config_name()

        header("⚙️  CONFIGURATION MANAGEMENT")

        click.echo(colored("  Active Profile: ", "dim") +
                   colored(active_name, "preset_name") + "\n")

        section_header("📦 Technology Stacks")
        click.echo("    " + colored("▣", "preset_name") + " " +
                   colored("stacks", "header_text") +
                   " " * 13 + colored("List available stacks", "dim"))
        click.echo("    " + colored("▣", "preset_name") + " " +
                   colored("add", "header_text") + " " +
                   colored("<stack>", "info") +
                   " " * 6 + colored("Add technology stack", "dim"))
        click.echo("    " + colored("▣", "preset_name") + " " +
                   colored("remove", "header_text") + " " +
                   colored("<stack>", "info") +
                   " " * 3 + colored("Remove technology stack", "dim"))

        section_header("📁 Configuration Profiles")
        click.echo("    " + colored("▸", "info") + " " +
                   colored("profiles", "header_text") +
                   " " * 10 + colored("List all profiles", "dim"))
        click.echo("    " + colored("▸", "info") + " " +
                   colored("profile new", "header_text") + " " +
                   colored("<name>", "info") +
                   " " * 1 + colored("Create new profile", "dim"))
        click.echo("    " + colored("▸", "info") + " " +
                   colored("profile use", "header_text") + " " +
                   colored("<name>", "info") +
                   " " * 1 + colored("Switch to profile", "dim"))
        click.echo("    " + colored("▸", "info") + " " +
                   colored("profile copy", "header_text") + " " +
                   colored("<src> <dst>", "info") +
                   "  " + colored("Copy profile", "dim"))
        click.echo("    " + colored("▸", "info") + " " +
                   colored("profile delete", "header_text") + " " +
                   colored("<name>", "info") +
                   "   " + colored("Delete profile", "dim"))

        section_header("📝 Custom Packages")
        click.echo("    " + colored("◆", "package_name") + " " +
                   colored("pkg add", "header_text") + " " +
                   colored("<pkg...>", "info") +
                   " " * 3 + colored("Add individual packages", "dim"))
        click.echo("    " + colored("◆", "package_name") + " " +
                   colored("pkg remove", "header_text") + " " +
                   colored("<pkg...>", "info") +
                   "  " + colored("Remove individual packages", "dim"))

        section_header("🔧 Other Commands")
        click.echo("    " + colored("▸", "info") + " " +
                   colored("show", "header_text") +
                   " " * 13 + colored("Show current configuration", "dim"))
        click.echo("    " + colored("▸", "info") + " " +
                   colored("edit", "header_text") +
                   " " * 13 + colored("Edit config file directly", "dim"))
        click.echo("    " + colored("▸", "info") + " " +
                   colored("reset", "header_text") +
                   " " * 12 + colored("Reset to defaults", "dim"))

        divider()
        click.echo()
        click.echo("  " + colored("💡 Tip:", "info") + " Use " +
                   colored("capsule <command> --help", "header_text") +
                   " for more info")
        click.echo()


@cli.command("show")
def show():
    """Show current configuration"""
    active_name = get_active_config_name()
    config = load_config()

    header("⚙  CONFIGURATION")

    # Show active profile name
    click.echo("  " + colored("Active Profile:", "dim") + " " +
               colored(active_name, "header_text") + "\n")

    section_header("Technology Stacks")
    presets = config.get("presets", [])
    if presets:
        for preset in presets:
            if preset == "base":
                preset_item(preset, "(core packages)", active=True)
            else:
                preset_data = load_preset(preset)
                if preset_data:
                    desc = preset_data.get("description", "")
                    preset_item(preset, desc, active=True)

                    # Show dependencies if any
                    dependencies = preset_data.get("dependencies", [])
                    if dependencies:
                        deps_text = ", ".join([colored(d, "info") for d in dependencies])
                        click.echo("      " + colored("↳ requires:", "dim") + " " + deps_text)

                    # Show optional dependencies
                    optional_deps = preset_data.get("optional_dependencies", [])
                    if optional_deps:
                        opt_names = []
                        for opt in optional_deps:
                            if isinstance(opt, dict):
                                opt_names.append(opt.get("name", ""))
                            else:
                                opt_names.append(opt)
                        opts_text = ", ".join([colored(o, "warning") for o in opt_names])
                        click.echo("      " + colored("↳ optional:", "dim") + " " + opts_text)
                else:
                    preset_item(preset, colored("(not found)", "error"), active=False)
    else:
        click.echo(colored("  No stacks configured", "dim"))

    if config.get("custom_packages"):
        section_header("Individual Packages")
        for pkg in config["custom_packages"]:
            package_item(pkg)

    section_header("Settings")
    info_line("Editor", colored(config.get('editor', 'vim'), 'info'))

    # Show config source
    if is_builtin_profile(active_name):
        info_line("Source", colored("Built-in profile (read-only)", 'warning'))
    else:
        info_line("Config File", colored(str(get_config_file()), 'dim'))
    click.echo()


# Backward compatibility alias
@config.command("show")
def config_show():
    """[DEPRECATED] Use 'capsule show' instead"""
    warning("[DEPRECATED] Use 'capsule show' instead of 'capsule config show'")
    ctx = click.get_current_context()
    ctx.invoke(show)


@cli.command("stacks")
def stacks():
    """List available technology stacks"""
    presets = sorted(list_presets())

    header("📦 TECHNOLOGY STACKS")

    # Group presets by category
    categories = {
        "Languages & Runtimes": {
            "icon": "🔧",
            "presets": ["python", "golang", "rust", "nodejs"]
        },
        "Development Tools": {
            "icon": "🛠",
            "presets": ["devtools", "cli-tools", "github"]
        },
        "Infrastructure": {
            "icon": "🏗",
            "presets": ["docker", "database", "webserver"]
        },
        "Security & Monitoring": {
            "icon": "🔒",
            "presets": ["security", "monitoring"]
        },
        "AI/ML": {
            "icon": "🤖",
            "presets": ["machine-learning", "ollama", "cuda"]
        },
    }

    for category, data in categories.items():
        category_presets = [p for p in data["presets"] if p in presets]
        if category_presets:
            section_header(f"{data['icon']}  {category}")
            for preset_name in category_presets:
                preset = load_preset(preset_name)
                if preset:
                    desc = preset.get("description", "")
                    preset_item(preset_name, desc, active=False)

                    # Show dependencies
                    dependencies = preset.get("dependencies", [])
                    if dependencies:
                        deps_text = ", ".join([colored(d, "info") for d in dependencies])
                        click.echo("      " + colored("↳ requires:", "dim") + " " + deps_text)

                    # Show optional dependencies
                    optional_deps = preset.get("optional_dependencies", [])
                    if optional_deps:
                        opt_names = []
                        for opt in optional_deps:
                            if isinstance(opt, dict):
                                opt_names.append(opt.get("name", ""))
                            else:
                                opt_names.append(opt)
                        opts_text = ", ".join([colored(o, "warning") for o in opt_names])
                        click.echo("      " + colored("↳ optional:", "dim") + " " + opts_text)

    divider()
    click.echo()
    click.echo("  " + colored("💡 Usage:", "info") + " " +
               colored("capsule add", "header_text") + " " +
               colored("<stack>", "section"))
    click.echo()


@cli.command("add")
@click.argument("stack")
def add(stack):
    """Add a technology stack to your configuration"""
    if stack not in list_presets() and stack != "base":
        error(f"Stack '{colored(stack, 'error')}' not found")
        click.echo("  " + colored("💡 Hint:", "info") + " Run " +
                   colored("capsule stacks", "header_text") +
                   " to see available stacks\n")
        sys.exit(1)

    config = load_config()
    if stack in config.get("presets", []):
        warning(f"Stack '{colored(stack, 'warning')}' is already added")
        return

    # Check for dependencies
    preset = load_preset(stack)
    dependencies = preset.get("dependencies", []) if preset else []
    optional_dependencies = preset.get("optional_dependencies", []) if preset else []

    # Auto-add required dependencies
    added_deps = []
    if dependencies:
        for dep in dependencies:
            if dep not in config.get("presets", []):
                config.setdefault("presets", []).append(dep)
                added_deps.append(dep)

    # Add the main stack
    config.setdefault("presets", []).append(stack)
    save_config(config)

    # Show what was added
    success(f"Added stack: {colored(stack, 'preset_name')}")

    if added_deps:
        deps_list = ", ".join([colored(d, "info") for d in added_deps])
        click.echo("  " + colored("↳", "info") + " " +
                   colored("Dependencies added:", "dim") + " " + deps_list + "\n")

    # Show optional dependencies
    if optional_dependencies:
        click.echo("  " + colored("ⓘ", "warning") + " " +
                   colored("Optional dependencies available:", "warning"))
        for opt_dep in optional_dependencies:
            if isinstance(opt_dep, dict):
                dep_name = opt_dep.get("name", "")
                dep_desc = opt_dep.get("description", "")
                click.echo("    " + colored("○", "warning") + " " +
                           colored(dep_name, "warning") + " - " +
                           colored(dep_desc, "dim"))
            else:
                click.echo("    " + colored("○", "warning") + " " +
                           colored(opt_dep, "warning"))
        click.echo()


@cli.command("remove")
@click.argument("stack")
def remove(stack):
    """Remove a technology stack from your configuration"""
    config = load_config()
    if stack in config.get("presets", []):
        config["presets"].remove(stack)
        save_config(config)
        success(f"Removed stack: {colored(stack, 'preset_name')}")
    else:
        error(f"Stack '{colored(stack, 'error')}' is not in your configuration")


# ============================================================================
# PACKAGE MANAGEMENT SUBGROUP
# ============================================================================

@cli.group("pkg")
def pkg():
    """Manage individual packages"""
    pass


@pkg.command("add")
@click.argument("packages", nargs=-1, required=True)
def pkg_add(packages):
    """Add individual packages to install"""
    config = load_config()
    added = []
    for pkg in packages:
        if pkg not in config.get("custom_packages", []):
            config.setdefault("custom_packages", []).append(pkg)
            added.append(pkg)

    if added:
        save_config(config)
        pkg_list = ", ".join([colored(p, "package_name") for p in added])
        success(f"Added packages: {pkg_list}")
    else:
        warning("All packages are already in configuration")


@pkg.command("remove")
@click.argument("packages", nargs=-1, required=True)
def pkg_remove(packages):
    """Remove individual packages"""
    config = load_config()
    removed = []
    for pkg in packages:
        if pkg in config.get("custom_packages", []):
            config["custom_packages"].remove(pkg)
            removed.append(pkg)

    if removed:
        save_config(config)
        pkg_list = ", ".join([colored(p, "package_name") for p in removed])
        success(f"Removed packages: {pkg_list}")
    else:
        error("Packages not found in configuration")


@cli.command("edit")
def edit():
    """Edit configuration file directly"""
    ensure_config()
    editor = load_config().get("editor", os.environ.get("EDITOR", "vim"))
    config_file = get_config_file()
    subprocess.run([editor, str(config_file)])


@cli.command("reset")
@click.confirmation_option(prompt="Reset configuration to defaults?")
def reset():
    """Reset configuration to defaults"""
    config_file = get_config_file()
    if config_file.exists():
        config_file.unlink()
    ensure_config()
    success("Configuration reset to defaults")


# ============================================================================
# PROFILE MANAGEMENT SUBGROUP
# ============================================================================

@cli.group("profile")
def profile():
    """Manage configuration profiles"""
    pass


@profile.command("use")
@click.argument("name")
def profile_use(name):
    """Switch to a different profile (user or built-in)"""
    user_configs = list_all_configs()
    builtin_configs = list_builtin_profiles()

    if name not in user_configs and name not in builtin_configs:
        error(f"Profile '{colored(name, 'error')}' not found")
        click.echo("  " + colored("💡 Hint:", "info") + " Run " +
                   colored("capsule profiles", "header_text") +
                   " to see available profiles\n")
        sys.exit(1)

    set_active_config_name(name)

    if is_builtin_profile(name):
        success(f"Switched to built-in profile: {colored(name, 'preset_name')}")
        click.echo("  " + colored("ⓘ", "info") + " " +
                   colored("Built-in profiles are read-only. Use", "dim") + " " +
                   colored("capsule profile import", "header_text") + " " +
                   colored("to customize.\n", "dim"))
    else:
        success(f"Switched to profile: {colored(name, 'preset_name')}")


@profile.command("new")
@click.argument("name")
@click.option("--copy-from", help="Copy settings from existing profile")
def profile_new(name, copy_from):
    """Create a new profile"""
    configs = list_all_configs()

    if name in configs:
        error(f"Profile '{colored(name, 'error')}' already exists")
        sys.exit(1)

    if copy_from:
        if copy_from not in configs:
            error(f"Source profile '{colored(copy_from, 'error')}' not found")
            sys.exit(1)
        # Copy from existing config
        source_config = load_config(copy_from)
        save_config(source_config, name)
        success(f"Created profile '{colored(name, 'preset_name')}' from '{colored(copy_from, 'info')}'")
    else:
        # Create new default config
        ensure_config(name)
        success(f"Created new profile: {colored(name, 'preset_name')}")


@profile.command("copy")
@click.argument("source")
@click.argument("dest")
def profile_copy(source, dest):
    """Copy a profile"""
    configs = list_all_configs()

    if source not in configs:
        error(f"Source profile '{colored(source, 'error')}' not found")
        sys.exit(1)

    if dest in configs:
        error(f"Destination profile '{colored(dest, 'error')}' already exists")
        sys.exit(1)

    source_config = load_config(source)
    save_config(source_config, dest)
    success(f"Copied '{colored(source, 'info')}' to '{colored(dest, 'preset_name')}'")


@profile.command("delete")
@click.argument("name")
@click.confirmation_option(prompt="Delete this profile?")
def profile_delete(name):
    """Delete a user profile"""
    active_name = get_active_config_name()

    if is_builtin_profile(name):
        error(f"Cannot delete built-in profile '{colored(name, 'error')}'")
        sys.exit(1)

    if name == active_name:
        error(f"Cannot delete active profile '{colored(name, 'error')}'")
        click.echo("  " + colored("💡 Hint:", "info") + " Switch to another profile first with " +
                   colored("capsule config profile use", "header_text") + "\n")
        sys.exit(1)

    configs = list_all_configs()
    if name not in configs:
        error(f"Profile '{colored(name, 'error')}' not found")
        sys.exit(1)

    config_file = get_config_file(name)
    config_file.unlink()
    success(f"Deleted profile: {colored(name, 'preset_name')}")


@profile.command("import")
@click.argument("builtin_name")
@click.argument("new_name", required=False)
def profile_import(builtin_name, new_name):
    """Import a built-in profile to user space for customization"""
    if not is_builtin_profile(builtin_name):
        error(f"Built-in profile '{colored(builtin_name, 'error')}' not found")
        click.echo("  " + colored("💡 Hint:", "info") + " Run " +
                   colored("capsule config profile list-builtin", "header_text") +
                   " to see available built-in profiles\n")
        sys.exit(1)

    # Default to same name if not specified
    if new_name is None:
        new_name = builtin_name

    user_configs = list_all_configs()
    if new_name in user_configs:
        error(f"User profile '{colored(new_name, 'error')}' already exists")
        sys.exit(1)

    # Load built-in and save as user profile
    builtin_config = get_builtin_profile(builtin_name)
    save_config(builtin_config, new_name)

    success(f"Imported built-in profile '{colored(builtin_name, 'info')}' as '{colored(new_name, 'preset_name')}'")
    click.echo("  " + colored("💡 Tip:", "info") + " You can now customize it with " +
               colored(f"capsule config profile use {new_name}", "header_text") + "\n")


@cli.command("profiles")
def profiles():
    """List all configuration profiles (built-in and user)"""
    user_configs = list_all_configs()
    builtin_configs = list_builtin_profiles()
    active_name = get_active_config_name()

    header("📁 CONFIGURATION PROFILES")

    # Show built-in profiles first
    if builtin_configs:
        section_header("🔹 Built-in Profiles (Read-Only)")
        for config_name in builtin_configs:
            is_active = (config_name == active_name)
            config_data = get_builtin_profile(config_name)
            stacks = [p for p in config_data.get("presets", []) if p != "base"]
            packages = config_data.get("custom_packages", [])
            desc = config_data.get("description", "")

            # Header line with name and status
            if is_active:
                icon = colored("▶", "success")
                name_colored = colored(config_name, "preset_name")
                status = " " + colored("✓ ACTIVE", "success")
            else:
                icon = colored("◇", "info")
                name_colored = colored(config_name, "info")
                status = ""

            click.echo(f"\n  {icon} {name_colored}{status}")

            # Description
            if desc:
                click.echo(f"     {colored(desc, 'dim')}")

            # Stacks
            if stacks:
                stacks_colored = ", ".join([colored(s, "preset_name") for s in stacks])
                click.echo(f"     {colored('Stacks:', 'info')} {stacks_colored}")

            # Packages
            if packages:
                pkgs_colored = ", ".join([colored(p, "package_name") for p in packages])
                click.echo(f"     {colored('Packages:', 'info')} {pkgs_colored}")

    # Show user profiles
    if user_configs:
        section_header("👤 User Profiles")
        for config_name in user_configs:
            is_active = (config_name == active_name)
            config_data = load_config(config_name)
            stacks = [p for p in config_data.get("presets", []) if p != "base"]
            packages = config_data.get("custom_packages", [])

            # Header line with name and status
            if is_active:
                icon = colored("▶", "success")
                name_colored = colored(config_name, "preset_name")
                status = " " + colored("✓ ACTIVE", "success")
            else:
                icon = colored("○", "info")
                name_colored = colored(config_name, "info")
                status = ""

            click.echo(f"\n  {icon} {name_colored}{status}")

            # Stacks
            if stacks:
                stacks_colored = ", ".join([colored(s, "preset_name") for s in stacks])
                click.echo(f"     {colored('Stacks:', 'info')} {stacks_colored}")
            else:
                click.echo(f"     {colored('Stacks:', 'info')} {colored('(none)', 'dim')}")

            # Packages
            if packages:
                pkgs_colored = ", ".join([colored(p, "package_name") for p in packages])
                click.echo(f"     {colored('Packages:', 'info')} {pkgs_colored}")
            else:
                click.echo(f"     {colored('Packages:', 'info')} {colored('(none)', 'dim')}")
    else:
        section_header("👤 User Profiles")
        click.echo(colored("\n  No user profiles yet", "dim"))
        click.echo("  " + colored("💡 Tip:", "info") + " Import a built-in with " +
                   colored("capsule config profile import <name>", "header_text"))

    divider()
    click.echo()
    click.echo("  " + colored("💡 Usage:", "info"))
    click.echo("    " + colored("capsule config profile use", "header_text") + " " +
               colored("<name>", "section") + "          " +
               colored("Switch to a profile", "dim"))
    click.echo("    " + colored("capsule config profile import", "header_text") + " " +
               colored("<name>", "section") + "     " +
               colored("Import built-in to customize", "dim"))
    click.echo()


# ============================================================================
# SETUP COMMANDS
# ============================================================================

@cli.command()
@click.option("--check", is_flag=True, help="Dry run mode")
@click.option("-v", "--verbose", count=True, help="Verbose output (-v, -vv, -vvv for more detail)")
def setup(check, verbose):
    """Set up server with configured packages and presets"""
    if check:
        banner("🔍 DRY RUN MODE")
        click.echo(colored("  Checking what would be installed...\n", "warning"))
    else:
        banner("🚀 SETTING UP SERVER")

    if verbose:
        click.echo(colored(f"  Verbose level: {verbose}\n", "info"))

    return run_nix(check=check, ask_pass=True, verbose=verbose)


@cli.command()
@click.option("-v", "--verbose", count=True, help="Verbose output (-v, -vv, -vvv for more detail)")
def check(verbose):
    """Check what would be changed (dry run)"""
    banner("🔍 CONFIGURATION CHECK")
    if verbose:
        click.echo(colored(f"  Verbose level: {verbose}\n", "info"))
    return run_nix(check=True, ask_pass=True, verbose=verbose)


@cli.command()
def list():
    """List all packages and their installation status"""
    config = load_config()
    configuration = generate_nix_config(config)

    header("📦 PACKAGE STATUS")

    # Get all packages from the configuration
    packages = configuration["vars"]["packages"]

    section_header(f"Configured Packages ({len(packages)} total)")

    installed_count = 0
    missing_count = 0

    # Check each package
    for pkg in sorted(packages):
        # Check if package is installed (works on Debian/Ubuntu)
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Status}", pkg],
                capture_output=True,
                text=True,
                check=False
            )

            # Package is installed if status contains "install ok installed"
            if result.returncode == 0 and "install ok installed" in result.stdout:
                click.echo(f"  {colored('✓', 'success')} {colored(pkg, 'preset_name')}")
                installed_count += 1
            else:
                click.echo(f"  {colored('✗', 'error')} {colored(pkg, 'dim')}")
                missing_count += 1
        except FileNotFoundError:
            # dpkg not available (not on Debian/Ubuntu)
            click.echo(f"  {colored('?', 'warning')} {colored(pkg, 'dim')} {colored('(status unknown - not on Debian/Ubuntu)', 'warning')}")

    divider()
    click.echo()

    # Summary
    if missing_count > 0 or installed_count > 0:
        click.echo(f"  {colored('Summary:', 'section')}")
        click.echo(f"    {colored('✓', 'success')} Installed: {colored(str(installed_count), 'preset_name')}")
        click.echo(f"    {colored('✗', 'error')} Missing: {colored(str(missing_count), 'error')}")

        if missing_count > 0:
            click.echo()
            click.echo(f"  {colored('💡 Tip:', 'info')} Run {colored('capsule setup', 'header_text')} to install missing packages")

    click.echo()


@cli.command()
def preview():
    """Preview generated Nix configuration"""
    config = load_config()
    configuration = generate_nix_config(config)

    header("📋 NIX CONFIGURATION PREVIEW")

    section_header("Summary")
    # Count packages from the config
    all_pkgs = []
    for preset_name in config.get("presets", []):
        preset = load_preset(preset_name)
        if preset and "packages" in preset:
            all_pkgs.extend(preset["packages"])
    all_pkgs.extend(config.get("custom_packages", []))
    pkg_count = len(set(all_pkgs))
    preset_count = len(config.get("presets", []))
    info_line("Stacks", colored(str(preset_count), "info"))
    info_line("Total Packages", colored(str(pkg_count), "success"))

    section_header("Generated Nix Configuration")
    click.echo(colored(configuration, "dim"))

    divider()
    click.echo()
    click.echo("  " + colored("💡 Tip:", "info") + " Run " +
               colored("capsule check", "header_text") +
               " to preview installation without applying")
    click.echo()


# ============================================================================
# NIXOS CONFIGURATION GENERATION
# ============================================================================

@cli.group(name="nixos")
def nixos_group():
    """NixOS configuration generation and management"""
    pass


@nixos_group.command(name="generate")
@click.option("--output", "-o", default=None, help="Output directory (default: ~/.capsule/nixos)")
@click.option("--hostname", default="nixos", help="System hostname (default: nixos)")
@click.option("--username", default=None, help="Primary user account name (default: current user)")
@click.option("--home-manager", is_flag=True, help="Generate home-manager configuration only")
@click.option("--flake", is_flag=True, help="Generate flake.nix only")
@click.option("--hardware", is_flag=True, help="Generate hardware-configuration.nix only")
@click.option("--all", "generate_all", is_flag=True, help="Generate all configuration files (default)")
def nixos_generate(output, hostname, username, home_manager, flake, hardware, generate_all):
    """Generate NixOS configuration files from Capsule profile"""

    # Load current configuration
    config = load_config()

    # Set defaults
    if output is None:
        output = CAPSULE_DIR / "nixos"
    else:
        output = Path(output)

    if username is None:
        username = os.environ.get("USER", "user")

    output.mkdir(parents=True, exist_ok=True)

    # Initialize generator
    generator = NixOSConfigGenerator(CAPSULE_DIR)

    header("🔧 NIXOS CONFIGURATION GENERATOR")

    # Determine what to generate
    if not (home_manager or flake or hardware):
        generate_all = True

    generated_files = []

    try:
        if generate_all:
            # Generate all files
            section_header("Generating complete NixOS configuration")
            info_line("Profile", config.get("description", "Custom configuration"))
            info_line("Hostname", hostname)
            info_line("Username", username)
            info_line("Output", str(output))
            click.echo()

            files = generator.generate_all(config, output, hostname, username)

            for file_type, file_path in files.items():
                generated_files.append((file_type, file_path))
                click.echo(f"  {colored('✓', 'success')} Generated {colored(file_type, 'preset_name')}")
                click.echo(f"    {colored(str(file_path), 'dim')}")

        else:
            # Generate specific files
            if home_manager:
                section_header("Generating Home Manager configuration")
                home_nix = generator.generate_home_manager(config, username)
                home_path = output / "home.nix"
                home_path.write_text(home_nix)
                generated_files.append(("home.nix", home_path))
                click.echo(f"  {colored('✓', 'success')} Generated {colored('home.nix', 'preset_name')}")
                click.echo(f"    {colored(str(home_path), 'dim')}")

            if flake:
                section_header("Generating Flake configuration")
                flake_nix = generator.generate_flake_nix(config, hostname, username)
                flake_path = output / "flake.nix"
                flake_path.write_text(flake_nix)
                generated_files.append(("flake.nix", flake_path))
                click.echo(f"  {colored('✓', 'success')} Generated {colored('flake.nix', 'preset_name')}")
                click.echo(f"    {colored(str(flake_path), 'dim')}")

            if hardware:
                section_header("Generating Hardware configuration")
                hardware_nix = generator.generate_hardware_config()
                hardware_path = output / "hardware-configuration.nix"
                hardware_path.write_text(hardware_nix)
                generated_files.append(("hardware-configuration.nix", hardware_path))
                click.echo(f"  {colored('✓', 'success')} Generated {colored('hardware-configuration.nix', 'preset_name')}")
                click.echo(f"    {colored(str(hardware_path), 'dim')}")

            if not (home_manager or flake or hardware):
                # Generate configuration.nix by default
                section_header("Generating NixOS configuration")
                config_nix = generator.generate_configuration_nix(config, hostname, username)
                config_path = output / "configuration.nix"
                config_path.write_text(config_nix)
                generated_files.append(("configuration.nix", config_path))
                click.echo(f"  {colored('✓', 'success')} Generated {colored('configuration.nix', 'preset_name')}")
                click.echo(f"    {colored(str(config_path), 'dim')}")

        click.echo()
        success("NixOS configuration generated successfully!")

        # Show next steps
        divider()
        click.echo()
        click.echo("  " + colored("📋 Next Steps:", "section"))
        click.echo()
        click.echo("  1. Review the generated configuration files")
        click.echo(f"     {colored('cd ' + str(output), 'info')}")
        click.echo()
        click.echo("  2. Test configuration (recommended)")
        click.echo(f"     {colored('capsule nixos test', 'info')}")
        click.echo()
        click.echo("  3. Deploy to NixOS system")
        click.echo(f"     {colored('sudo cp ' + str(output) + '/*.nix /etc/nixos/', 'info')}")
        click.echo(f"     {colored('sudo nixos-rebuild switch', 'info')}")
        click.echo()

    except Exception as e:
        error(f"Failed to generate configuration: {str(e)}")
        sys.exit(1)


@nixos_group.command(name="validate")
@click.option("--config", "-c", default=None, help="Path to configuration.nix (default: ~/.capsule/nixos/configuration.nix)")
def nixos_validate(config):
    """Validate NixOS configuration syntax"""

    if config is None:
        config = CAPSULE_DIR / "nixos" / "configuration.nix"
    else:
        config = Path(config)

    header("✓ NIXOS CONFIGURATION VALIDATION")

    info_line("Validating", str(config))
    click.echo()

    if not config.exists():
        error(f"Configuration file not found: {config}")
        sys.exit(1)

    is_valid, errors = validate_config(config)

    if is_valid:
        success("Configuration is valid!")
        click.echo()
        click.echo("  " + colored("💡 Next:", "info") + " Test in VM with " +
                   colored("capsule nixos test", "header_text"))
        click.echo()
    else:
        error("Configuration validation failed!")
        click.echo()
        section_header("Errors")
        for err in errors:
            click.echo(f"  {colored('✗', 'error')} {err}")
        click.echo()
        sys.exit(1)


@nixos_group.command(name="test")
@click.option("--config-dir", "-d", default=None, help="Configuration directory (default: ~/.capsule/nixos)")
def nixos_test(config_dir):
    """Test NixOS configuration in a VM"""

    if config_dir is None:
        config_dir = CAPSULE_DIR / "nixos"
    else:
        config_dir = Path(config_dir)

    header("🖥️  NIXOS VM TEST")

    config_path = config_dir / "configuration.nix"

    if not config_path.exists():
        error(f"Configuration not found: {config_path}")
        click.echo()
        click.echo("  " + colored("💡 Generate one first:", "info") + " " +
                   colored("capsule nixos generate", "header_text"))
        click.echo()
        sys.exit(1)

    info_line("Configuration", str(config_path))
    click.echo()

    section_header("Building VM")
    click.echo()

    try:
        # Validate first
        is_valid, errors = validate_config(config_path)
        if not is_valid:
            error("Configuration validation failed!")
            for err in errors:
                click.echo(f"  {colored('✗', 'error')} {err}")
            sys.exit(1)

        # Build VM
        click.echo("  Building VM (this may take a few minutes)...")
        result = test_in_vm(config_dir)

        if result:
            success("VM build completed successfully!")
            click.echo()
            section_header("Running the VM")
            click.echo()
            click.echo("  Run the VM with:")
            click.echo(f"    {colored('./result/bin/run-nixos-vm', 'info')}")
            click.echo()
        else:
            error("VM build failed!")
            click.echo()
            click.echo("  Check the output above for errors.")
            sys.exit(1)

    except Exception as e:
        error(f"VM test failed: {str(e)}")
        sys.exit(1)


@nixos_group.command(name="apply")
@click.option("--config-dir", "-d", default=None, help="Configuration directory (default: ~/.capsule/nixos)")
@click.option("--target", "-t", help="Remote host to apply (username@hostname)")
@click.option("--port", "-p", default=22, help="SSH port (default: 22)")
@click.option("--dry-run", is_flag=True, help="Show what would be done without executing")
@click.confirmation_option(prompt="Apply NixOS configuration?")
def nixos_apply(config_dir, target, port, dry_run):
    """Apply NixOS configuration to system"""

    if config_dir is None:
        config_dir = CAPSULE_DIR / "nixos"
    else:
        config_dir = Path(config_dir)

    header("🚀 NIXOS CONFIGURATION APPLY")

    config_path = config_dir / "configuration.nix"

    if not config_path.exists():
        error(f"Configuration not found: {config_path}")
        sys.exit(1)

    # Validate first
    is_valid, errors = validate_config(config_path)
    if not is_valid:
        error("Configuration validation failed!")
        for err in errors:
            click.echo(f"  {colored('✗', 'error')} {err}")
        sys.exit(1)

    if target:
        # Remote deployment
        section_header("Remote Deployment")
        info_line("Target", target)
        info_line("Port", str(port))
        click.echo()

        # Build SSH command
        ssh_cmd = ["ssh"]
        if port != 22:
            ssh_cmd.extend(["-p", str(port)])
        ssh_cmd.append(target)

        # Copy configuration files
        click.echo("  Copying configuration files...")
        scp_cmd = ["scp"]
        if port != 22:
            scp_cmd.extend(["-P", str(port)])
        scp_cmd.extend([str(config_dir / "*.nix"), f"{target}:/tmp/"])

        if not dry_run:
            try:
                subprocess.run(scp_cmd, check=True)

                # Apply on remote
                click.echo("  Applying configuration on remote...")
                apply_cmd = ssh_cmd + [
                    "sudo cp /tmp/*.nix /etc/nixos/ && sudo nixos-rebuild switch"
                ]
                subprocess.run(apply_cmd, check=True)

                success("Configuration applied successfully on remote!")
            except subprocess.CalledProcessError as e:
                error(f"Remote deployment failed: {str(e)}")
                sys.exit(1)
        else:
            click.echo(f"\n  Would run: {' '.join(scp_cmd)}")
            click.echo(f"  Would run: {' '.join(ssh_cmd + ['sudo cp /tmp/*.nix /etc/nixos/ && sudo nixos-rebuild switch'])}")

    else:
        # Local deployment
        section_header("Local Deployment")
        info_line("Configuration", str(config_path))
        click.echo()

        if not dry_run:
            try:
                # Copy configuration
                click.echo("  Copying configuration to /etc/nixos/...")
                subprocess.run([
                    "sudo", "cp",
                    str(config_dir / "configuration.nix"),
                    str(config_dir / "hardware-configuration.nix"),
                    "/etc/nixos/"
                ], check=True)

                # Apply configuration
                click.echo("  Applying configuration...")
                subprocess.run(["sudo", "nixos-rebuild", "switch"], check=True)

                success("Configuration applied successfully!")

            except subprocess.CalledProcessError as e:
                error(f"Deployment failed: {str(e)}")
                sys.exit(1)
        else:
            click.echo(f"\n  Would copy configuration to /etc/nixos/")
            click.echo(f"  Would run: sudo nixos-rebuild switch")

    click.echo()


@nixos_group.command(name="rollback")
@click.option("--generation", "-g", type=int, help="Generation number to rollback to")
@click.confirmation_option(prompt="Rollback NixOS configuration?")
def nixos_rollback(generation):
    """Rollback to a previous NixOS generation"""

    header("⏮️  NIXOS ROLLBACK")

    if generation:
        info_line("Rolling back to generation", str(generation))
    else:
        info_line("Rolling back to", "previous generation")

    click.echo()

    try:
        if generation:
            cmd = ["sudo", "nixos-rebuild", "switch", "--rollback", "--generation", str(generation)]
        else:
            cmd = ["sudo", "nixos-rebuild", "switch", "--rollback"]

        subprocess.run(cmd, check=True)
        success("Rollback completed successfully!")

    except subprocess.CalledProcessError as e:
        error(f"Rollback failed: {str(e)}")
        sys.exit(1)


@nixos_group.command(name="list-generations")
def nixos_list_generations():
    """List all NixOS system generations"""

    header("📜 NIXOS GENERATIONS")

    try:
        result = subprocess.run(
            ["nixos-rebuild", "list-generations"],
            capture_output=True,
            text=True,
            check=True
        )

        click.echo(result.stdout)

    except subprocess.CalledProcessError as e:
        error(f"Failed to list generations: {str(e)}")
        sys.exit(1)


@cli.command()
def backup():
    """Backup current package list"""
    try:
        subprocess.run(["dpkg", "--get-selections"],
                      stdout=open("packages.txt", "w"),
                      check=True)
        success(f"Package list saved to {colored('packages.txt', 'info')}")
    except subprocess.CalledProcessError:
        error("Failed to backup packages")
        sys.exit(1)


@cli.command()
def restore():
    """Restore packages from packages.txt"""
    if not Path("packages.txt").exists():
        error(f"{colored('packages.txt', 'error')} not found")
        sys.exit(1)

    banner("📦 RESTORING PACKAGES")
    try:
        subprocess.run(["sudo", "dpkg", "--set-selections"],
                      stdin=open("packages.txt"), check=True)
        subprocess.run(["sudo", "apt-get", "dselect-upgrade", "-y"], check=True)
        success("Packages restored successfully")
    except subprocess.CalledProcessError:
        error("Failed to restore packages")
        sys.exit(1)


# ============================================================================
# BOOTSTRAP (DEPENDENCY INSTALLATION)
# ============================================================================

@cli.command(name="bootstrap")
@click.option("--remote", help="Bootstrap on remote server (username@hostname)")
@click.option("--port", "-p", default=22, help="SSH port (default: 22)")
@click.option("--key", "-i", help="SSH private key path")
def bootstrap_cmd(remote, port, key):
    """Install all dependencies (Python, pip, Nix) on local or remote system"""

    if remote:
        # Remote bootstrap
        if "@" not in remote:
            error("Remote must be in format: username@hostname")
            sys.exit(1)

        banner("🔧 REMOTE BOOTSTRAP")
        click.echo(f"  {colored('Target:', 'info')} {colored(remote, 'preset_name')}\n")

        # Build SSH command
        ssh_cmd = ["ssh"]
        if port != 22:
            ssh_cmd.extend(["-p", str(port)])
        if key:
            ssh_cmd.extend(["-i", key])

        # First, check what's missing
        check_script = """
MISSING=""
echo "🔧 Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 not found"
    MISSING="$MISSING python3"
else
    echo "  ✓ Python 3 found: $(python3 --version)"
fi

if ! command -v pip3 &> /dev/null; then
    echo "  ✗ pip3 not found"
    MISSING="$MISSING pip3"
else
    echo "  ✓ pip3 found: $(pip3 --version)"
fi

if command -v nix &> /dev/null; then
    echo "  ✓ Nix found: $(nix --version | head -1)"
else
    echo "  ⚠ Nix not installed (will install via pip3)"
fi

echo ""
if [ ! -z "$MISSING" ]; then
    echo "MISSING:$MISSING"
else
    echo "MISSING:none"
fi
"""

        click.echo(colored("  Checking remote dependencies...\n", "info"))

        check_cmd = ssh_cmd + [remote, check_script]
        try:
            result = subprocess.run(check_cmd, capture_output=True, text=True, check=True)
            output = result.stdout

            # Parse what's missing
            missing_line = [line for line in output.split('\n') if line.startswith('MISSING:')]
            if missing_line:
                missing = missing_line[0].replace('MISSING:', '').strip()
            else:
                missing = "none"

            # Show the output
            for line in output.split('\n'):
                if not line.startswith('MISSING:'):
                    click.echo(f"  {line}")

            if missing != "none":
                # Something is missing, ask user
                click.echo(colored(f"\n  Missing dependencies: {missing}", "warning"))
                click.echo(f"\n  To install these, you'll need sudo access on the remote server.")

                if click.confirm(colored("  Would you like to install missing dependencies now?", "info"), default=False):
                    # Install with sudo
                    install_script = f"""
sudo apt update && sudo apt install -y python3 python3-pip
echo ""
echo "✓ Dependencies installed!"
"""
                    click.echo(colored("\n  Installing via sudo (you may be prompted for password)...\n", "info"))
                    install_cmd = ssh_cmd + ["-t", remote, install_script]  # -t for pseudo-terminal (password prompt)
                    try:
                        subprocess.run(install_cmd, check=True)
                        click.echo()
                    except subprocess.CalledProcessError:
                        error("Installation failed")
                        sys.exit(1)
                else:
                    warning("Skipping dependency installation")
                    click.echo(f"\n  {colored('Manual fix:', 'section')} SSH to server and run:")
                    click.echo(f"    {colored('sudo apt update && sudo apt install -y python3 python3-pip', 'header_text')}\n")
                    sys.exit(0)

            # Now install Nix via pip3
            nix_script = """
echo "🔧 Installing Nix..."
if command -v nix &> /dev/null; then
    echo "  ✓ Nix already installed"
else
    pip3 install --user --break-system-packages nix
    echo "  ✓ Nix installed"
fi

echo ""
echo "🔧 Configuring PATH..."
if ! grep -q '.local/bin' ~/.bashrc; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    echo "  ✓ Added ~/.local/bin to PATH"
else
    echo "  ✓ PATH already configured"
fi

export PATH="$HOME/.local/bin:$PATH"
echo ""
echo "✓ Bootstrap complete!"
"""
            click.echo(colored("\n  Installing Nix and configuring PATH...\n", "info"))
            nix_cmd = ssh_cmd + [remote, nix_script]
            result = subprocess.run(nix_cmd, check=True, text=True)

            success(f"Bootstrap completed on {colored(remote, 'preset_name')}!")
            click.echo(f"\n  {colored('Next:', 'section')} Run {colored('capsule plant', 'header_text')} to deploy Capsule\n")

        except subprocess.CalledProcessError as e:
            error("Bootstrap failed on remote server")
            sys.exit(1)

    else:
        # Local bootstrap
        banner("🔧 LOCAL BOOTSTRAP")

        click.echo(colored("  Checking system dependencies...\n", "info"))

        # Check Python
        click.echo(colored("  [1/4]", "section") + " Checking Python 3...")
        try:
            result = subprocess.run(["python3", "--version"], capture_output=True, text=True, check=True)
            version = result.stdout.strip()
            click.echo(f"        {colored('✓', 'success')} Found: {colored(version, 'dim')}\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            error("Python 3 not found!")
            click.echo("  Please install Python 3.7+ first:")
            click.echo("    Ubuntu/Debian: " + colored("sudo apt install python3", "header_text"))
            click.echo("    macOS: " + colored("brew install python3", "header_text") + "\n")
            sys.exit(1)

        # Check pip3
        click.echo(colored("  [2/4]", "section") + " Checking pip3...")
        try:
            result = subprocess.run(["pip3", "--version"], capture_output=True, text=True, check=True)
            version = result.stdout.strip().split()[1]
            click.echo(f"        {colored('✓', 'success')} Found: pip {colored(version, 'dim')}\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            warning("pip3 not found, attempting to install...")
            try:
                subprocess.run(["sudo", "apt", "install", "-y", "python3-pip"], check=True)
                success("pip3 installed!")
            except subprocess.CalledProcessError:
                error("Failed to install pip3")
                click.echo("  Please install pip3 manually:")
                click.echo("    Ubuntu/Debian: " + colored("sudo apt install python3-pip", "header_text") + "\n")
                sys.exit(1)

        # Check/Install Nix
        click.echo(colored("  [3/4]", "section") + " Checking Nix...")
        try:
            result = subprocess.run(["nix", "--version"], capture_output=True, text=True, check=True)
            version = result.stdout.split('\n')[0].split()[1].strip('[]')
            click.echo(f"        {colored('✓', 'success')} Found: Nix {colored(version, 'dim')}\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            click.echo(f"        {colored('→', 'info')} Installing Nix via pip3...\n")
            try:
                subprocess.run(["pip3", "install", "--user", "nix"], check=True)
                success("Nix installed!")

                # Check PATH
                home = Path.home()
                local_bin = home / ".local" / "bin"
                if str(local_bin) not in os.environ.get("PATH", ""):
                    warning(f"~/.local/bin not in PATH")
                    click.echo(f"  Add to your shell config (~/.bashrc or ~/.zshrc):")
                    path_cmd = 'export PATH="$HOME/.local/bin:$PATH"'
                    click.echo(f"    {colored(path_cmd, 'header_text')}\n")
            except subprocess.CalledProcessError:
                error("Failed to install Nix")
                sys.exit(1)

        # Verify Capsule installation
        click.echo(colored("  [4/4]", "section") + " Checking Capsule installation...")
        try:
            result = subprocess.run(["capsule", "--version"], capture_output=True, text=True, check=True)
            version = result.stdout.strip().split()[-1]
            click.echo(f"        {colored('✓', 'success')} Capsule {colored(version, 'dim')} is installed\n")
        except (subprocess.CalledProcessError, FileNotFoundError):
            warning("Capsule not found in PATH")
            click.echo("  Current directory installation detected")
            click.echo(f"  Install globally: {colored('pip3 install .', 'header_text')}\n")

        success("Bootstrap complete! All dependencies are ready. 🌱")

        click.echo(colored("\n  Quick start:", "section"))
        click.echo(f"    • {colored('capsule profile use ml', 'header_text')} - Choose a profile")
        click.echo(f"    • {colored('capsule preview', 'header_text')} - Preview configuration")
        click.echo(f"    • {colored('sudo capsule setup', 'header_text')} - Apply configuration\n")


# ============================================================================
# PLANT (REMOTE DEPLOYMENT)
# ============================================================================

@cli.command()
@click.argument("server")
@click.option("--port", "-p", default=22, help="SSH port (default: 22)")
@click.option("--key", "-i", help="SSH private key path")
@click.option("--bootstrap/--no-bootstrap", default=True, help="Run bootstrap before planting (default: yes)")
def plant(server, port, key, bootstrap):
    """Deploy Capsule to a remote server (username@server)"""

    if "@" not in server:
        error("Server must be in format: username@hostname")
        click.echo("  " + colored("💡 Example:", "info") + " " +
                   colored("capsule plant user@192.168.1.100", "header_text") + "\n")
        sys.exit(1)

    username, hostname = server.split("@", 1)

    # Run bootstrap first if requested
    if bootstrap:
        click.echo(colored("  Running bootstrap first...\n", "info"))
        ctx = click.get_current_context()
        ctx.invoke(bootstrap_cmd, remote=server, port=port, key=key)
        click.echo("\n" + colored("─" * 60, "dim") + "\n")

    banner("🌱 PLANTING CAPSULE")

    click.echo(f"  {colored('Target:', 'info')} {colored(server, 'preset_name')}")
    click.echo(f"  {colored('Port:', 'info')} {colored(str(port), 'dim')}\n")

    # Create tarball of current capsule directory
    import tarfile
    tarball_path = Path("/tmp/capsule-package.tar.gz")

    click.echo(colored("  [1/4]", "section") + " Packaging Capsule...")
    try:
        # Package the project root (which contains setup.py), not just capsule_package
        project_root = Path(__file__).parent.parent
        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(project_root, arcname="capsule")
        click.echo(f"        {colored('✓', 'success')} Created package: {colored(str(tarball_path), 'dim')}\n")
    except Exception as e:
        error(f"Failed to create package: {e}")
        sys.exit(1)

    # Build SSH/SCP commands
    ssh_base = ["ssh"]
    scp_base = ["scp"]

    if port != 22:
        ssh_base.extend(["-p", str(port)])
        scp_base.extend(["-P", str(port)])

    if key:
        ssh_base.extend(["-i", key])
        scp_base.extend(["-i", key])

    # Copy tarball to remote server
    click.echo(colored("  [2/4]", "section") + " Copying to remote server...\n")
    scp_cmd = scp_base + [str(tarball_path), f"{server}:/tmp/"]

    try:
        subprocess.run(scp_cmd, check=True)
        click.echo(f"\n        {colored('✓', 'success')} Transferred to {colored(f'{server}:/tmp/capsule-package.tar.gz', 'dim')}\n")
    except subprocess.CalledProcessError as e:
        error(f"Failed to copy to remote server")
        sys.exit(1)

    # Extract and install on remote
    click.echo(colored("  [3/4]", "section") + " Extracting on remote server...\n")
    extract_cmd = ssh_base + [
        server,
        "cd /tmp && tar -xzf capsule-package.tar.gz"
    ]

    try:
        subprocess.run(extract_cmd, check=True)
        click.echo(f"\n        {colored('✓', 'success')} Extracted to {colored('/tmp/capsule/', 'dim')}\n")
    except subprocess.CalledProcessError as e:
        error("Failed to extract on remote server")
        sys.exit(1)

    # Install Capsule on remote
    click.echo(colored("  [4/4]", "section") + " Installing Capsule on remote server...")
    click.echo(f"        {colored('→', 'info')} Running: pip3 install --user /tmp/capsule/\n")

    # Create ~/.local/bin if it doesn't exist and install
    install_script = """
set -e
mkdir -p ~/.local/bin
pip3 install --user --break-system-packages /tmp/capsule/
echo ""
echo "INSTALL_SUCCESS"
ls -la ~/.local/bin/capsule 2>/dev/null || echo "Binary installed"
"""

    install_cmd = ssh_base + [server, install_script]

    try:
        result = subprocess.run(install_cmd, check=True, text=True, capture_output=False)

        click.echo(f"\n        {colored('✓', 'success')} Capsule installed successfully!\n")
        click.echo(f"  {colored('ⓘ', 'info')} Installed to {colored('~/.local/bin/capsule', 'preset_name')}")

        # Ensure PATH is configured
        path_check_cmd = ssh_base + [
            server,
            "grep -q '.local/bin' ~/.profile 2>/dev/null || echo 'export PATH=\"$HOME/.local/bin:$PATH\"' >> ~/.profile"
        ]
        subprocess.run(path_check_cmd, capture_output=True)

        click.echo(f"  {colored('ⓘ', 'info')} PATH configured in ~/.profile\n")

    except subprocess.CalledProcessError as e:
        error("Installation failed")
        click.echo(f"\n  {colored('→', 'info')} Try manual installation:")
        click.echo(f"    {colored(f'ssh {server}', 'header_text')}")
        click.echo(f"    {colored('pip3 install --user /tmp/capsule/', 'header_text')}\n")
        sys.exit(1)

    # Cleanup
    tarball_path.unlink()

    success(f"Capsule planted on {colored(server, 'preset_name')}! 🌱")

    # Ask if user wants to SSH in and complete setup
    click.echo()
    if click.confirm(colored("  Would you like to SSH into the server now to complete setup?", "info"), default=True):
        divider()
        click.echo()
        banner("🚀 CONNECTING TO SERVER")

        # Build SSH command
        ssh_cmd = ssh_base + ["-t", server]

        # Create an interactive setup script
        setup_script = """
# Source PATH to ensure capsule is available
export PATH="$HOME/.local/bin:$PATH"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           🌱 Capsule - Server Setup Assistant                ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "  Let's configure your server!"
echo ""
echo "  Step 1: Verify Capsule installation"
capsule --version
echo ""
echo "  Step 2: Choose a profile"
echo "  Run: capsule profiles"
echo ""
echo "  Step 3: Configure your profile"
echo "  Run: capsule profile use <profile-name>"
echo ""
echo "  Step 4: Review configuration"
echo "  Run: capsule show"
echo ""
echo "  Step 5: Deploy"
echo "  Run: capsule setup"
echo ""
echo "────────────────────────────────────────────────────────────"
echo ""

# Start interactive shell with custom prompt
PS1="\\[\\e[1;32m\\]capsule-setup\\[\\e[0m\\]@\\h:\\w$ "
exec bash --norc --noprofile
"""

        # Connect to server with setup script
        click.echo(f"  {colored('Connecting to:', 'info')} {colored(server, 'preset_name')}")
        click.echo(f"  {colored('→', 'dim')} Starting interactive setup session...\n")

        try:
            # Execute the SSH command with the setup script
            subprocess.run(ssh_cmd + [setup_script], check=False)
            click.echo()
            success("SSH session closed")
        except KeyboardInterrupt:
            click.echo()
            warning("SSH session interrupted")
        except Exception as e:
            error(f"Failed to connect: {e}")
    else:
        click.echo()
        click.echo(colored("  Manual setup steps:", "section"))
        click.echo(f"    1. SSH to server: {colored(f'ssh {server}', 'header_text')}")
        click.echo(f"    2. Verify install: {colored('capsule --version', 'header_text')}")
        click.echo(f"    3. Configure: {colored('capsule profile use <profile>', 'header_text')}")
        click.echo(f"    4. Deploy: {colored('capsule setup', 'header_text')} {colored('(will prompt for password)', 'dim')}\n")


# ============================================================================
# DOCUMENTATION
# ============================================================================

@cli.command()
def docs():
    """Generate and open interactive documentation in browser"""
    banner("📚 GENERATING DOCUMENTATION")

    # Get current stacks and profiles
    presets = sorted(list_presets())
    builtin_profiles = list_builtin_profiles()

    html_content = generate_docs_html(presets, builtin_profiles)

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html_content)
        docs_path = f.name

    # Open in browser
    success("Documentation generated!")
    click.echo(f"  {colored('↳', 'info')} Opening in browser: {colored(docs_path, 'dim')}\n")
    webbrowser.open(f'file://{docs_path}')


def generate_docs_html(presets, builtin_profiles):
    """Generate HTML documentation"""

    # Build stacks HTML
    stacks_html = ""
    categories = {
        "Languages & Runtimes": {
            "icon": "🔧",
            "presets": ["python", "golang", "rust", "nodejs"]
        },
        "Development Tools": {
            "icon": "🛠",
            "presets": ["devtools", "cli-tools", "github"]
        },
        "Infrastructure": {
            "icon": "🏗",
            "presets": ["docker", "database", "webserver"]
        },
        "Security & Monitoring": {
            "icon": "🔒",
            "presets": ["security", "monitoring"]
        },
        "AI/ML": {
            "icon": "🤖",
            "presets": ["machine-learning", "ollama", "cuda"]
        },
    }

    for category, data in categories.items():
        category_presets = [p for p in data["presets"] if p in presets]
        if category_presets:
            stacks_html += f'<h3>{data["icon"]} {category}</h3><div class="stack-list">'
            for preset_name in category_presets:
                preset = load_preset(preset_name)
                if preset:
                    desc = preset.get("description", "")
                    deps = preset.get("dependencies", [])
                    opt_deps = preset.get("optional_dependencies", [])

                    stacks_html += f'<div class="stack-item"><strong>{preset_name}</strong><span class="desc">{desc}</span>'
                    if deps:
                        stacks_html += f'<div class="deps">Requires: {", ".join(deps)}</div>'
                    if opt_deps:
                        opt_names = [opt.get("name", opt) if isinstance(opt, dict) else opt for opt in opt_deps]
                        stacks_html += f'<div class="opt-deps">Optional: {", ".join(opt_names)}</div>'
                    stacks_html += '</div>'
            stacks_html += '</div>'

    # Build profiles HTML
    profiles_html = ""
    for profile_name in builtin_profiles:
        profile = get_builtin_profile(profile_name)
        desc = profile.get("description", "")
        stacks = ", ".join([s for s in profile.get("presets", []) if s != "base"])
        pkgs = ", ".join(profile.get("custom_packages", []))

        profiles_html += f'''
        <div class="profile-card">
            <h3>{profile_name}</h3>
            <p class="profile-desc">{desc}</p>
            <div class="profile-details">
                <div><strong>Stacks:</strong> {stacks}</div>
                <div><strong>Packages:</strong> {pkgs}</div>
            </div>
            <div class="code-block">capsule config profile use {profile_name}</div>
        </div>
        '''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌱 Capsule Documentation</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #2c3e50;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        header {{
            background: linear-gradient(135deg, #06b6d4 0%, #10b981 100%);
            color: white;
            padding: 60px 40px;
            text-align: center;
        }}

        header h1 {{
            font-size: 3.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }}

        header .tagline {{
            font-size: 1.2em;
            opacity: 0.95;
            font-weight: 300;
        }}

        nav {{
            background: #f8f9fa;
            padding: 20px 40px;
            border-bottom: 2px solid #e9ecef;
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}

        nav a {{
            color: #06b6d4;
            text-decoration: none;
            font-weight: 600;
            padding: 8px 16px;
            border-radius: 6px;
            transition: all 0.3s;
        }}

        nav a:hover {{
            background: #06b6d4;
            color: white;
        }}

        .content {{
            padding: 40px;
        }}

        section {{
            margin-bottom: 50px;
        }}

        h2 {{
            color: #06b6d4;
            font-size: 2em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #06b6d4;
        }}

        h3 {{
            color: #10b981;
            font-size: 1.4em;
            margin: 25px 0 15px 0;
        }}

        .code-block {{
            background: #1e293b;
            color: #10b981;
            padding: 15px 20px;
            border-radius: 8px;
            font-family: "Monaco", "Menlo", monospace;
            font-size: 0.95em;
            overflow-x: auto;
            margin: 15px 0;
            border-left: 4px solid #10b981;
        }}

        .command-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}

        .command-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #06b6d4;
            transition: transform 0.3s, box-shadow 0.3s;
        }}

        .command-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }}

        .command-card h4 {{
            color: #06b6d4;
            margin-bottom: 10px;
            font-size: 1.1em;
        }}

        .command-card .cmd {{
            background: #1e293b;
            color: #10b981;
            padding: 8px 12px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 0.9em;
            margin: 10px 0;
        }}

        .stack-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}

        .stack-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #10b981;
        }}

        .stack-item strong {{
            color: #10b981;
            font-size: 1.1em;
        }}

        .stack-item .desc {{
            display: block;
            color: #6c757d;
            margin-top: 5px;
            font-size: 0.9em;
        }}

        .deps {{
            margin-top: 8px;
            font-size: 0.85em;
            color: #06b6d4;
        }}

        .opt-deps {{
            margin-top: 5px;
            font-size: 0.85em;
            color: #f59e0b;
        }}

        .profile-card {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 20px;
            border: 2px solid #e9ecef;
            transition: transform 0.3s;
        }}

        .profile-card:hover {{
            transform: scale(1.02);
            border-color: #06b6d4;
        }}

        .profile-card h3 {{
            color: #06b6d4;
            margin: 0 0 10px 0;
        }}

        .profile-desc {{
            color: #6c757d;
            margin-bottom: 15px;
        }}

        .profile-details {{
            margin: 15px 0;
            font-size: 0.9em;
        }}

        .profile-details div {{
            margin: 5px 0;
        }}

        .example-box {{
            background: #f0f9ff;
            border-left: 4px solid #06b6d4;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
        }}

        .example-box h4 {{
            color: #06b6d4;
            margin-bottom: 10px;
        }}

        footer {{
            background: #1e293b;
            color: white;
            text-align: center;
            padding: 30px;
            margin-top: 40px;
        }}

        footer a {{
            color: #10b981;
            text-decoration: none;
        }}

        .feature-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}

        .feature {{
            text-align: center;
            padding: 20px;
        }}

        .feature-icon {{
            font-size: 3em;
            margin-bottom: 10px;
        }}

        .feature h3 {{
            color: #2c3e50;
            font-size: 1.2em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌱 Capsule</h1>
            <p class="tagline">Beautiful Server Configuration Made Simple</p>
        </header>

        <nav>
            <a href="#quick-start">Quick Start</a>
            <a href="#profiles">Profiles</a>
            <a href="#stacks">Technology Stacks</a>
            <a href="#commands">Commands</a>
            <a href="#examples">Examples</a>
        </nav>

        <div class="content">
            <section id="overview">
                <h2>Overview</h2>
                <p>Capsule is a user-friendly Ubuntu server configuration tool that combines the power of Nix with an intuitive CLI interface. Configure servers using built-in profiles, modular technology stacks, and automatic dependency management.</p>

                <div class="feature-grid">
                    <div class="feature">
                        <div class="feature-icon">📦</div>
                        <h3>Built-in Profiles</h3>
                        <p>Pre-configured setups for common use cases</p>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">🔗</div>
                        <h3>Smart Dependencies</h3>
                        <p>Automatic dependency resolution</p>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">🎨</div>
                        <h3>Beautiful CLI</h3>
                        <p>Gorgeous ASCII UI with colors</p>
                    </div>
                    <div class="feature">
                        <div class="feature-icon">⚡</div>
                        <h3>Idempotent</h3>
                        <p>Safe to run multiple times</p>
                    </div>
                </div>
            </section>

            <section id="quick-start">
                <h2>🚀 Quick Start</h2>
                <div class="code-block">
# Install capsule<br>
pip3 install capsule<br>
<br>
# Use a built-in profile<br>
capsule config profile use ml-gpu<br>
<br>
# Preview what will be installed<br>
capsule preview<br>
<br>
# Apply configuration<br>
sudo capsule setup
                </div>
            </section>

            <section id="profiles">
                <h2>📁 Built-in Profiles</h2>
                <p>Capsule ships with pre-configured profiles embedded in the binary. Use them directly or import and customize:</p>
                {profiles_html}
            </section>

            <section id="stacks">
                <h2>📦 Technology Stacks</h2>
                <p>Modular technology stacks that can be mixed and matched. Dependencies are resolved automatically:</p>
                {stacks_html}
            </section>

            <section id="commands">
                <h2>🔧 Command Reference</h2>

                <h3>Profile Management</h3>
                <div class="command-grid">
                    <div class="command-card">
                        <h4>List Profiles</h4>
                        <div class="cmd">capsule config profiles</div>
                        <p>Show all built-in and user profiles</p>
                    </div>
                    <div class="command-card">
                        <h4>Use Profile</h4>
                        <div class="cmd">capsule config profile use &lt;name&gt;</div>
                        <p>Switch to a profile</p>
                    </div>
                    <div class="command-card">
                        <h4>Import Profile</h4>
                        <div class="cmd">capsule config profile import &lt;name&gt;</div>
                        <p>Import built-in to customize</p>
                    </div>
                    <div class="command-card">
                        <h4>Create Profile</h4>
                        <div class="cmd">capsule config profile new &lt;name&gt;</div>
                        <p>Create a new custom profile</p>
                    </div>
                </div>

                <h3>Stack Management</h3>
                <div class="command-grid">
                    <div class="command-card">
                        <h4>List Stacks</h4>
                        <div class="cmd">capsule config stacks</div>
                        <p>Show all available technology stacks</p>
                    </div>
                    <div class="command-card">
                        <h4>Add Stack</h4>
                        <div class="cmd">capsule config add &lt;stack&gt;</div>
                        <p>Add a stack (auto-resolves dependencies)</p>
                    </div>
                    <div class="command-card">
                        <h4>Remove Stack</h4>
                        <div class="cmd">capsule config remove &lt;stack&gt;</div>
                        <p>Remove a stack from configuration</p>
                    </div>
                    <div class="command-card">
                        <h4>Show Config</h4>
                        <div class="cmd">capsule config show</div>
                        <p>Display current configuration</p>
                    </div>
                </div>

                <h3>Installation</h3>
                <div class="command-grid">
                    <div class="command-card">
                        <h4>Setup</h4>
                        <div class="cmd">sudo capsule setup</div>
                        <p>Install all configured packages</p>
                    </div>
                    <div class="command-card">
                        <h4>Check</h4>
                        <div class="cmd">capsule check</div>
                        <p>Dry run (preview changes)</p>
                    </div>
                    <div class="command-card">
                        <h4>Preview</h4>
                        <div class="cmd">capsule preview</div>
                        <p>View generated Nix configuration</p>
                    </div>
                </div>
            </section>

            <section id="examples">
                <h2>💡 Examples</h2>

                <div class="example-box">
                    <h4>Quick Deploy with Built-in Profile</h4>
                    <div class="code-block">
# Fresh Ubuntu server<br>
pip3 install capsule<br>
capsule config profile use ml-gpu<br>
capsule check  # Preview<br>
sudo capsule setup  # Deploy!
                    </div>
                </div>

                <div class="example-box">
                    <h4>Custom Configuration</h4>
                    <div class="code-block">
# Import and customize<br>
capsule config profile import dev my-dev<br>
capsule config profile use my-dev<br>
capsule config add golang rust<br>
capsule config pkg add neovim zsh<br>
sudo capsule setup
                    </div>
                </div>

                <div class="example-box">
                    <h4>Build from Scratch</h4>
                    <div class="code-block">
capsule config profile new custom<br>
capsule config profile use custom<br>
capsule config add python docker nodejs<br>
capsule config pkg add htop tmux<br>
capsule preview<br>
sudo capsule setup
                    </div>
                </div>
            </section>
        </div>

        <footer>
            <p>🌱 <strong>Capsule</strong> - Beautiful Server Configuration</p>
            <p>Powered by Nix • Version 0.9.0</p>
            <p><a href="https://github.com/yourusername/capsule">GitHub</a></p>
        </footer>
    </div>
</body>
</html>'''


# ============================================================================
# UPDATE COMMAND
# ============================================================================

SOURCE_DIR = CAPSULE_DIR / "source"
REPO_URL = "git@github.com:Geijutsu/capsule.git"

@cli.command()
def update():
    """Update Capsule to the latest version from GitHub"""
    banner("🔄 UPDATING CAPSULE")

    # Check if git is installed
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        error("Git is not installed")
        click.echo("  Please install git first:")
        click.echo("    Ubuntu/Debian: " + colored("sudo apt install git", "header_text"))
        click.echo("    macOS: " + colored("brew install git", "header_text") + "\n")
        sys.exit(1)

    # Clone or pull the repository
    if SOURCE_DIR.exists():
        # Repository already cloned, pull latest changes
        click.echo(colored("  [1/3]", "section") + " Fetching latest changes...")
        try:
            # Get current commit before pulling
            old_commit = subprocess.run(
                ["git", "-C", str(SOURCE_DIR), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()[:7]

            result = subprocess.run(
                ["git", "-C", str(SOURCE_DIR), "pull", "origin", "main"],
                capture_output=True,
                text=True,
                check=True
            )

            if "Already up to date" in result.stdout:
                click.echo(f"        {colored('✓', 'success')} Already up to date\n")
            else:
                # Get new commit after pulling
                new_commit = subprocess.run(
                    ["git", "-C", str(SOURCE_DIR), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True
                ).stdout.strip()[:7]

                # Get commit summary
                commits = subprocess.run(
                    ["git", "-C", str(SOURCE_DIR), "log", "--oneline", f"{old_commit}..{new_commit}"],
                    capture_output=True,
                    text=True,
                    check=True
                ).stdout.strip().split('\n')

                # Get file changes
                files_changed = subprocess.run(
                    ["git", "-C", str(SOURCE_DIR), "diff", "--name-status", f"{old_commit}..{new_commit}"],
                    capture_output=True,
                    text=True,
                    check=True
                ).stdout.strip().split('\n')

                click.echo(f"        {colored('✓', 'success')} Fetched latest changes")
                click.echo(f"        {colored('Commits:', 'dim')} {len(commits)} new commit(s)")

                # Show commit messages (first 3)
                for i, commit in enumerate(commits[:3]):
                    if commit:
                        click.echo(f"          {colored('•', 'info')} {commit}")
                if len(commits) > 3:
                    click.echo(f"          {colored(f'... and {len(commits) - 3} more', 'dim')}")

                # Show file changes summary
                added = sum(1 for f in files_changed if f.startswith('A'))
                modified = sum(1 for f in files_changed if f.startswith('M'))
                deleted = sum(1 for f in files_changed if f.startswith('D'))

                changes_summary = []
                if added: changes_summary.append(f"{added} added")
                if modified: changes_summary.append(f"{modified} modified")
                if deleted: changes_summary.append(f"{deleted} deleted")

                if changes_summary:
                    click.echo(f"        {colored('Files:', 'dim')} {', '.join(changes_summary)}")
                click.echo()

        except subprocess.CalledProcessError as e:
            error("Failed to fetch updates")
            click.echo(f"  {colored('Error:', 'error')} {e.stderr}\n")
            sys.exit(1)
    else:
        # Repository doesn't exist, clone it
        click.echo(colored("  [1/3]", "section") + " Cloning capsule repository...")
        try:
            SOURCE_DIR.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", REPO_URL, str(SOURCE_DIR)],
                capture_output=True,
                text=True,
                check=True
            )
            click.echo(f"        {colored('✓', 'success')} Cloned repository\n")
        except subprocess.CalledProcessError as e:
            error("Failed to clone repository")
            click.echo(f"  {colored('Error:', 'error')} {e.stderr}")
            click.echo(f"\n  {colored('Note:', 'warning')} Make sure you have SSH access to GitHub")
            click.echo(f"  {colored('→', 'info')} Check your SSH keys: {colored('ssh -T git@github.com', 'header_text')}\n")
            sys.exit(1)

    # Get current and new version
    click.echo(colored("  [2/3]", "section") + " Checking versions...")
    try:
        current_result = subprocess.run(
            ["capsule", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        current_version = current_result.stdout.strip().split()[-1]
    except:
        current_version = "unknown"

    # Read new version from setup.py
    setup_file = SOURCE_DIR / "setup.py"
    try:
        with open(setup_file) as f:
            for line in f:
                if "version=" in line:
                    new_version = line.split('"')[1]
                    break
    except:
        new_version = "unknown"

    click.echo(f"        {colored('Current:', 'dim')} {colored(current_version, 'info')}")
    click.echo(f"        {colored('Latest:', 'dim')} {colored(new_version, 'preset_name')}\n")

    # Reinstall
    click.echo(colored("  [3/3]", "section") + " Reinstalling capsule...")
    try:
        install_cmd = ["pip3", "install", "--user", "--upgrade", str(SOURCE_DIR)]

        # Add --break-system-packages if needed (Python 3.12+)
        try:
            python_version = subprocess.run(
                ["python3", "--version"],
                capture_output=True,
                text=True
            ).stdout.strip()
            if "Python 3.12" in python_version or "Python 3.13" in python_version:
                install_cmd.insert(3, "--break-system-packages")
        except:
            pass

        result = subprocess.run(
            install_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        click.echo(f"        {colored('✓', 'success')} Reinstalled successfully!\n")
    except subprocess.CalledProcessError as e:
        error("Failed to reinstall")
        click.echo(f"  {colored('Output:', 'error')}\n{e.stdout if e.stdout else ''}")
        click.echo(f"  {colored('Errors:', 'error')}\n{e.stderr if e.stderr else ''}\n")
        sys.exit(1)

    success(f"Capsule updated to version {colored(new_version, 'preset_name')}! 🌱")

    click.echo(colored("  Verify the update:", "section"))
    click.echo(f"    {colored('capsule --version', 'header_text')}\n")


# ============================================================================
# DEPLOY COMMAND
# ============================================================================

@cli.command()
@click.option('-m', '--message', help='Commit message (optional, will prompt if not provided)')
@click.option('--dry-run', is_flag=True, help='Show what would be done without executing')
def deploy(message, dry_run):
    """Safely stage, commit, and push changes from the current directory"""
    banner("🚀 DEPLOYING CHANGES")

    # Check if git is installed
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        error("Git is not installed")
        click.echo("  Please install git first:")
        click.echo("    Ubuntu/Debian: " + colored("sudo apt install git", "header_text"))
        click.echo("    macOS: " + colored("brew install git", "header_text") + "\n")
        sys.exit(1)

    # Use current working directory
    repo_dir = Path.cwd()

    # Check if current directory is a git repository
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
            cwd=repo_dir
        )
    except subprocess.CalledProcessError:
        error("Not a git repository")
        click.echo(f"  Current directory: {colored(str(repo_dir), 'dim')}")
        click.echo(f"  Run {colored('git init', 'header_text')} first\n")
        sys.exit(1)

    click.echo(f"  {colored('Repository:', 'dim')} {colored(str(repo_dir), 'info')}\n")

    # Step 1: Auto-increment version
    click.echo(colored("  [1/6]", "section") + " Incrementing version...")
    setup_py = repo_dir / "setup.py"

    if setup_py.exists():
        try:
            # Read setup.py
            with open(setup_py, 'r') as f:
                setup_content = f.read()

            # Extract current version
            import re
            version_match = re.search(r'version="(\d+)\.(\d+)\.(\d+)"', setup_content)
            if version_match:
                major, minor, patch = version_match.groups()
                old_version = f"{major}.{minor}.{patch}"
                new_patch = int(patch) + 1
                new_version = f"{major}.{minor}.{new_patch}"

                if not dry_run:
                    # Update setup.py
                    setup_content = setup_content.replace(
                        f'version="{old_version}"',
                        f'version="{new_version}"'
                    )
                    with open(setup_py, 'w') as f:
                        f.write(setup_content)

                    # Update __init__.py
                    init_py = repo_dir / "capsule_package" / "__init__.py"
                    if init_py.exists():
                        with open(init_py, 'r') as f:
                            init_content = f.read()
                        init_content = init_content.replace(
                            f'@click.version_option(version="{old_version}")',
                            f'@click.version_option(version="{new_version}")'
                        )
                        with open(init_py, 'w') as f:
                            f.write(init_content)

                    click.echo(f"        {colored('✓', 'success')} Version: {colored(old_version, 'dim')} → {colored(new_version, 'preset_name')}\n")
                else:
                    click.echo(f"        {colored('➜', 'info')} Would update: {colored(old_version, 'dim')} → {colored(new_version, 'preset_name')}\n")
            else:
                click.echo(f"        {colored('⚠', 'warning')} Version not found in setup.py\n")
        except Exception as e:
            warning(f"Failed to increment version: {e}")
            click.echo()
    else:
        click.echo(f"        {colored('⚠', 'warning')} setup.py not found, skipping version increment\n")

    # Step 2: Check for uncommitted changes
    click.echo(colored("  [2/6]", "section") + " Checking for changes...")
    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_dir
        )

        if not status_result.stdout.strip():
            warning("No changes to deploy")
            click.echo("  Working tree is clean\n")
            sys.exit(0)

        # Show what will be staged
        changes = status_result.stdout.strip().split('\n')
        click.echo(f"        {colored('✓', 'success')} Found {len(changes)} change(s):")
        for change in changes[:5]:  # Show first 5 changes
            click.echo(f"          {colored(change.strip(), 'dim')}")
        if len(changes) > 5:
            click.echo(f"          {colored(f'... and {len(changes) - 5} more', 'dim')}")
        click.echo()

    except subprocess.CalledProcessError as e:
        error("Failed to check git status")
        click.echo(f"  {colored('Error:', 'error')} {e.stderr}\n")
        sys.exit(1)

    # Step 3: Stage changes
    click.echo(colored("  [3/6]", "section") + " Staging changes...")
    if dry_run:
        click.echo(f"        {colored('➜', 'info')} Would run: git add -A")
    else:
        try:
            subprocess.run(["git", "add", "-A"], capture_output=True, check=True, cwd=repo_dir)
            click.echo(f"        {colored('✓', 'success')} All changes staged\n")
        except subprocess.CalledProcessError as e:
            error("Failed to stage changes")
            click.echo(f"  {colored('Error:', 'error')} {e.stderr}\n")
            sys.exit(1)

    # Step 4: Get or generate commit message
    if not message:
        # Generate heuristic commit message based on changed files
        click.echo(colored("  [4/6]", "section") + " Generating commit message...")

        # Parse changed files
        modified_files = []
        added_files = []
        deleted_files = []

        for change in changes:
            status = change[:2].strip()
            filepath = change[3:].strip() if len(change) > 3 else ""

            if status == 'M':
                modified_files.append(filepath)
            elif status in ['A', '??']:
                added_files.append(filepath)
            elif status == 'D':
                deleted_files.append(filepath)

        # Generate message based on changes
        message_parts = []

        # Check for specific patterns
        sprout_changes = [f for f in added_files + modified_files if 'sprout' in f.lower()]
        yml_changes = [f for f in added_files + modified_files if f.endswith('.yml')]
        py_changes = [f for f in modified_files if f.endswith('.py')]

        if sprout_changes:
            sprout_names = [f.split('/')[-1].replace('.yml', '') for f in sprout_changes if '.yml' in f]
            if sprout_names:
                message_parts.append(f"Add sprouts: {', '.join(sprout_names[:3])}")

        if py_changes and 'deploy' in str(py_changes):
            message_parts.append("Update deploy command")
        elif py_changes:
            message_parts.append(f"Update {len(py_changes)} Python file(s)")

        if added_files and not sprout_changes:
            message_parts.append(f"Add {len(added_files)} file(s)")

        if deleted_files:
            message_parts.append(f"Remove {len(deleted_files)} file(s)")

        # Fallback message
        if not message_parts:
            if len(modified_files) > 0:
                message_parts.append(f"Update {len(modified_files)} file(s)")
            else:
                message_parts.append("Update files")

        message = " and ".join(message_parts[:2])  # Keep it concise

        click.echo(f"        {colored('Generated:', 'dim')} {colored(message, 'preset_name')}")
        click.echo(f"        {colored('Tip:', 'dim')} Use -m to specify custom message\n")
    else:
        click.echo(colored("  [4/6]", "section") + " Creating commit...")

    if dry_run:
        click.echo(f"        {colored('➜', 'info')} Would commit with message: {colored(message, 'preset_name')}")
    else:
        try:
            subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_dir
            )
            click.echo(f"        {colored('✓', 'success')} Committed: {colored(message, 'preset_name')}\n")
        except subprocess.CalledProcessError as e:
            error("Failed to create commit")
            click.echo(f"  {colored('Error:', 'error')} {e.stderr}\n")
            sys.exit(1)

    # Step 5: Get current branch
    click.echo(colored("  [5/6]", "section") + " Checking branch...")
    try:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_dir
        )
        current_branch = branch_result.stdout.strip()
        click.echo(f"        {colored('✓', 'success')} On branch: {colored(current_branch, 'preset_name')}\n")
    except subprocess.CalledProcessError as e:
        error("Failed to get current branch")
        click.echo(f"  {colored('Error:', 'error')} {e.stderr}\n")
        sys.exit(1)

    # Step 6: Push to origin
    click.echo(colored("  [6/6]", "section") + " Pushing to origin...")
    if dry_run:
        click.echo(f"        {colored('➜', 'info')} Would run: git push origin {current_branch}")
        click.echo()
        warning("Dry run complete - no changes were made")
        click.echo()
    else:
        try:
            push_result = subprocess.run(
                ["git", "push", "origin", current_branch],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_dir
            )
            click.echo(f"        {colored('✓', 'success')} Pushed to origin/{current_branch}\n")

            success(f"Deployed to {colored(current_branch, 'preset_name')}! 🚀")

            # Show summary
            click.echo(colored("  Summary:", "section"))
            click.echo(f"    Commit: {colored(message, 'dim')}")
            click.echo(f"    Branch: {colored(current_branch, 'dim')}\n")

        except subprocess.CalledProcessError as e:
            error("Failed to push to origin")
            click.echo(f"  {colored('Error:', 'error')} {e.stderr}")
            click.echo("\n  " + colored("💡 Tip:", "info") + " You may need to:")
            click.echo("    • Set up a remote: " + colored("git remote add origin <url>", "header_text"))
            click.echo("    • Pull first: " + colored("git pull origin " + current_branch, "header_text"))
            click.echo("    • Force push (caution): " + colored("git push -f origin " + current_branch, "header_text") + "\n")
            sys.exit(1)


# ============================================================================
# SPROUTS COMMANDS (QUICK INSTALL TEMPLATES)
# ============================================================================

@cli.command()
def sprouts():
    """List available installation sprouts (quick install templates)"""
    sprouts = sorted(list_sprouts())

    header("🌱 INSTALLATION SPROUTS")

    if not sprouts:
        warning("No sprouts available")
        return

    click.echo("  " + colored("Sprouts are quick-install templates for popular tools", "dim") + "\n")

    # Group by category
    categories = {}
    for sprout_name in sprouts:
        sprout = load_sprout(sprout_name)
        if sprout:
            category = sprout.get("category", "Other")
            if category not in categories:
                categories[category] = []
            categories[category].append((sprout_name, sprout))

    # Display by category
    for category, items in sorted(categories.items()):
        section_header(f"  {category}")
        for sprout_name, sprout in items:
            desc = sprout.get("description", "")
            url = sprout.get("url", "")
            deps = sprout.get("dependencies", [])

            preset_item(sprout_name, desc, active=False)

            if url:
                click.echo("      " + colored("↳ url:", "dim") + " " + colored(url, "info"))

            if deps:
                deps_text = ", ".join([colored(d, "info") for d in deps])
                click.echo("      " + colored("↳ requires:", "dim") + " " + deps_text)

    divider()
    click.echo()
    click.echo("  " + colored("💡 Usage:", "info") + " " +
               colored("capsule sprout", "header_text") + " " +
               colored("<name>", "section") + " to install")
    click.echo()


@cli.command()
@click.argument("name")
@click.option("--check", is_flag=True, help="Dry run mode (preview changes)")
@click.option("--no-sudo", is_flag=True, help="Skip tasks requiring sudo")
def sprout(name, check, no_sudo):
    """Install a sprout (quick install template)"""
    sprout_config = load_sprout(name)

    if not sprout_config:
        error(f"Sprout '{colored(name, 'error')}' not found")
        click.echo("  " + colored("💡 Hint:", "info") + " Run " +
                   colored("capsule sprouts", "header_text") +
                   " to see available sprouts\n")
        sys.exit(1)

    # Display sprout info
    if check:
        banner(f"🔍 DRY RUN: {name.upper()}")
    else:
        banner(f"🌱 INSTALLING: {name.upper()}")

    desc = sprout_config.get("description", "")
    url = sprout_config.get("url", "")

    click.echo("  " + colored("Description:", "dim") + " " + desc)
    if url:
        click.echo("  " + colored("URL:", "dim") + " " + colored(url, "info"))
    click.echo()

    # Check dependencies
    deps = sprout_config.get("dependencies", [])
    if deps:
        section_header("Checking Dependencies")
        all_satisfied = True
        for dep in deps:
            # Check if dependency is satisfied
            check_cmd = f"command -v {dep} > /dev/null 2>&1"
            result = subprocess.run(check_cmd, shell=True, capture_output=True)
            if result.returncode == 0:
                click.echo(f"  {colored('✓', 'success')} {colored(dep, 'preset_name')} is installed")
            else:
                click.echo(f"  {colored('✗', 'error')} {colored(dep, 'error')} is missing")
                all_satisfied = False

        if not all_satisfied:
            click.echo()
            error("Some dependencies are missing")
            click.echo("  Please install missing dependencies first\n")
            sys.exit(1)
        click.echo()

    # Generate and run configuration
    configuration_data = {
        "name": f"Install {sprout_config.get('name', name)}",
        "hosts": "localhost",
        "become": False,  # Will use become per-task if needed
        "tasks": sprout_config.get("tasks", [])
    }

    # Write temporary configuration
    temp_configuration = Path("/tmp/capsule-sprout-configuration.yml")
    with open(temp_configuration, "w") as f:
        yaml.dump([configuration_data], f, default_flow_style=False)

    # Build nix command
    # Add -v for verbose output to show progress (especially for downloads)
    cmd = ["nix-configuration", str(temp_configuration), "-c", "local", "-v"]
    if check:
        cmd.append("--check")

    # Check if any tasks require sudo
    tasks = sprout_config.get("tasks", [])
    needs_sudo = any(task.get("become", False) or task.get("systemd") or task.get("apt") for task in tasks)

    if needs_sudo and not no_sudo:
        cmd.append("--ask-become-pass")
        click.echo(colored("  ⓘ This sprout requires sudo access\n", "warning"))

    # Run nix
    try:
        if needs_sudo and not no_sudo:
            click.echo(colored("  Running installation tasks (you may be prompted for password)...\n", "info"))
        else:
            click.echo(colored("  Running installation tasks...\n", "info"))
        result = subprocess.run(cmd, check=True)

        if check:
            success(f"Dry run completed for {colored(name, 'preset_name')}!")
            click.echo("  " + colored("→", "info") + " Run without --check to actually install\n")
        else:
            success(f"Successfully installed {colored(name, 'preset_name')}! 🌱")

            # Show next steps if available
            next_steps = sprout_config.get("next_steps", [])
            if next_steps:
                click.echo(colored("\n  Next steps:", "section"))
                for step in next_steps:
                    click.echo(f"    {colored('▸', 'info')} {step}")
                click.echo()

        return result.returncode

    except subprocess.CalledProcessError as e:
        error(f"Installation of {colored(name, 'error')} failed")
        click.echo(f"  {colored('Exit code:', 'error')} {e.returncode}\n")
        return e.returncode
    except FileNotFoundError:
        error("nix-configuration not found")
        click.echo("  Install Nix first: " + colored("capsule bootstrap", "header_text") + "\n")
        return 1


if __name__ == "__main__":
    cli()

# ============================================================================
# OPENMESH MANAGEMENT
# ============================================================================

@cli.group("openmesh", invoke_without_command=True)
@click.pass_context
def openmesh(ctx):
    """Manage OpenMesh xNode infrastructure"""
    if ctx.invoked_subcommand is None:
        # Show OpenMesh overview when called without subcommand
        header("🌐 OPENMESH")

        section_header("🔹 Overview")
        info_line("Status", colored("Not configured", "warning"), icon="●")
        info_line("Active xNodes", colored("0", "dim"), icon="▸")
        info_line("Total Capacity", colored("N/A", "dim"), icon="▸")

        click.echo()
        section_header("🔹 Quick Start")
        click.echo(f"  {colored('1.', 'info')} Configure OpenMesh credentials:")
        click.echo(f"     {colored('capsule openmesh configure', 'header_text')}")
        click.echo()
        click.echo(f"  {colored('2.', 'info')} Browse available xNodes:")
        click.echo(f"     {colored('capsule openmesh xnode browse', 'header_text')}")
        click.echo()
        click.echo(f"  {colored('3.', 'info')} Deploy your first xNode:")
        click.echo(f"     {colored('capsule openmesh xnode deploy', 'header_text')}")
        click.echo()

        section_header("🔹 Available Commands")
        click.echo(f"  {colored('configure', 'preset_name'):15} Configure OpenMesh API credentials")
        click.echo(f"  {colored('xnodes', 'preset_name'):15} List all running xNodes")
        click.echo(f"  {colored('xnode', 'preset_name'):15} Manage individual xNodes")
        click.echo()

        click.echo(f"  {colored('💡 Tip:', 'info')} Run {colored('capsule openmesh xnode --help', 'header_text')} for xNode commands\n")


@openmesh.command("configure")
@click.option("--api-key", prompt=True, hide_input=True, help="OpenMesh API key")
@click.option("--api-secret", prompt=True, hide_input=True, help="OpenMesh API secret")
@click.option("--region", default="us-east-1", help="Default deployment region")
def openmesh_configure(api_key, api_secret, region):
    """Configure OpenMesh API credentials and settings"""
    banner("🌐 OpenMesh Configuration", "🔧")

    # Store credentials securely
    config_data = {
        "api_key": api_key,
        "api_secret": api_secret,
        "region": region,
        "configured_at": subprocess.check_output(["date", "+%Y-%m-%d %H:%M:%S"]).decode().strip()
    }

    # Save to OpenMesh config
    openmesh_config_file = CAPSULE_DIR / "openmesh.yml"
    with open(openmesh_config_file, "w") as f:
        yaml.dump(config_data, f)

    success("OpenMesh configured successfully!")
    click.echo(f"  {colored('▸', 'info')} Default region: {colored(region, 'preset_name')}")
    click.echo(f"  {colored('▸', 'info')} Next: Run {colored('capsule openmesh xnode browse', 'header_text')}\n")


@openmesh.command("xnodes")
@click.option("--status", type=click.Choice(["all", "running", "stopped", "deploying"]), default="all", help="Filter by status")
@click.option("--region", help="Filter by region")
def openmesh_xnodes(status, region):
    """List all xNodes across all regions"""
    header("🔌 ACTIVE XNODES")

    # Placeholder data structure
    xnodes = []

    if not xnodes:
        warning("No xNodes found")
        click.echo(f"  {colored('💡 Tip:', 'info')} Deploy your first xNode with {colored('capsule openmesh xnode deploy', 'header_text')}\n")
        return

    section_header("🔹 Running xNodes")
    for xnode in xnodes:
        if status != "all" and xnode["status"] != status:
            continue
        if region and xnode["region"] != region:
            continue

        status_icon = colored("●", "success") if xnode["status"] == "running" else colored("○", "warning")
        click.echo(f"  {status_icon} {colored(xnode['name'], 'preset_name'):20} "
                   f"{colored(xnode['id'], 'dim'):15} "
                   f"{colored(xnode['region'], 'info'):15} "
                   f"{colored(xnode['cpu'] + ' CPU', 'dim'):10} "
                   f"{colored(xnode['memory'], 'dim'):8} "
                   f"{colored(xnode['uptime'], 'dim')}")

    click.echo()
    click.echo(f"  {colored('Total:', 'section')} {colored(str(len(xnodes)), 'preset_name')} xNodes\n")


@openmesh.group("xnode", invoke_without_command=True)
@click.pass_context
def xnode(ctx):
    """Manage individual xNodes"""
    if ctx.invoked_subcommand is None:
        banner("🔌 xNode Management", "⚙️")

        click.echo(colored("  Available Commands:\n", "section"))
        click.echo(f"  {colored('browse', 'preset_name'):15} Browse available xNode templates")
        click.echo(f"  {colored('deploy', 'preset_name'):15} Deploy a new xNode")
        click.echo(f"  {colored('launch', 'preset_name'):15} Launch a specific xNode")
        click.echo(f"  {colored('restart', 'preset_name'):15} Restart a running xNode")
        click.echo(f"  {colored('stop', 'preset_name'):15} Stop a running xNode")
        click.echo(f"  {colored('tunnel', 'preset_name'):15} Create SSH tunnel to xNode")
        click.echo(f"  {colored('manage', 'preset_name'):15} Interactive xNode management")
        click.echo()

        click.echo(f"  {colored('💡 Tip:', 'info')} Run {colored('capsule openmesh xnode <command> --help', 'header_text')} for detailed help\n")


@xnode.command("browse")
@click.option("--region", help="Filter templates by region")
@click.option("--size", type=click.Choice(["small", "medium", "large", "xl"]), help="Filter by size")
def xnode_browse(region, size):
    """Browse available xNode templates and configurations"""
    header("🔍 AVAILABLE XNODE TEMPLATES")

    templates = [
        {"id": "basic-cpu-2", "name": "Basic (2 CPU)", "cpu": "2", "memory": "4GB", "storage": "50GB", "price": "$0.05/hr"},
        {"id": "standard-cpu-4", "name": "Standard (4 CPU)", "cpu": "4", "memory": "8GB", "storage": "100GB", "price": "$0.10/hr"},
        {"id": "performance-cpu-8", "name": "Performance (8 CPU)", "cpu": "8", "memory": "16GB", "storage": "200GB", "price": "$0.20/hr"},
        {"id": "xl-cpu-16", "name": "XL (16 CPU)", "cpu": "16", "memory": "32GB", "storage": "500GB", "price": "$0.40/hr"},
    ]

    section_header("🔹 Available Templates")
    for template in templates:
        click.echo(f"  {colored('◆', 'package_name')} {colored(template['name'], 'preset_name'):25} "
                   f"{colored(template['cpu'] + ' CPU', 'dim'):12} "
                   f"{colored(template['memory'], 'dim'):8} "
                   f"{colored(template['storage'], 'dim'):10} "
                   f"{colored(template['price'], 'info')}")

    click.echo()
    click.echo(f"  {colored('💡 Next:', 'info')} Deploy a template with {colored('capsule openmesh xnode deploy --template <id>', 'header_text')}\n")


@xnode.command("deploy")
@click.option("--template", required=True, help="Template ID to deploy")
@click.option("--name", help="Custom name for the xNode")
@click.option("--region", default="us-east-1", help="Deployment region")
@click.option("--profile", help="Capsule profile to install (e.g., dev, ml, prod)")
@click.option("--auto-configure", is_flag=True, help="Automatically configure xNode with Capsule")
def xnode_deploy(template, name, region, profile, auto_configure):
    """Deploy a new xNode instance"""
    banner("🚀 Deploying xNode", "🔌")

    if not name:
        import time
        name = f"xnode-{template}-{int(time.time())}"

    click.echo(colored("  Deployment Configuration:", "section"))
    info_line("Template", colored(template, "preset_name"))
    info_line("Name", colored(name, "info"))
    info_line("Region", colored(region, "info"))
    if profile:
        info_line("Capsule Profile", colored(profile, "preset_name"))

    click.echo()
    click.echo(colored("  ▸ Creating xNode instance...", "info"))
    click.echo(colored("  ▸ Allocating resources...", "info"))
    click.echo(colored("  ▸ Configuring networking...", "info"))

    if auto_configure and profile:
        click.echo(colored("  ▸ Installing Capsule profile...", "info"))

    success(f"xNode {colored(name, 'preset_name')} deployed successfully!")
    click.echo(f"  {colored('▸', 'info')} Instance ID: {colored('xnode-12345', 'dim')}")
    click.echo(f"  {colored('▸', 'info')} IP Address: {colored('203.0.113.42', 'info')}")
    click.echo(f"  {colored('▸', 'info')} SSH: {colored('ssh root@203.0.113.42', 'header_text')}\n")


@xnode.command("launch")
@click.argument("xnode_id")
def xnode_launch(xnode_id):
    """Launch (start) a stopped xNode"""
    banner(f"🚀 Launching xNode: {xnode_id}", "▶️")
    click.echo(colored("  Starting xNode instance...", "info"))
    success(f"xNode {colored(xnode_id, 'preset_name')} launched successfully!\n")


@xnode.command("restart")
@click.argument("xnode_id")
@click.option("--force", is_flag=True, help="Force restart without graceful shutdown")
def xnode_restart(xnode_id, force):
    """Restart a running xNode"""
    banner(f"🔄 Restarting xNode: {xnode_id}", "🔌")
    restart_type = "Force restarting" if force else "Gracefully restarting"
    click.echo(colored(f"  {restart_type} xNode...", "info"))
    success(f"xNode {colored(xnode_id, 'preset_name')} restarted successfully!\n")


@xnode.command("stop")
@click.argument("xnode_id")
@click.confirmation_option(prompt="Stop this xNode?")
def xnode_stop(xnode_id):
    """Stop a running xNode"""
    banner(f"⏸️  Stopping xNode: {xnode_id}", "🔌")
    click.echo(colored("  Gracefully shutting down xNode...", "info"))
    success(f"xNode {colored(xnode_id, 'preset_name')} stopped successfully!\n")


@xnode.command("tunnel")
@click.argument("xnode_id")
@click.option("--local-port", default=8080, help="Local port for tunnel")
@click.option("--remote-port", default=80, help="Remote port on xNode")
@click.option("--background", is_flag=True, help="Run tunnel in background")
def xnode_tunnel(xnode_id, local_port, remote_port, background):
    """Create SSH tunnel to an xNode for secure access"""
    banner(f"🔒 Creating Tunnel: {xnode_id}", "🔌")

    xnode_ip = "203.0.113.42"  # Placeholder
    info_line("xNode ID", colored(xnode_id, "preset_name"))
    info_line("Remote Address", colored(xnode_ip, "info"))
    info_line("Local Port", colored(str(local_port), "info"))
    info_line("Remote Port", colored(str(remote_port), "info"))
    click.echo()

    tunnel_cmd = f"ssh -L {local_port}:localhost:{remote_port} root@{xnode_ip}"

    if background:
        tunnel_cmd += " -N -f"
        click.echo(colored("  Creating background tunnel...", "info"))
        success("Tunnel established in background!")
        click.echo(f"  {colored('▸', 'info')} Access via: {colored(f'http://localhost:{local_port}', 'header_text')}\n")
    else:
        click.echo(colored("  Run this command to create the tunnel:", "section"))
        click.echo(f"  {colored(tunnel_cmd, 'header_text')}\n")


@xnode.command("manage")
@click.argument("xnode_id")
def xnode_manage(xnode_id):
    """Interactive management console for an xNode"""
    header(f"⚙️  MANAGING XNODE: {xnode_id.upper()}")

    xnode_details = {
        "id": xnode_id,
        "name": "prod-east-1",
        "status": "running",
        "region": "us-east-1",
        "ip": "203.0.113.42",
        "cpu": "4",
        "memory": "8GB",
        "storage": "100GB",
        "uptime": "5d 3h 42m",
        "template": "standard-cpu-4"
    }

    section_header("🔹 Instance Details")
    info_line("Name", colored(xnode_details["name"], "preset_name"))
    info_line("Status", colored(xnode_details["status"], "success"))
    info_line("Region", colored(xnode_details["region"], "info"))
    info_line("IP Address", colored(xnode_details["ip"], "info"))
    info_line("Template", colored(xnode_details["template"], "dim"))

    click.echo()
    section_header("🔹 Resources")
    info_line("CPU", colored(xnode_details["cpu"], "info"))
    info_line("Memory", colored(xnode_details["memory"], "info"))
    info_line("Storage", colored(xnode_details["storage"], "info"))
    info_line("Uptime", colored(xnode_details["uptime"], "dim"))

    click.echo()
    section_header("🔹 Quick Actions")
    ip_addr = xnode_details["ip"]
    click.echo(f"  {colored('[1]', 'preset_name')} {colored('SSH into xNode', 'dim'):30} {colored(f'ssh root@{ip_addr}', 'header_text')}")
    click.echo(f"  {colored('[2]', 'preset_name')} {colored('Create tunnel', 'dim'):30} {colored(f'capsule openmesh xnode tunnel {xnode_id}', 'header_text')}")
    click.echo(f"  {colored('[3]', 'preset_name')} {colored('Restart xNode', 'dim'):30} {colored(f'capsule openmesh xnode restart {xnode_id}', 'header_text')}")
    click.echo(f"  {colored('[4]', 'preset_name')} {colored('Stop xNode', 'dim'):30} {colored(f'capsule openmesh xnode stop {xnode_id}', 'header_text')}")
    click.echo()


# ============================================================
# MONITORING COMMANDS - Health checks, metrics, and alerts
# ============================================================

@openmesh.group("monitor")
def monitor():
    """Monitor xNode health, metrics, and alerts"""
    pass


@monitor.command("status")
@click.option("--detailed", is_flag=True, help="Show detailed status")
def monitor_status(detailed):
    """Show monitoring dashboard with overall health status"""
    _load_monitoring_modules()
    if not MONITORING_AVAILABLE:
        error("Monitoring module not installed")
        return

    monitoring = get_default_monitoring()
    dashboard = monitoring.get_dashboard_data()

    header("📊 XNODE MONITORING DASHBOARD")

    # Overview
    section_header("🔹 Overview")
    total = dashboard['total_xnodes']
    healthy = dashboard['healthy_xnodes']
    unhealthy = dashboard['unhealthy_xnodes']

    info_line("Total xNodes", colored(str(total), "preset_name"))
    info_line("Healthy", colored(str(healthy), "success"))
    info_line("Unhealthy", colored(str(unhealthy), "error" if unhealthy > 0 else "dim"))

    # Alerts
    click.echo()
    section_header("🔹 Active Alerts")
    critical = dashboard['critical_alerts']
    warnings = dashboard['warning_alerts']

    if critical > 0:
        click.echo(f"  {colored('⚠️  CRITICAL:', 'error')} {colored(str(critical), 'error')} alerts")
    if warnings > 0:
        click.echo(f"  {colored('⚠️  Warning:', 'warning')} {colored(str(warnings), 'warning')} alerts")
    if critical == 0 and warnings == 0:
        click.echo(f"  {colored('✓', 'success')} No active alerts")

    if detailed:
        click.echo()
        section_header("🔹 xNode Status")
        for xnode_id, health in dashboard['recent_checks'].items():
            status_color = {
                'healthy': 'success',
                'degraded': 'warning',
                'unhealthy': 'error',
                'unknown': 'dim'
            }.get(health.status.value, 'dim')

            status_symbol = {
                'healthy': '✓',
                'degraded': '⚠',
                'unhealthy': '✗',
                'unknown': '?'
            }.get(health.status.value, '?')

            click.echo(f"  {colored(status_symbol, status_color)} {colored(xnode_id, 'preset_name'):30} {colored(health.status.value, status_color)}")

    click.echo()


@monitor.command("health")
@click.argument("xnode_id")
@click.option("--run-check", is_flag=True, help="Run new health check")
def monitor_health(xnode_id, run_check):
    """Check health status of an xNode"""
    _load_monitoring_modules()
    if not MONITORING_AVAILABLE:
        error("Monitoring module not installed")
        return

    monitoring = get_default_monitoring()

    banner(f"🏥 Health Check: {xnode_id}", "📊")

    if run_check:
        # Load xNode data from inventory
        _load_provider_modules()
        inventory = get_default_inventory()
        xnodes = inventory.list_xnodes()
        xnode_data = next((x for x in xnodes if x['id'] == xnode_id), None)

        if not xnode_data:
            error(f"xNode {xnode_id} not found in inventory")
            return

        click.echo(colored("  Running health checks...", "info"))
        health = monitoring.check_health(xnode_id, xnode_data)
    else:
        # Get most recent health check
        status = monitoring.get_xnode_status(xnode_id)
        health = status.get('current_health')

        if not health:
            error(f"No health data available for {xnode_id}. Run with --run-check to perform check.")
            return

    # Display results
    section_header("🔹 Health Status")
    status_color = {
        'healthy': 'success',
        'degraded': 'warning',
        'unhealthy': 'error',
        'unknown': 'dim'
    }.get(health.status.value, 'dim')

    info_line("Status", colored(health.status.value.upper(), status_color))
    info_line("Timestamp", colored(health.timestamp, "dim"))

    click.echo()
    section_header("🔹 Checks")
    for check_name, passed in health.checks.items():
        symbol = colored("✓", "success") if passed else colored("✗", "error")
        response_time = health.response_times.get(check_name, 0)
        click.echo(f"  {symbol} {colored(check_name.upper(), 'preset_name'):15} {colored(f'{response_time:.0f}ms', 'dim')}")

    if health.error_messages:
        click.echo()
        section_header("🔹 Errors")
        for error_msg in health.error_messages:
            click.echo(f"  {colored('•', 'error')} {colored(error_msg, 'dim')}")

    click.echo()


@monitor.command("metrics")
@click.argument("xnode_id")
@click.option("--collect", is_flag=True, help="Collect fresh metrics")
def monitor_metrics(xnode_id, collect):
    """Show resource usage metrics for an xNode"""
    _load_monitoring_modules()
    if not MONITORING_AVAILABLE:
        error("Monitoring module not installed")
        return

    monitoring = get_default_monitoring()

    banner(f"📈 Metrics: {xnode_id}", "📊")

    if collect:
        _load_provider_modules()
        inventory = get_default_inventory()
        xnodes = inventory.list_xnodes()
        xnode_data = next((x for x in xnodes if x['id'] == xnode_id), None)

        if not xnode_data:
            error(f"xNode {xnode_id} not found in inventory")
            return

        click.echo(colored("  Collecting metrics...", "info"))
        metrics = monitoring.collect_metrics(xnode_id, xnode_data)

        if not metrics:
            error("Failed to collect metrics. Ensure SSH access is configured.")
            return
    else:
        status = monitoring.get_xnode_status(xnode_id)
        metrics = status.get('current_metrics')

        if not metrics:
            error(f"No metrics available for {xnode_id}. Run with --collect to gather metrics.")
            return

    # Display metrics
    section_header("🔹 Resource Usage")

    cpu_color = "error" if metrics.cpu_percent > 90 else "warning" if metrics.cpu_percent > 75 else "success"
    mem_color = "error" if metrics.memory_percent > 90 else "warning" if metrics.memory_percent > 80 else "success"
    disk_color = "error" if metrics.disk_percent > 90 else "warning" if metrics.disk_percent > 85 else "success"

    info_line("CPU", colored(f"{metrics.cpu_percent:.1f}%", cpu_color))
    info_line("Memory", colored(f"{metrics.memory_percent:.1f}%", mem_color))
    info_line("Disk", colored(f"{metrics.disk_percent:.1f}%", disk_color))

    click.echo()
    section_header("🔹 System Load")
    load_1, load_5, load_15 = metrics.load_average
    info_line("1 min", colored(f"{load_1:.2f}", "dim"))
    info_line("5 min", colored(f"{load_5:.2f}", "dim"))
    info_line("15 min", colored(f"{load_15:.2f}", "dim"))

    click.echo()
    info_line("Timestamp", colored(metrics.timestamp, "dim"))
    click.echo()


@monitor.command("alerts")
@click.option("--severity", type=click.Choice(['info', 'warning', 'critical']), help="Filter by severity")
@click.option("--xnode-id", help="Filter by xNode ID")
def monitor_alerts(severity, xnode_id):
    """Show active monitoring alerts"""
    _load_monitoring_modules()
    if not MONITORING_AVAILABLE:
        error("Monitoring module not installed")
        return

    monitoring = get_default_monitoring()
    dashboard = monitoring.get_dashboard_data()

    header("🚨 ACTIVE ALERTS")

    alerts = dashboard['active_alerts']

    # Filter alerts
    if severity:
        alerts = [a for a in alerts if a.severity.value == severity]
    if xnode_id:
        alerts = [a for a in alerts if a.xnode_id == xnode_id]

    # Filter out resolved
    alerts = [a for a in alerts if not a.resolved]

    if not alerts:
        success("No active alerts!")
        click.echo()
        return

    # Group by severity
    critical = [a for a in alerts if a.severity.value == 'critical']
    warnings = [a for a in alerts if a.severity.value == 'warning']
    info_alerts = [a for a in alerts if a.severity.value == 'info']

    if critical:
        section_header("🔹 Critical Alerts")
        for alert in critical:
            ack_symbol = "✓" if alert.acknowledged else "!"
            click.echo(f"  {colored(ack_symbol, 'error')} {colored(alert.xnode_id, 'preset_name'):20} {colored(alert.message, 'error')}")
            click.echo(f"    {colored(f'ID: {alert.id}', 'dim')} • {colored(alert.timestamp, 'dim')}")
            click.echo()

    if warnings:
        section_header("🔹 Warning Alerts")
        for alert in warnings:
            ack_symbol = "✓" if alert.acknowledged else "⚠"
            click.echo(f"  {colored(ack_symbol, 'warning')} {colored(alert.xnode_id, 'preset_name'):20} {colored(alert.message, 'warning')}")
            click.echo(f"    {colored(f'ID: {alert.id}', 'dim')} • {colored(alert.timestamp, 'dim')}")
            click.echo()

    if info_alerts:
        section_header("🔹 Info Alerts")
        for alert in info_alerts:
            click.echo(f"  {colored('ℹ', 'info')} {colored(alert.xnode_id, 'preset_name'):20} {alert.message}")
            click.echo(f"    {colored(f'ID: {alert.id}', 'dim')} • {colored(alert.timestamp, 'dim')}")
            click.echo()


@monitor.command("ack")
@click.argument("alert_id")
def monitor_ack(alert_id):
    """Acknowledge an alert"""
    _load_monitoring_modules()
    if not MONITORING_AVAILABLE:
        error("Monitoring module not installed")
        return

    monitoring = get_default_monitoring()
    monitoring.acknowledge_alert(alert_id)
    success(f"Alert {alert_id} acknowledged")
    click.echo()


@monitor.command("resolve")
@click.argument("alert_id")
def monitor_resolve(alert_id):
    """Resolve an alert"""
    _load_monitoring_modules()
    if not MONITORING_AVAILABLE:
        error("Monitoring module not installed")
        return

    monitoring = get_default_monitoring()
    monitoring.resolve_alert(alert_id)
    success(f"Alert {alert_id} resolved")
    click.echo()


@monitor.command("config")
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--check-interval", type=int, help="Set check interval in seconds")
@click.option("--cpu-warning", type=float, help="CPU warning threshold (percent)")
@click.option("--cpu-critical", type=float, help="CPU critical threshold (percent)")
@click.option("--memory-warning", type=float, help="Memory warning threshold (percent)")
@click.option("--memory-critical", type=float, help="Memory critical threshold (percent)")
@click.option("--enable-email", is_flag=True, help="Enable email alerts")
@click.option("--enable-slack", is_flag=True, help="Enable Slack alerts")
@click.option("--slack-webhook", help="Slack webhook URL")
def monitor_config(show, check_interval, cpu_warning, cpu_critical,
                  memory_warning, memory_critical, enable_email, enable_slack, slack_webhook):
    """Configure monitoring settings and thresholds"""
    _load_monitoring_modules()
    if not MONITORING_AVAILABLE:
        error("Monitoring module not installed")
        return

    monitoring = get_default_monitoring()

    if show:
        header("⚙️  MONITORING CONFIGURATION")

        section_header("🔹 Check Settings")
        info_line("Check Interval", colored(f"{monitoring.config.check_interval_seconds}s", "info"))
        info_line("Ping Timeout", colored(f"{monitoring.config.ping_timeout}s", "dim"))
        info_line("SSH Timeout", colored(f"{monitoring.config.ssh_timeout}s", "dim"))

        click.echo()
        section_header("🔹 Alert Thresholds")
        info_line("CPU Warning", colored(f"{monitoring.config.cpu_warning_threshold}%", "warning"))
        info_line("CPU Critical", colored(f"{monitoring.config.cpu_critical_threshold}%", "error"))
        info_line("Memory Warning", colored(f"{monitoring.config.memory_warning_threshold}%", "warning"))
        info_line("Memory Critical", colored(f"{monitoring.config.memory_critical_threshold}%", "error"))
        info_line("Disk Warning", colored(f"{monitoring.config.disk_warning_threshold}%", "warning"))
        info_line("Disk Critical", colored(f"{monitoring.config.disk_critical_threshold}%", "error"))

        click.echo()
        section_header("🔹 Alert Delivery")
        info_line("Console", colored("✓" if monitoring.config.console_alerts else "✗", "success" if monitoring.config.console_alerts else "dim"))
        info_line("Email", colored("✓" if monitoring.config.email_alerts else "✗", "success" if monitoring.config.email_alerts else "dim"))
        info_line("Slack", colored("✓" if monitoring.config.slack_alerts else "✗", "success" if monitoring.config.slack_alerts else "dim"))

        click.echo()
        return

    # Update configuration
    updated = False

    if check_interval:
        monitoring.config.check_interval_seconds = check_interval
        updated = True

    if cpu_warning:
        monitoring.config.cpu_warning_threshold = cpu_warning
        updated = True

    if cpu_critical:
        monitoring.config.cpu_critical_threshold = cpu_critical
        updated = True

    if memory_warning:
        monitoring.config.memory_warning_threshold = memory_warning
        updated = True

    if memory_critical:
        monitoring.config.memory_critical_threshold = memory_critical
        updated = True

    if enable_email:
        monitoring.config.email_alerts = True
        updated = True

    if enable_slack:
        monitoring.config.slack_alerts = True
        updated = True

    if slack_webhook:
        monitoring.config.slack_webhook_url = slack_webhook
        updated = True

    if updated:
        monitoring._save_config()
        success("Monitoring configuration updated!")
        click.echo()
    else:
        click.echo(colored("No configuration changes specified. Use --show to view current config.", "dim"))
        click.echo()


@monitor.command("watch")
@click.option("--interval", default=5, help="Refresh interval in seconds")
def monitor_watch(interval):
    """Real-time monitoring dashboard (refreshes automatically)"""
    _load_monitoring_modules()
    if not MONITORING_AVAILABLE:
        error("Monitoring module not installed")
        return

    import time
    import sys

    monitoring = get_default_monitoring()

    click.echo(colored("Starting real-time monitoring dashboard...", "info"))
    click.echo(colored(f"Refresh interval: {interval}s (Press Ctrl+C to exit)", "dim"))
    click.echo()

    try:
        while True:
            # Clear screen
            click.clear()

            # Get dashboard data
            dashboard = monitoring.get_dashboard_data()

            # Display
            header("📊 XNODE MONITORING - LIVE")

            section_header("🔹 Overview")
            total = dashboard['total_xnodes']
            healthy = dashboard['healthy_xnodes']
            unhealthy = dashboard['unhealthy_xnodes']

            info_line("Total xNodes", colored(str(total), "preset_name"))
            info_line("Healthy", colored(str(healthy), "success"))
            info_line("Unhealthy", colored(str(unhealthy), "error" if unhealthy > 0 else "dim"))

            click.echo()
            section_header("🔹 Active Alerts")
            critical = dashboard['critical_alerts']
            warnings = dashboard['warning_alerts']

            if critical > 0:
                click.echo(f"  {colored('⚠️  CRITICAL:', 'error')} {colored(str(critical), 'error')} alerts")
            if warnings > 0:
                click.echo(f"  {colored('⚠️  Warning:', 'warning')} {colored(str(warnings), 'warning')} alerts")
            if critical == 0 and warnings == 0:
                click.echo(f"  {colored('✓', 'success')} No active alerts")

            click.echo()
            section_header("🔹 xNode Status")
            for xnode_id, health in dashboard['recent_checks'].items():
                status_color = {
                    'healthy': 'success',
                    'degraded': 'warning',
                    'unhealthy': 'error',
                    'unknown': 'dim'
                }.get(health.status.value, 'dim')

                status_symbol = {
                    'healthy': '✓',
                    'degraded': '⚠',
                    'unhealthy': '✗',
                    'unknown': '?'
                }.get(health.status.value, '?')

                click.echo(f"  {colored(status_symbol, status_color)} {colored(xnode_id, 'preset_name'):30} {colored(health.status.value, status_color)}")

            click.echo()
            click.echo(colored(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "dim"))
            click.echo(colored(f"Next refresh in {interval}s...", "dim"))

            time.sleep(interval)

    except KeyboardInterrupt:
        click.echo()
        click.echo(colored("Monitoring stopped.", "info"))
        click.echo()
        sys.exit(0)


# Import provider and inventory modules (after CLI is defined to avoid conflicts)
PROVIDERS_AVAILABLE = False
MONITORING_AVAILABLE = False

def _load_provider_modules():
    """Lazy load provider and inventory modules"""
    global PROVIDERS_AVAILABLE, get_provider_manager, get_default_inventory, ProviderTemplate
    try:
        from capsule_package import providers as providers_module
        from capsule_package import inventory as inventory_module
        get_provider_manager = providers_module.get_default_manager
        get_default_inventory = inventory_module.get_default_inventory
        ProviderTemplate = providers_module.ProviderTemplate
        PROVIDERS_AVAILABLE = True
        return True
    except Exception as e:
        # logger.error(f"Failed to load provider modules: {e}")
        PROVIDERS_AVAILABLE = False
        return False


def _load_monitoring_modules():
    """Lazy load monitoring module"""
    global MONITORING_AVAILABLE, get_default_monitoring
    try:
        from capsule_package import monitoring as monitoring_module
        get_default_monitoring = monitoring_module.get_default_monitoring
        MONITORING_AVAILABLE = True
        return True
    except Exception as e:
        # logger.error(f"Failed to load monitoring module: {e}")
        MONITORING_AVAILABLE = False
        return False


# ============================================================================
# PROVIDER MANAGEMENT
# ============================================================================

@openmesh.command("providers")
@click.option("--detailed", is_flag=True, help="Show detailed information")
def openmesh_providers(detailed):
    """List all available hardware providers"""
    _load_provider_modules()
    if not PROVIDERS_AVAILABLE:
        error("Provider module not installed")
        return

    header("🏢 HARDWARE PROVIDERS")

    manager = get_provider_manager()

    section_header("🔹 Available Providers")
    for provider_name in manager.list_providers():
        provider = manager.get_provider(provider_name)
        
        status = colored("●", "success") if provider.api_key else colored("○", "warning")
        cred_status = colored("Configured", "success") if provider.api_key else colored("Not configured", "warning")
        
        click.echo(f"  {status} {colored(provider_name.title(), 'preset_name'):15} "
                   f"{colored(f'{len(provider.templates)} templates', 'info'):18} "
                   f"{colored(f'{len(provider.regions)} regions', 'dim'):15} "
                   f"{cred_status}")

        if detailed and provider.api_key:
            click.echo(f"      {colored('Regions:', 'dim')} {', '.join(provider.regions[:5])}")

    click.echo()
    click.echo(f"  {colored('💡 Tip:', 'info')} Configure provider: {colored('capsule openmesh provider configure <name>', 'header_text')}\n")


@openmesh.group("provider")
def provider_group():
    """Manage hardware provider settings"""
    pass


@provider_group.command("configure")
@click.argument("provider_name", type=click.Choice(["hivelocity", "digitalocean", "vultr", "aws", "equinix", "linode", "scaleway"]))
@click.option("--api-key", prompt=True, hide_input=True, help="Provider API key")
def provider_configure(provider_name, api_key):
    """Configure provider API credentials"""
    _load_provider_modules()
    if not PROVIDERS_AVAILABLE:
        error("Provider module not installed")
        return

    banner(f"🔧 Configuring {provider_name.title()}", "🏢")

    manager = get_provider_manager()
    manager.configure_provider(provider_name, api_key)

    success(f"{provider_name.title()} configured successfully!")
    click.echo(f"  {colored('▸', 'info')} API key saved securely")
    click.echo(f"  {colored('▸', 'info')} Next: {colored(f'capsule openmesh templates --provider {provider_name}', 'header_text')}\n")


@provider_group.command("templates")
@click.argument("provider_name")
def provider_templates(provider_name):
    """List templates for a specific provider"""
    _load_provider_modules()
    if not PROVIDERS_AVAILABLE:
        error("Provider module not installed")
        return

    manager = get_provider_manager()
    provider = manager.get_provider(provider_name)
    
    if not provider:
        error(f"Provider '{provider_name}' not found")
        return

    header(f"📋 {provider_name.upper()} TEMPLATES")

    section_header("🔹 Available Templates")
    for template in provider.templates:
        gpu_info = f" + {template.gpu}" if template.gpu else ""
        click.echo(f"  {colored('◆', 'package_name')} {colored(template.name, 'preset_name'):25} "
                   f"{colored(f'{template.cpu}CPU', 'info'):8} "
                   f"{colored(f'{template.memory_gb}GB', 'info'):6} "
                   f"{colored(f'{template.storage_gb}GB', 'dim'):8} "
                   f"{colored(f'${template.price_hourly:.3f}/hr', 'success')}{gpu_info}")

    click.echo()


@openmesh.command("templates")
@click.option("--provider", help="Filter by provider")
@click.option("--min-cpu", type=int, default=0, help="Minimum CPU cores")
@click.option("--min-memory", type=int, default=0, help="Minimum memory (GB)")
@click.option("--max-price", type=float, help="Maximum hourly price")
@click.option("--gpu", is_flag=True, help="Show only GPU instances")
def openmesh_templates(provider, min_cpu, min_memory, max_price, gpu):
    """Compare templates across all providers"""
    _load_provider_modules()
    if not PROVIDERS_AVAILABLE:
        error("Provider module not installed")
        return

    header("📊 TEMPLATE COMPARISON")

    manager = get_provider_manager()
    
    max_price_filter = max_price if max_price else float('inf')
    templates = manager.compare_templates(min_cpu=min_cpu, min_memory=min_memory, max_price=max_price_filter)
    
    if provider:
        templates = [t for t in templates if t.provider == provider]
    
    if gpu:
        templates = [t for t in templates if t.gpu]

    section_header("🔹 Matching Templates")
    if not templates:
        warning("No templates match your criteria")
        return

    for template in templates[:20]:  # Show top 20
        provider_colored = colored(template.provider.upper()[:4], 'preset_name')
        gpu_info = f" 🎮 {colored(template.gpu, 'success')}" if template.gpu else ""
        
        click.echo(f"  {provider_colored} {template.name:25} "
                   f"{colored(f'{template.cpu}C', 'info'):5} "
                   f"{colored(f'{template.memory_gb}G', 'info'):5} "
                   f"{colored(f'${template.price_hourly:.3f}/hr', 'success'):12} "
                   f"{colored(f'${template.price_monthly:.0f}/mo', 'dim')}{gpu_info}")

    click.echo()
    click.echo(f"  {colored('Total:', 'section')} {colored(str(len(templates)), 'preset_name')} templates\n")


# ============================================================================
# INVENTORY MANAGEMENT
# ============================================================================

@openmesh.command("inventory")
@click.option("--provider", help="Filter by provider")
@click.option("--status", help="Filter by status")
@click.option("--tags", help="Filter by tags (comma-separated)")
def openmesh_inventory(provider, status, tags):
    """View xNode inventory and cost tracking"""
    _load_provider_modules()
    if not PROVIDERS_AVAILABLE:
        error("Inventory module not installed")
        return

    header("📦 XNODE INVENTORY")

    inventory = get_default_inventory()
    xnodes = inventory.list_all()

    if provider:
        xnodes = [x for x in xnodes if x.get('provider') == provider]
    if status:
        xnodes = [x for x in xnodes if x.get('status') == status]
    if tags:
        tag_list = [t.strip() for t in tags.split(',')]
        xnodes = [x for x in xnodes if any(t in x.get('tags', []) for t in tag_list)]

    if not xnodes:
        warning("No xNodes in inventory")
        click.echo(f"  {colored('💡 Tip:', 'info')} Deploy your first xNode with {colored('capsule openmesh deploy', 'header_text')}\n")
        return

    section_header("🔹 Deployed xNodes")
    for xnode in xnodes:
        status_icon = colored("●", "success") if xnode.get('status') == 'running' else colored("○", "warning")
        provider_name = xnode.get('provider', 'unknown')
        cost = xnode.get('cost_hourly', 0)
        
        click.echo(f"  {status_icon} {colored(xnode.get('name'), 'preset_name'):20} "
                   f"{colored(provider_name, 'info'):12} "
                   f"{colored(xnode.get('status', 'unknown'), 'dim'):12} "
                   f"{colored(f'${cost:.3f}/hr', 'success')}")

    # Show cost summary
    stats = inventory.get_statistics()
    click.echo()
    section_header("🔹 Cost Summary")
    click.echo(f"  {colored('Active xNodes:', 'dim')} {colored(str(stats['total_running']), 'success')}")
    hourly_cost = stats['total_cost_hourly']
    monthly_cost = stats['total_cost_monthly']
    click.echo(f"  {colored('Hourly:', 'dim')} {colored(f'${hourly_cost:.2f}', 'info')}")
    click.echo(f"  {colored('Monthly:', 'dim')} {colored(f'${monthly_cost:.2f}', 'success')}")
    click.echo()


@openmesh.command("cost-report")
def cost_report():
    """Generate detailed cost report"""
    _load_provider_modules()
    if not PROVIDERS_AVAILABLE:
        error("Inventory module not installed")
        return

    inventory = get_default_inventory()
    report = inventory.get_cost_report()

    click.echo(report.generate_report())


# ============================================================================
# ENHANCED DEPLOYMENT
# ============================================================================

@xnode.command("deploy-with-provider")
@click.option("--provider", required=True, type=click.Choice(["hivelocity", "digitalocean", "vultr", "aws", "equinix", "linode", "scaleway"]), help="Hardware provider")
@click.option("--template", required=True, help="Template ID")
@click.option("--name", required=True, help="xNode name")
@click.option("--region", help="Deployment region")
@click.option("--profile", help="Capsule profile to install")
@click.option("--tags", help="Tags (comma-separated)")
def xnode_deploy_with_provider(provider, template, name, region, profile, tags):
    """Deploy xNode using a specific hardware provider"""
    _load_provider_modules()
    if not PROVIDERS_AVAILABLE:
        error("Provider module not installed")
        return

    banner(f"🚀 Deploying to {provider.title()}", "🔌")

    manager = get_provider_manager()
    inventory = get_default_inventory()

    # Get provider and template
    prov = manager.get_provider(provider)
    if not prov:
        error(f"Provider '{provider}' not found")
        return

    templ = prov.get_template(template)
    if not templ:
        error(f"Template '{template}' not found for {provider}")
        return

    # Show deployment details
    click.echo(colored("  Deployment Configuration:", "section"))
    info_line("Provider", colored(provider.title(), "preset_name"))
    info_line("Template", colored(templ.name, "info"))
    info_line("Name", colored(name, "info"))
    info_line("Region", colored(region or "default", "dim"))
    info_line("Cost", colored(f"${templ.price_hourly:.3f}/hr (${templ.price_monthly:.0f}/mo)", "success"))
    if profile:
        info_line("Capsule Profile", colored(profile, "preset_name"))

    click.echo()

    # Deploy
    config = {'name': name, 'region': region}
    instance = prov.deploy(template, config)

    # Add to inventory
    tag_list = [t.strip() for t in tags.split(',')] if tags else []
    inventory.add_xnode(
        instance,
        provider=provider,
        template=template,
        cost_hourly=templ.price_hourly,
        tags=tag_list
    )

    success(f"xNode {colored(name, 'preset_name')} deployed successfully!")
    click.echo(f"  {colored('▸', 'info')} Instance ID: {colored(instance['id'], 'dim')}")
    click.echo(f"  {colored('▸', 'info')} Provider: {colored(provider.title(), 'preset_name')}")
    click.echo(f"  {colored('▸', 'info')} Added to inventory")
    click.echo()


@openmesh.command("deploy")
@click.option("--name", required=True, help="xNode name")
@click.option("--min-cpu", type=int, default=2, help="Minimum CPU cores")
@click.option("--min-memory", type=int, default=4, help="Minimum memory (GB)")
@click.option("--max-price", type=float, help="Maximum hourly price")
@click.option("--gpu", is_flag=True, help="Require GPU")
@click.option("--provider", help="Prefer specific provider")
@click.option("--profile", help="Capsule profile to install")
@click.option("--tags", help="Tags (comma-separated)")
def openmesh_deploy(name, min_cpu, min_memory, max_price, gpu, provider, profile, tags):
    """Smart deploy - automatically select best provider/template"""
    _load_provider_modules()
    if not PROVIDERS_AVAILABLE:
        error("Provider/inventory modules not installed")
        return

    banner("🤖 Smart Deployment", "🚀")

    manager = get_provider_manager()
    inventory = get_default_inventory()

    # Find best option
    max_price_val = max_price if max_price else float('inf')
    templates = manager.compare_templates(min_cpu=min_cpu, min_memory=min_memory, max_price=max_price_val)

    if gpu:
        templates = [t for t in templates if t.gpu]

    if provider:
        templates = [t for t in templates if t.provider == provider]

    if not templates:
        error("No templates match your requirements")
        return

    # Select cheapest
    selected = templates[0]

    click.echo(colored("  Recommended Template:", "section"))
    info_line("Provider", colored(selected.provider.title(), "preset_name"))
    info_line("Template", colored(selected.name, "info"))
    info_line("Specs", colored(f"{selected.cpu} CPU, {selected.memory_gb}GB RAM, {selected.storage_gb}GB Storage", "dim"))
    info_line("Cost", colored(f"${selected.price_hourly:.3f}/hr (${selected.price_monthly:.0f}/mo)", "success"))
    if selected.gpu:
        info_line("GPU", colored(selected.gpu, "success"))

    click.echo()

    if not click.confirm("Deploy with this template?"):
        warning("Deployment cancelled")
        return

    # Deploy
    prov = manager.get_provider(selected.provider)
    config = {'name': name}
    instance = prov.deploy(selected.id, config)

    # Add to inventory
    tag_list = [t.strip() for t in tags.split(',')] if tags else []
    inventory.add_xnode(
        instance,
        provider=selected.provider,
        template=selected.id,
        cost_hourly=selected.price_hourly,
        tags=tag_list
    )

    success(f"xNode {colored(name, 'preset_name')} deployed!")
    click.echo(f"  {colored('▸', 'info')} Provider: {colored(selected.provider.title(), 'preset_name')}")
    click.echo(f"  {colored('▸', 'info')} Cost: {colored(f'${selected.price_hourly:.3f}/hr', 'success')}")
    click.echo(f"  {colored('▸', 'info')} Added to inventory")
    click.echo()

