use anyhow::{Context, Result};
use std::fs;
use std::path::Path;

use super::collectors::SystemSnapshot;
use super::package_mapper::PackageMapper;

pub struct NixConfigGenerator {
    snapshot: SystemSnapshot,
    mapper: PackageMapper,
}

impl NixConfigGenerator {
    pub fn new(snapshot: SystemSnapshot) -> Self {
        Self {
            snapshot,
            mapper: PackageMapper::new(),
        }
    }

    pub fn generate(&self, output_dir: &Path) -> Result<()> {
        // Create subdirectories
        let services_dir = output_dir.join("services");
        fs::create_dir_all(&services_dir)?;

        // Generate main configuration
        self.generate_main_config(output_dir)?;

        // Generate packages.nix
        self.generate_packages_nix(output_dir)?;

        // Generate users.nix
        self.generate_users_nix(output_dir)?;

        // Generate service files
        self.generate_service_files(&services_dir)?;

        Ok(())
    }

    fn generate_main_config(&self, output_dir: &Path) -> Result<()> {
        let config = format!(
            r#"# Capsule Server Snapshot Configuration
# Generated from: {}
# OS: {}

{{ config, pkgs, ... }}:

{{
  # Import modular configurations
  imports = [
    ./packages.nix
    ./users.nix
  ];

  # System metadata
  networking.hostName = "{}";

  # Nix settings
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # Enable common services
  services.openssh.enable = true;

  # System packages
  environment.systemPackages = with pkgs; [
    vim
    git
    curl
    wget
    htop
  ];
}}
"#,
            self.snapshot.hostname,
            self.snapshot.os_version,
            self.snapshot.hostname
        );

        fs::write(output_dir.join("configuration.nix"), config)
            .context("Failed to write configuration.nix")
    }

    fn generate_packages_nix(&self, output_dir: &Path) -> Result<()> {
        let mut nix_packages = Vec::new();
        let mut unmapped = Vec::new();

        // Map packages
        for pkg in &self.snapshot.packages {
            // Skip system packages
            if self.mapper.is_system_package(&pkg.name) {
                continue;
            }

            // Only include manually installed packages to avoid bloat
            if pkg.manually_installed {
                if let Some(nix_name) = self.mapper.map(&pkg.name) {
                    nix_packages.push(nix_name);
                } else {
                    unmapped.push(pkg.name.clone());
                }
            }
        }

        // Remove duplicates
        nix_packages.sort();
        nix_packages.dedup();

        let mut config = String::from(
            r#"# Package Configuration
# This file lists all packages to be installed

{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
"#,
        );

        for pkg in &nix_packages {
            config.push_str(&format!("    {}\n", pkg));
        }

        config.push_str("  ];\n");

        if !unmapped.is_empty() {
            config.push_str("\n  # Unmapped packages (manual installation may be required):\n");
            for pkg in &unmapped {
                config.push_str(&format!("  # - {}\n", pkg));
            }
        }

        config.push_str("}\n");

        fs::write(output_dir.join("packages.nix"), config)
            .context("Failed to write packages.nix")
    }

    fn generate_users_nix(&self, output_dir: &Path) -> Result<()> {
        let mut config = String::from(
            r#"# User Configuration
# This file defines system users and groups

{ config, pkgs, ... }:

{
  users.users = {
"#,
        );

        for user in &self.snapshot.users {
            // Skip root - it's always present
            if user.username == "root" {
                continue;
            }

            config.push_str(&format!("    {} = {{\n", user.username));
            config.push_str("      isNormalUser = true;\n");
            config.push_str(&format!("      home = \"{}\";\n", user.home));
            config.push_str(&format!("      shell = pkgs.{};\n", shell_to_nix(&user.shell)));

            if !user.groups.is_empty() {
                let groups: Vec<String> = user.groups
                    .iter()
                    .filter(|g| *g != &user.username) // Filter out primary group
                    .map(|g| format!("\"{}\"", g))
                    .collect();

                if !groups.is_empty() {
                    config.push_str(&format!("      extraGroups = [ {} ];\n", groups.join(" ")));
                }
            }

            config.push_str(&format!("      uid = {};\n", user.uid));
            config.push_str("    };\n\n");
        }

        config.push_str("  };\n}\n");

        fs::write(output_dir.join("users.nix"), config)
            .context("Failed to write users.nix")
    }

    fn generate_service_files(&self, services_dir: &Path) -> Result<()> {
        for service in &self.snapshot.services {
            // Only save custom service files (from /etc/systemd/system)
            if let Some(ref content) = service.unit_file {
                let service_path = services_dir.join(&service.name);
                fs::write(service_path, content)
                    .context(format!("Failed to write service file: {}", service.name))?;
            }
        }

        // Create a manifest of services
        let mut manifest = String::from("# Service Manifest\n\n");
        manifest.push_str("## Enabled Services\n\n");

        for service in &self.snapshot.services {
            if service.enabled {
                manifest.push_str(&format!(
                    "- {} ({})\n",
                    service.name,
                    if service.running { "running" } else { "stopped" }
                ));
            }
        }

        fs::write(services_dir.join("MANIFEST.md"), manifest)
            .context("Failed to write service manifest")?;

        Ok(())
    }
}

fn shell_to_nix(shell: &str) -> &str {
    match shell {
        "/bin/bash" | "/usr/bin/bash" => "bash",
        "/bin/zsh" | "/usr/bin/zsh" => "zsh",
        "/bin/fish" | "/usr/bin/fish" => "fish",
        "/bin/sh" => "bash", // Default to bash for sh
        _ => "bash",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_shell_conversion() {
        assert_eq!(shell_to_nix("/bin/bash"), "bash");
        assert_eq!(shell_to_nix("/bin/zsh"), "zsh");
        assert_eq!(shell_to_nix("/usr/bin/fish"), "fish");
        assert_eq!(shell_to_nix("/bin/sh"), "bash");
    }
}
