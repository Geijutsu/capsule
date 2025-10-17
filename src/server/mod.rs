use anyhow::{Context, Result};
use colored::*;
use std::path::Path;
use std::process::Command;
use std::fs;

mod collectors;
mod nix_generator;
mod package_mapper;
mod checksum;

use collectors::SystemSnapshot;
use nix_generator::NixConfigGenerator;
use checksum::ChecksumManifest;

pub fn pack(output_dir: &Path) -> Result<()> {
    println!("{}", "📸 Creating server snapshot...".cyan().bold());
    println!();

    // Create output directory
    fs::create_dir_all(output_dir)
        .context("Failed to create output directory")?;

    println!("{} Analyzing system...", "▸".green().bold());

    // Collect system information
    let snapshot = collect_system_snapshot()?;

    println!("{} Found {} packages", "  ✓".green(), snapshot.packages.len());
    println!("{} Found {} services", "  ✓".green(), snapshot.services.len());
    println!("{} Found {} users", "  ✓".green(), snapshot.users.len());
    println!();

    // Generate Nix configuration
    println!("{} Generating Nix configuration...", "▸".green().bold());
    let generator = NixConfigGenerator::new(snapshot);
    generator.generate(output_dir)?;

    println!("{} Created configuration.nix", "  ✓".green());
    println!("{} Created packages.nix", "  ✓".green());
    println!("{} Created users.nix", "  ✓".green());
    println!("{} Created services/", "  ✓".green());
    println!();

    // Save README
    let readme = generate_readme();
    fs::write(output_dir.join("README.md"), readme)?;
    println!("{} Created README.md", "  ✓".green());
    println!();

    // Generate checksums
    println!("{} Generating checksums...", "▸".green().bold());
    let manifest = ChecksumManifest::generate(output_dir)?;
    let checksum_file = output_dir.join("checksums.json");
    manifest.save(&checksum_file)?;
    println!("{} Created checksums.json ({} files)", "  ✓".green(), manifest.files.len());
    println!();

    println!(
        "{} Snapshot created successfully at: {}",
        "✅".green(),
        output_dir.display().to_string().cyan()
    );
    println!();
    println!(
        "{} To validate: {} {}",
        "💡 Tip:".yellow(),
        "capsule server validate".cyan().bold(),
        output_dir.display().to_string().cyan()
    );
    println!(
        "{} To restore: {} {}",
        "💡 Tip:".yellow(),
        "capsule server unpack".cyan().bold(),
        output_dir.display().to_string().cyan()
    );
    println!();

    Ok(())
}

pub fn unpack(snapshot_dir: &Path, dry_run: bool) -> Result<()> {
    if dry_run {
        println!("{}", "🔍 Dry run - showing what would be done".cyan().bold());
    } else {
        println!("{}", "📦 Restoring server from snapshot...".cyan().bold());
    }
    println!();

    // Validate snapshot directory
    if !snapshot_dir.exists() {
        anyhow::bail!("Snapshot directory not found: {}", snapshot_dir.display());
    }

    let config_file = snapshot_dir.join("configuration.nix");
    if !config_file.exists() {
        anyhow::bail!("Invalid snapshot: configuration.nix not found");
    }

    println!("{} Checking Nix installation...", "▸".green().bold());

    let nix_installed = Command::new("nix")
        .arg("--version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);

    if !nix_installed {
        println!("{} Nix not found - installing...", "  !".yellow());
        if !dry_run {
            install_nix()?;
            println!("{} Nix installed successfully", "  ✓".green());
        } else {
            println!("{} Would install Nix package manager", "  →".cyan());
        }
    } else {
        println!("{} Nix is already installed", "  ✓".green());
    }
    println!();

    println!("{} Applying Nix configuration...", "▸".green().bold());
    if !dry_run {
        apply_nix_config(snapshot_dir)?;
        println!("{} Configuration applied", "  ✓".green());
    } else {
        println!("{} Would apply Nix configuration from {}",
            "  →".cyan(), config_file.display());
    }
    println!();

    println!("{} Restoring configuration files...", "▸".green().bold());
    let etc_overrides = snapshot_dir.join("etc-overrides");
    if etc_overrides.exists() {
        if !dry_run {
            restore_etc_overrides(&etc_overrides)?;
            println!("{} Configuration files restored", "  ✓".green());
        } else {
            println!("{} Would restore files from etc-overrides/", "  →".cyan());
        }
    } else {
        println!("{} No etc-overrides found", "  ○".white());
    }
    println!();

    println!("{} Enabling and starting services...", "▸".green().bold());
    if !dry_run {
        enable_services(snapshot_dir)?;
        println!("{} Services started", "  ✓".green());
    } else {
        println!("{} Would enable and start systemd services", "  →".cyan());
    }
    println!();

    if dry_run {
        println!("{} Dry run complete - no changes made", "✅".green());
    } else {
        println!("{} Server restoration complete!", "✅".green());
        println!();
        println!("{} Validate services with: {}",
            "💡 Tip:".yellow(),
            "systemctl status".cyan().bold());
    }
    println!();

    Ok(())
}

fn collect_system_snapshot() -> Result<SystemSnapshot> {
    let packages = collectors::collect_packages()?;
    let services = collectors::collect_services()?;
    let users = collectors::collect_users()?;

    Ok(SystemSnapshot {
        packages,
        services,
        users,
        hostname: get_hostname()?,
        os_version: get_os_version()?,
    })
}

fn get_hostname() -> Result<String> {
    let output = Command::new("hostname")
        .output()
        .context("Failed to get hostname")?;

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn get_os_version() -> Result<String> {
    let output = Command::new("lsb_release")
        .arg("-d")
        .arg("-s")
        .output()
        .context("Failed to get OS version")?;

    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

fn install_nix() -> Result<()> {
    println!("{} Installing Nix package manager...", "  ▸".cyan());

    let status = Command::new("sh")
        .arg("-c")
        .arg("curl -L https://nixos.org/nix/install | sh -s -- --daemon")
        .status()
        .context("Failed to install Nix")?;

    if !status.success() {
        anyhow::bail!("Nix installation failed");
    }

    Ok(())
}

fn apply_nix_config(snapshot_dir: &Path) -> Result<()> {
    let config_file = snapshot_dir.join("configuration.nix");

    // For Ubuntu with Nix, we use nix-env to install packages
    // rather than full NixOS system activation
    let status = Command::new("sh")
        .arg("-c")
        .arg(format!(
            "nix-env -iA nixpkgs -f {}",
            config_file.display()
        ))
        .status()
        .context("Failed to apply Nix configuration")?;

    if !status.success() {
        anyhow::bail!("Failed to apply Nix configuration");
    }

    Ok(())
}

fn restore_etc_overrides(etc_dir: &Path) -> Result<()> {
    // Copy files from etc-overrides to /etc/
    // This requires root permissions
    let status = Command::new("sudo")
        .arg("cp")
        .arg("-r")
        .arg(etc_dir.to_str().unwrap())
        .arg("/etc/")
        .status()
        .context("Failed to restore etc files")?;

    if !status.success() {
        anyhow::bail!("Failed to restore /etc/ files");
    }

    Ok(())
}

fn enable_services(snapshot_dir: &Path) -> Result<()> {
    let services_dir = snapshot_dir.join("services");

    if !services_dir.exists() {
        return Ok(());
    }

    for entry in fs::read_dir(&services_dir)? {
        let entry = entry?;
        let path = entry.path();

        if path.extension().and_then(|s| s.to_str()) == Some("service") {
            let service_name = path.file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("");

            // Copy service file
            Command::new("sudo")
                .arg("cp")
                .arg(&path)
                .arg(format!("/etc/systemd/system/{}", service_name))
                .status()?;

            // Enable and start service
            Command::new("sudo")
                .arg("systemctl")
                .arg("enable")
                .arg(service_name)
                .status()?;

            Command::new("sudo")
                .arg("systemctl")
                .arg("start")
                .arg(service_name)
                .status()?;
        }
    }

    // Reload systemd
    Command::new("sudo")
        .arg("systemctl")
        .arg("daemon-reload")
        .status()?;

    Ok(())
}

pub fn validate(snapshot_dir: &Path, verbose: bool) -> Result<()> {
    println!("{}", "🔍 Validating snapshot integrity...".cyan().bold());
    println!();

    // Check if snapshot exists
    if !snapshot_dir.exists() {
        anyhow::bail!("Snapshot directory not found: {}", snapshot_dir.display());
    }

    // Load checksums manifest
    let checksum_file = snapshot_dir.join("checksums.json");
    if !checksum_file.exists() {
        anyhow::bail!("Checksum manifest not found. This snapshot may have been created with an older version of capsule.");
    }

    println!("{} Loading checksum manifest...", "▸".green().bold());
    let manifest = ChecksumManifest::load(&checksum_file)?;
    println!("{} Loaded {} file checksums", "  ✓".green(), manifest.files.len());
    println!();

    // Display manifest metadata
    println!("{} Snapshot Information:", "▸".cyan().bold());
    println!("  {} {}", "Version:".white().bold(), manifest.version.cyan());
    println!("  {} {}", "Created:".white().bold(), manifest.created_at.cyan());
    println!();

    // Validate files
    println!("{} Validating files...", "▸".green().bold());
    let report = manifest.validate(snapshot_dir, verbose)?;

    if !verbose {
        println!("{} Checked {} files", "  ▸".cyan(), report.total_files);
    }
    println!();

    // Display results
    use prettytable::{Table, Row, Cell, format};
    let mut table = Table::new();
    table.set_format(*format::consts::FORMAT_NO_BORDER_LINE_SEPARATOR);

    table.add_row(Row::new(vec![
        Cell::new("Status").style_spec("Fb"),
        Cell::new("Count").style_spec("Fb"),
    ]));

    table.add_row(Row::new(vec![
        Cell::new("✓ Valid").style_spec("Fg"),
        Cell::new(&report.valid_files.to_string()).style_spec("Fg"),
    ]));

    if report.invalid_files > 0 {
        table.add_row(Row::new(vec![
            Cell::new("✗ Invalid").style_spec("Fr"),
            Cell::new(&report.invalid_files.to_string()).style_spec("Fr"),
        ]));
    }

    if report.missing_files > 0 {
        table.add_row(Row::new(vec![
            Cell::new("⚠ Missing").style_spec("Fy"),
            Cell::new(&report.missing_files.to_string()).style_spec("Fy"),
        ]));
    }

    table.printstd();
    println!();

    // Display errors if any
    if !report.errors.is_empty() {
        println!("{} Issues Found:", "▸".red().bold());
        println!();

        for error in &report.errors {
            match &error.error_type {
                checksum::ErrorType::Missing => {
                    println!("  {} {} {}", "✗".red().bold(), "Missing:".red(), error.file.white());
                }
                checksum::ErrorType::Mismatch => {
                    println!("  {} {} {}", "✗".red().bold(), "Checksum mismatch:".red(), error.file.white());
                    if verbose {
                        if let Some(ref expected) = error.expected {
                            println!("    {} {}", "Expected:".yellow(), expected.white());
                        }
                        if let Some(ref actual) = error.actual {
                            println!("    {} {}", "Actual:  ".yellow(), actual.white());
                        }
                    }
                }
                checksum::ErrorType::ReadError(msg) => {
                    println!("  {} {} {} ({})", "✗".red().bold(), "Read error:".red(), error.file.white(), msg.yellow());
                }
            }
        }
        println!();
    }

    // Final verdict
    if report.is_valid() {
        println!("{} Snapshot validation passed!", "✅".green());
        println!();
        println!("{} All {} files verified successfully",
            "▸".green().bold(),
            report.valid_files);
    } else {
        println!("{} Snapshot validation failed!", "❌".red());
        println!();
        println!("{} {} issues detected:",
            "▸".red().bold(),
            report.invalid_files + report.missing_files);
        println!("  {} {} corrupted or modified files", "▸".red(), report.invalid_files);
        println!("  {} {} missing files", "▸".yellow(), report.missing_files);
        println!();

        anyhow::bail!("Snapshot integrity check failed");
    }

    println!();
    Ok(())
}

fn generate_readme() -> String {
    r#"# Capsule Server Snapshot

This snapshot was created by the `capsule` CLI tool.

## Contents

- `configuration.nix` - Main Nix configuration
- `packages.nix` - Package definitions
- `users.nix` - User account definitions
- `services/` - SystemD service files
- `etc-overrides/` - Configuration files that can't be declaratively managed
- `checksums.json` - File integrity checksums

## Validation

To validate snapshot integrity:

```bash
capsule server validate ./capsule-snapshot
capsule server validate --verbose ./capsule-snapshot  # Show all file checks
```

## Restoration

To restore this snapshot on a new server:

```bash
capsule server unpack ./capsule-snapshot
```

### Dry Run

To preview what would be done without making changes:

```bash
capsule server unpack --dry-run ./capsule-snapshot
```

## Requirements

- Ubuntu 20.04+ (recommended)
- Root/sudo access
- Internet connection (for installing Nix and packages)

## What Gets Restored

✅ System packages (via Nix)
✅ User accounts and groups
✅ SystemD services
✅ Configuration files
✅ Service startup configuration

## Manual Steps

Some things may require manual intervention:

- Database data (backup/restore separately)
- SSL certificates
- Application secrets
- Custom compiled software

## Generated

This snapshot was created with Capsule - a user-friendly server configuration tool.
"#.to_string()
}
