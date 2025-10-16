# Capsule Nix Integration - Quick Reference

## Files Created

### Core Modules (✅ Complete)
- `/src/config.rs` - Config management and preset handling
- `/src/ui.rs` - Terminal UI utilities
- `/src/nix.rs` - Nix command execution
- `/src/nixos.rs` - NixOS configuration generator
- `/src/main_nixos_additions.rs` - CLI command implementations

### Documentation
- `/NIX_INTEGRATION_GUIDE.md` - Complete integration guide
- `/QUICK_REFERENCE.md` - This file

## Quick Integration

### 1. Update `src/lib.rs`

Uncomment these lines (currently commented):

```rust
pub mod nix;
pub mod nixos;

pub use nix::*;
pub use nixos::*;
```

### 2. Update `src/main.rs`

Add imports:
```rust
use capsule::nix::*;
use capsule::nixos::*;
use std::path::PathBuf;
```

Copy enums and functions from `src/main_nixos_additions.rs`

### 3. Build

```bash
cd /Users/joshkornreich/Documents/Projects/CLIs/seed/capsule
cargo build
```

## Command Quick Reference

```bash
# Package Management
capsule setup                    # Install packages
capsule check                    # Dry run
capsule preview                  # Show Nix config

# NixOS Generation
capsule nixos generate           # Generate all configs
capsule nixos validate           # Validate syntax
capsule nixos test              # Test in VM
capsule nixos apply             # Apply to system
capsule nixos rollback          # Rollback
capsule nixos list-generations  # List generations
```

## Architecture

```
capsule::config
├── Config - Main configuration type
├── Preset - Stack/preset definition
├── load_config() - Load from file
├── save_config() - Save to file
├── collect_packages() - Gather all packages
└── resolve_dependencies() - Resolve preset deps

capsule::nix
├── generate_nix_config() - Generate Nix expression
├── run_nix_env() - Install packages
├── validate_nix_syntax() - Validate with nix-instantiate
└── run_nixos_rebuild() - Apply NixOS config

capsule::nixos
├── NixOSConfigGenerator
│   ├── generate_configuration_nix() - System config
│   ├── generate_home_manager() - User config
│   ├── generate_flake_nix() - Flakes config
│   ├── generate_hardware_config() - Hardware config
│   ├── detect_services() - Service mapping
│   └── generate_all() - Generate everything
├── validate_config() - Validate syntax
└── test_in_vm() - Build VM for testing
```

## Python → Rust Mapping

| Python | Rust | Location |
|--------|------|----------|
| `generate_nix_config()` | `generate_nix_config()` | src/nix.rs |
| `run_nix()` | `run_nix_env()` | src/nix.rs |
| `NixOSConfigGenerator` | `NixOSConfigGenerator` | src/nixos.rs |
| `generate_configuration_nix()` | `generate_configuration_nix()` | src/nixos.rs |
| `generate_home_manager()` | `generate_home_manager()` | src/nixos.rs |
| `generate_flake_nix()` | `generate_flake_nix()` | src/nixos.rs |
| `validate_config()` | `validate_config()` | src/nixos.rs |
| `test_in_vm()` | `test_in_vm()` | src/nixos.rs |

## Dependencies Added to Cargo.toml

- ✅ `chrono` - Timestamps in generated configs
- ✅ `dirs` - Home directory resolution
- ✅ `colored` - Terminal colors
- ✅ `serde_yaml` - YAML parsing
- ✅ `anyhow` - Error handling

## Testing

```bash
# Run unit tests
cargo test

# Test specific module
cargo test --lib nix
cargo test --lib nixos

# Build and install
cargo build --release
cargo install --path .
```

## Example Workflow

```bash
# 1. Add stacks
capsule add python
capsule add docker

# 2. Add packages
capsule pkg add tmux htop

# 3. Preview
capsule preview

# 4. Generate NixOS config
capsule nixos generate --hostname myserver

# 5. Review
ls ~/.capsule/nixos/

# 6. Validate
capsule nixos validate

# 7. Deploy
sudo cp ~/.capsule/nixos/*.nix /etc/nixos/
sudo nixos-rebuild switch
```

## Service Mappings

When you add these presets, the following services are automatically configured:

- `docker` → `virtualisation.docker.enable = true`
- `webserver` → `services.nginx.enable = true`
- `database` → `services.postgresql.enable = true`
- `monitoring` → `services.prometheus.enable + services.grafana.enable`

## Notes

- All modules have unit tests
- Error handling uses `anyhow::Result`
- Terminal output uses `colored` crate
- Config files are YAML format
- Preset files expected in `capsule_package/presets/`

## Integration Status

| Component | Status |
|-----------|--------|
| Config module | ✅ Complete |
| UI module | ✅ Complete |
| Nix module | ✅ Complete |
| NixOS module | ✅ Complete |
| CLI commands | ✅ Ready to integrate |
| Unit tests | ✅ Included |
| Documentation | ✅ Complete |
