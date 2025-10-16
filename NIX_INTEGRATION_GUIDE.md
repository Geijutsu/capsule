# Nix Integration & NixOS Generator - Integration Guide

## Overview

This guide describes the Nix integration system created for the Rust rewrite of Capsule with exact parity to the Python version.

## Created Files

### Core Modules

1. **src/config.rs** - Configuration management
   - Config types (Config, Preset, OptionalDependency)
   - Config file loading/saving
   - Preset management
   - Dependency resolution
   - Package collection

2. **src/ui.rs** - Terminal UI utilities
   - Header, section, divider functions
   - Success, error, warning messages
   - Info lines and banner
   - Capsule logo display

3. **src/nix.rs** - Nix command execution
   - `generate_nix_config()` - Generate Nix configuration from profile
   - `run_nix_env()` - Run nix-env to install packages
   - `run_nix_build()` - Run nix-build
   - `validate_nix_syntax()` - Validate using nix-instantiate
   - `check_nix_installed()` - Check if Nix is available
   - `check_nixos_available()` - Check if NixOS commands available
   - `run_nixos_rebuild()` - Run nixos-rebuild
   - `list_generations()` - List NixOS generations

4. **src/nixos.rs** - NixOS configuration generator
   - `NixOSConfigGenerator` - Main generator class
   - `generate_configuration_nix()` - Generate configuration.nix
   - `generate_home_manager()` - Generate home.nix
   - `generate_flake_nix()` - Generate flake.nix
   - `generate_hardware_config()` - Generate hardware-configuration.nix
   - `generate_all()` - Generate all files + README
   - `detect_services()` - Service mapping (docker → virtualisation.docker.enable, etc.)
   - `validate_config()` - Validate syntax
   - `test_in_vm()` - Build and test VM

5. **src/main_nixos_additions.rs** - Command handlers and CLI additions

## Integration Steps

### Step 1: Update src/lib.rs

Uncomment or add the nix and nixos modules:

```rust
pub mod config;
pub mod nix;
pub mod nixos;
pub mod ui;

pub use config::*;
pub use nix::*;
pub use nixos::*;
pub use ui::*;
```

### Step 2: Update src/main.rs

Add to the imports at the top:

```rust
use capsule::nix::*;
use capsule::nixos::*;
use std::path::PathBuf;
```

Add these commands to the `Commands` enum:

```rust
    /// Install packages using Nix
    Setup {
        /// Dry run mode (check what would be installed)
        #[arg(long)]
        check: bool,
        /// Verbose output level
        #[arg(short, long, action = clap::ArgAction::Count)]
        verbose: u8,
    },

    /// Dry run - check what would be changed
    Check {
        /// Verbose output level
        #[arg(short, long, action = clap::ArgAction::Count)]
        verbose: u8,
    },

    /// Preview generated Nix configuration
    Preview,

    /// NixOS configuration generation and management
    Nixos {
        #[command(subcommand)]
        command: NixOSCommands,
    },
```

Add the `NixOSCommands` enum (see src/main_nixos_additions.rs).

Add these match arms to the main match statement:

```rust
        Some(Commands::Setup { check, verbose }) => cmd_setup(check, verbose)?,
        Some(Commands::Check { verbose }) => cmd_check(verbose)?,
        Some(Commands::Preview) => cmd_preview()?,
        Some(Commands::Nixos { command }) => handle_nixos_command(command)?,
```

Add the handler functions from src/main_nixos_additions.rs to the bottom of main.rs.

### Step 3: Update Cargo.toml dependencies

Already added:
- chrono = { version = "0.4", features = ["serde"] }
- dirs = "5.0"
- colored = "2.1"
- anyhow = "1.0"
- serde_yaml = "0.9"

## Commands Implemented

### Package Management

```bash
# Install packages
capsule setup

# Dry run
capsule check

# Preview Nix configuration
capsule preview
```

### NixOS Configuration Generation

```bash
# Generate all NixOS config files
capsule nixos generate

# Generate with custom options
capsule nixos generate --output /path/to/output \
                       --hostname myserver \
                       --username myuser

# Generate specific files
capsule nixos generate --home-manager
capsule nixos generate --flake
capsule nixos generate --hardware

# Validate configuration
capsule nixos validate
capsule nixos validate --config /path/to/configuration.nix

# Test in VM
capsule nixos test
capsule nixos test --config-dir /path/to/nixos

# Apply configuration (requires NixOS)
capsule nixos apply
capsule nixos apply --flake

# Rollback to previous generation
capsule nixos rollback

# List generations
capsule nixos list-generations
```

## Key Features

1. **Package Organization** - Automatically groups packages by preset/stack
2. **Service Detection** - Maps presets to NixOS services (docker → virtualisation.docker.enable)
3. **Template-based** - Uses string templates for config generation
4. **Validation** - Syntax validation with nix-instantiate
5. **VM Testing** - Build and test configs in a VM before deployment
6. **Generation Management** - List and rollback generations
7. **Flake Support** - Modern Nix flakes configuration
8. **Home Manager** - User-level package management

## Service Mappings

Current service mappings in `detect_services()`:

- `docker` → `virtualisation.docker.enable = true`
- `webserver` → `services.nginx.enable = true` + firewall ports
- `database` → `services.postgresql.enable = true`
- `monitoring` → `services.prometheus.enable + services.grafana.enable`

## Generated Files

When running `capsule nixos generate`, the following files are created:

1. **configuration.nix** - Main system configuration
   - Boot loader settings
   - Network configuration
   - User accounts
   - Services
   - System packages
   - Firewall rules
   - Nix settings

2. **home.nix** - Home Manager configuration
   - User packages
   - Shell configuration
   - Editor settings
   - Git configuration
   - Direnv setup

3. **flake.nix** - Modern Nix flakes configuration
   - Inputs (nixpkgs, home-manager)
   - System configuration
   - Home Manager integration

4. **hardware-configuration.nix** - Hardware-specific settings
   - Auto-detected if `nixos-generate-config` is available
   - Template provided otherwise

5. **README.md** - Usage instructions

## Example Usage Flow

```bash
# 1. Configure your profile
capsule add python
capsule add docker
capsule add github
capsule pkg add tmux htop jq

# 2. Preview what will be generated
capsule preview

# 3. Generate NixOS configuration
capsule nixos generate --hostname myserver --username myuser

# 4. Validate the configuration
capsule nixos validate

# 5. Test in a VM (optional but recommended)
capsule nixos test

# 6. Deploy to NixOS system
cd ~/.capsule/nixos
sudo cp *.nix /etc/nixos/
sudo nixos-rebuild switch

# Or with flakes:
sudo nixos-rebuild switch --flake ~/.capsule/nixos#myserver
```

## Testing

Unit tests are included in both modules:

```bash
cargo test
```

## Notes

- The preset files need to be available at runtime (currently expects them in `capsule_package/presets/`)
- Hardware detection requires `nixos-generate-config` to be available
- NixOS commands (`nixos-rebuild`, etc.) require running on NixOS
- Nix package installation works on any system with Nix installed

## Python Parity Checklist

✅ Generate Nix configuration from profiles
✅ Run nix-env commands
✅ Parse Nix output
✅ Handle Nix flakes
✅ Generate configuration.nix
✅ Generate home.nix (Home Manager)
✅ Generate flake.nix
✅ Generate hardware-configuration.nix
✅ Service mapping (docker → virtualisation.docker.enable, etc.)
✅ Validation with nix-instantiate
✅ VM testing support
✅ Rollback and generation management
✅ All CLI commands implemented

## Future Enhancements

- Remote deployment support
- More service mappings
- Custom service templates
- Backup/restore of configurations
- Migration from other package managers
