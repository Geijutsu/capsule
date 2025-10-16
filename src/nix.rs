// Nix integration module for Capsule

use crate::config::{collect_packages, load_preset, Config};
use crate::ui::{error, info_line, success};
use anyhow::{Context, Result};
use std::path::Path;
use std::process::{Command, Stdio};

/// Generate Nix configuration from profile
pub fn generate_nix_config(config: &Config) -> Result<String> {
    let (unique_packages, packages_by_preset) = collect_packages(config)?;

    let mut lines = Vec::new();

    // Header
    lines.push("{ config, pkgs, ... }:".to_string());
    lines.push("{".to_string());
    lines.push("  # Capsule-generated configuration".to_string());
    lines.push(format!(
        "  # Generated from profile: {}",
        config.description.as_ref().unwrap_or(&"custom".to_string())
    ));
    lines.push("".to_string());
    lines.push("  environment.systemPackages = with pkgs; [".to_string());

    // Add packages grouped by preset
    for preset_name in ["base", "custom"]
        .iter()
        .copied()
        .chain(config.presets.iter().map(|s| s.as_str()))
    {
        if let Some(packages) = packages_by_preset.get(preset_name) {
            if packages.is_empty() {
                continue;
            }

            // Add comment for this preset
            let description = if preset_name == "base" {
                "Base system packages".to_string()
            } else if preset_name == "custom" {
                "Custom packages".to_string()
            } else if let Ok(Some(preset)) = load_preset(preset_name) {
                preset.description
            } else {
                preset_name.to_string()
            };

            lines.push(format!("    # {}", description));
            for pkg in packages {
                lines.push(format!("    {}", pkg));
            }
            lines.push("".to_string());
        }
    }

    lines.push("  ];".to_string());
    lines.push("}".to_string());

    Ok(lines.join("\n"))
}

/// Run nix-env command to install packages
pub fn run_nix_env(config: &Config, check: bool, verbose: u8) -> Result<i32> {
    let (packages, _) = collect_packages(config)?;

    if packages.is_empty() {
        error("No packages to install");
        return Ok(1);
    }

    // Build nix-env command
    let mut cmd = Command::new("nix-env");
    cmd.arg("-iA");

    // Add nixpkgs prefix to packages
    for pkg in &packages {
        cmd.arg(format!("nixpkgs.{}", pkg));
    }

    // Add flags
    if check {
        cmd.arg("--dry-run");
    }

    if verbose > 0 {
        for _ in 0..verbose.min(4) {
            cmd.arg("-v");
        }
    }

    // Print command if verbose
    if verbose > 0 || check {
        println!("\nRunning: {:?}\n", cmd);
    }

    // Execute command
    let status = cmd
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status()
        .context("Failed to execute nix-env")?;

    if status.success() {
        if !check {
            success("Nix packages installed successfully!");
        } else {
            info_line("Dry-run", "No changes made");
        }
        Ok(0)
    } else {
        error(&format!(
            "Nix installation failed with exit code: {}",
            status.code().unwrap_or(-1)
        ));
        Ok(status.code().unwrap_or(1))
    }
}

/// Run nix-build command
pub fn run_nix_build(nix_file: &Path, verbose: bool) -> Result<i32> {
    let mut cmd = Command::new("nix-build");
    cmd.arg(nix_file);

    if verbose {
        cmd.arg("--verbose");
    }

    if verbose {
        println!("\nRunning: {:?}\n", cmd);
    }

    let status = cmd
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status()
        .context("Failed to execute nix-build")?;

    Ok(status.code().unwrap_or(1))
}

/// Validate Nix configuration syntax using nix-instantiate
pub fn validate_nix_syntax(nix_file: &Path) -> Result<bool> {
    let output = Command::new("nix-instantiate")
        .arg("--parse")
        .arg(nix_file)
        .output()
        .context("Failed to execute nix-instantiate")?;

    if output.status.success() {
        Ok(true)
    } else {
        eprintln!("Validation error: {}", String::from_utf8_lossy(&output.stderr));
        Ok(false)
    }
}

/// Check if Nix is installed
pub fn check_nix_installed() -> bool {
    Command::new("nix-env")
        .arg("--version")
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

/// Check if NixOS commands are available
pub fn check_nixos_available() -> bool {
    Command::new("nixos-rebuild")
        .arg("--help")
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

/// Run nixos-rebuild command
pub fn run_nixos_rebuild(
    action: &str,
    config_dir: Option<&Path>,
    flake: bool,
) -> Result<i32> {
    let mut cmd = Command::new("sudo");
    cmd.arg("nixos-rebuild");
    cmd.arg(action);

    if let Some(dir) = config_dir {
        if flake {
            let hostname = std::env::var("HOSTNAME").unwrap_or_else(|_| "nixos".to_string());
            cmd.arg("--flake");
            cmd.arg(format!("{}#{}", dir.display(), hostname));
        } else {
            cmd.arg("-I");
            cmd.arg(format!("nixos-config={}/configuration.nix", dir.display()));
        }
    }

    println!("\nRunning: {:?}\n", cmd);

    let status = cmd
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status()
        .context("Failed to execute nixos-rebuild")?;

    Ok(status.code().unwrap_or(1))
}

/// List NixOS generations
pub fn list_generations() -> Result<Vec<String>> {
    let output = Command::new("nixos-rebuild")
        .arg("list-generations")
        .output()
        .context("Failed to execute nixos-rebuild list-generations")?;

    if output.status.success() {
        let generations_str = String::from_utf8_lossy(&output.stdout);
        Ok(generations_str.lines().map(|s| s.to_string()).collect())
    } else {
        Ok(Vec::new())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_nix_config() {
        let config = Config::default();
        let result = generate_nix_config(&config);
        assert!(result.is_ok());
        let nix_config = result.unwrap();
        assert!(nix_config.contains("environment.systemPackages"));
        assert!(nix_config.contains("git"));
    }
}
