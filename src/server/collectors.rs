use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::process::Command;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PackageInfo {
    pub name: String,
    pub version: String,
    pub architecture: String,
    pub manually_installed: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceInfo {
    pub name: String,
    pub enabled: bool,
    pub running: bool,
    pub unit_file: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserInfo {
    pub username: String,
    pub uid: u32,
    pub gid: u32,
    pub home: String,
    pub shell: String,
    pub groups: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemSnapshot {
    pub packages: Vec<PackageInfo>,
    pub services: Vec<ServiceInfo>,
    pub users: Vec<UserInfo>,
    pub hostname: String,
    pub os_version: String,
}

pub fn collect_packages() -> Result<Vec<PackageInfo>> {
    let mut packages = Vec::new();

    // Get all installed packages
    let output = Command::new("dpkg-query")
        .args(&["-W", "-f=${Package}|${Version}|${Architecture}\\n"])
        .output()
        .context("Failed to query installed packages")?;

    let dpkg_output = String::from_utf8_lossy(&output.stdout);

    // Get manually installed packages
    let manual_output = Command::new("apt-mark")
        .arg("showmanual")
        .output()
        .context("Failed to get manually installed packages")?;

    let manual_packages: std::collections::HashSet<String> = String::from_utf8_lossy(&manual_output.stdout)
        .lines()
        .map(|s| s.trim().to_string())
        .collect();

    // Parse dpkg output
    for line in dpkg_output.lines() {
        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() >= 3 {
            let name = parts[0].trim().to_string();
            packages.push(PackageInfo {
                manually_installed: manual_packages.contains(&name),
                name,
                version: parts[1].trim().to_string(),
                architecture: parts[2].trim().to_string(),
            });
        }
    }

    Ok(packages)
}

pub fn collect_services() -> Result<Vec<ServiceInfo>> {
    let mut services = Vec::new();

    // Get all services
    let output = Command::new("systemctl")
        .args(&["list-unit-files", "--type=service", "--no-pager", "--no-legend"])
        .output()
        .context("Failed to list systemd services")?;

    let systemctl_output = String::from_utf8_lossy(&output.stdout);

    for line in systemctl_output.lines() {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() >= 2 {
            let service_name = parts[0].to_string();
            let state = parts[1];

            // Check if service is running
            let running = Command::new("systemctl")
                .args(&["is-active", &service_name])
                .output()
                .map(|o| String::from_utf8_lossy(&o.stdout).trim() == "active")
                .unwrap_or(false);

            // Only include enabled or running services
            if state == "enabled" || running {
                // Try to get unit file content
                let unit_file = read_service_file(&service_name).ok();

                services.push(ServiceInfo {
                    name: service_name,
                    enabled: state == "enabled",
                    running,
                    unit_file,
                });
            }
        }
    }

    Ok(services)
}

fn read_service_file(service_name: &str) -> Result<String> {
    // Try to read from /etc/systemd/system first (custom services)
    let custom_path = format!("/etc/systemd/system/{}", service_name);
    if std::path::Path::new(&custom_path).exists() {
        return std::fs::read_to_string(&custom_path)
            .context("Failed to read service file");
    }

    // Try /lib/systemd/system
    let system_path = format!("/lib/systemd/system/{}", service_name);
    if std::path::Path::new(&system_path).exists() {
        return std::fs::read_to_string(&system_path)
            .context("Failed to read service file");
    }

    anyhow::bail!("Service file not found")
}

pub fn collect_users() -> Result<Vec<UserInfo>> {
    let mut users = Vec::new();

    // Read /etc/passwd
    let passwd_content = std::fs::read_to_string("/etc/passwd")
        .context("Failed to read /etc/passwd")?;

    for line in passwd_content.lines() {
        let parts: Vec<&str> = line.split(':').collect();
        if parts.len() >= 7 {
            let username = parts[0].to_string();
            let uid: u32 = parts[2].parse().unwrap_or(0);
            let gid: u32 = parts[3].parse().unwrap_or(0);

            // Skip system users (uid < 1000) except root
            if uid < 1000 && uid != 0 {
                continue;
            }

            // Get user's groups
            let groups_output = Command::new("groups")
                .arg(&username)
                .output()
                .ok()
                .and_then(|o| String::from_utf8(o.stdout).ok())
                .unwrap_or_default();

            let groups: Vec<String> = groups_output
                .split(':')
                .nth(1)
                .unwrap_or("")
                .split_whitespace()
                .map(|s| s.to_string())
                .collect();

            users.push(UserInfo {
                username,
                uid,
                gid,
                home: parts[5].to_string(),
                shell: parts[6].to_string(),
                groups,
            });
        }
    }

    Ok(users)
}
