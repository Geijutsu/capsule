// Core configuration types and utilities for Capsule

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use anyhow::{Context, Result};

/// Capsule configuration profile
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub presets: Vec<String>,
    #[serde(default)]
    pub custom_packages: Vec<String>,
    #[serde(default)]
    pub editor: Option<String>,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            description: Some("Default configuration".to_string()),
            presets: vec!["base".to_string()],
            custom_packages: vec![],
            editor: Some("vim".to_string()),
        }
    }
}

/// Preset/Stack definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Preset {
    pub name: String,
    pub description: String,
    #[serde(default)]
    pub category: Option<String>,
    #[serde(default)]
    pub packages: Vec<String>,
    #[serde(default)]
    pub dependencies: Vec<String>,
    #[serde(default)]
    pub optional_dependencies: Vec<OptionalDependency>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum OptionalDependency {
    Simple(String),
    Detailed {
        name: String,
        description: String,
    },
}

/// Get Capsule config directory
pub fn get_capsule_dir() -> PathBuf {
    dirs::home_dir()
        .expect("Could not find home directory")
        .join(".capsule")
}

/// Get presets directory
pub fn get_presets_dir() -> PathBuf {
    // Check if presets directory exists relative to binary
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()));
    
    if let Some(exe_dir) = exe_dir {
        let presets_path = exe_dir.join("../share/capsule/presets");
        if presets_path.exists() {
            return presets_path;
        }
    }
    
    // Fall back to development path
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("capsule_package/presets")
}

/// Load configuration from file
pub fn load_config(profile_name: Option<&str>) -> Result<Config> {
    let config_dir = get_capsule_dir().join("configs");
    let config_file = if let Some(name) = profile_name {
        config_dir.join(format!("{}.yml", name))
    } else {
        config_dir.join("default.yml")
    };

    if !config_file.exists() {
        return Ok(Config::default());
    }

    let contents = std::fs::read_to_string(&config_file)
        .context(format!("Failed to read config file: {:?}", config_file))?;
    let config: Config = serde_yaml::from_str(&contents)
        .context("Failed to parse config YAML")?;
    Ok(config)
}

/// Save configuration to file
pub fn save_config(config: &Config, profile_name: Option<&str>) -> Result<()> {
    let config_dir = get_capsule_dir().join("configs");
    std::fs::create_dir_all(&config_dir)
        .context("Failed to create config directory")?;

    let config_file = if let Some(name) = profile_name {
        config_dir.join(format!("{}.yml", name))
    } else {
        config_dir.join("default.yml")
    };

    let contents = serde_yaml::to_string(config)
        .context("Failed to serialize config")?;
    std::fs::write(config_file, contents)
        .context("Failed to write config file")?;
    Ok(())
}

/// Load a preset by name
pub fn load_preset(name: &str) -> Result<Option<Preset>> {
    let preset_file = get_presets_dir().join(format!("{}.yml", name));

    if !preset_file.exists() {
        return Ok(None);
    }

    let contents = std::fs::read_to_string(&preset_file)
        .context(format!("Failed to read preset file: {:?}", preset_file))?;
    let preset: Preset = serde_yaml::from_str(&contents)
        .context("Failed to parse preset YAML")?;
    Ok(Some(preset))
}

/// Resolve preset dependencies recursively
pub fn resolve_dependencies(preset_name: &str) -> Result<Vec<String>> {
    let mut resolved = Vec::new();
    let mut visiting = std::collections::HashSet::new();

    resolve_dependencies_inner(preset_name, &mut resolved, &mut visiting)?;

    Ok(resolved)
}

fn resolve_dependencies_inner(
    preset_name: &str,
    resolved: &mut Vec<String>,
    visiting: &mut std::collections::HashSet<String>,
) -> Result<()> {
    if visiting.contains(preset_name) || resolved.contains(&preset_name.to_string()) {
        return Ok(());
    }

    visiting.insert(preset_name.to_string());

    if let Some(preset) = load_preset(preset_name)? {
        // Resolve dependencies first
        for dep in &preset.dependencies {
            resolve_dependencies_inner(dep, resolved, visiting)?;
        }

        if !resolved.contains(&preset_name.to_string()) {
            resolved.push(preset_name.to_string());
        }
    }

    visiting.remove(preset_name);
    Ok(())
}

/// Collect all packages from config
pub fn collect_packages(config: &Config) -> Result<(Vec<String>, HashMap<String, Vec<String>>)> {
    let mut all_packages = Vec::new();
    let mut packages_by_preset = HashMap::new();

    // Base packages
    let base_packages = vec![
        "git".to_string(),
        "curl".to_string(),
        "wget".to_string(),
        "vim".to_string(),
        "htop".to_string(),
        "unzip".to_string(),
    ];
    packages_by_preset.insert("base".to_string(), base_packages.clone());
    all_packages.extend(base_packages);

    // Resolve and collect preset packages
    for preset_name in &config.presets {
        if preset_name == "base" {
            continue;
        }

        let resolved = resolve_dependencies(preset_name)?;
        for stack in resolved {
            if packages_by_preset.contains_key(&stack) {
                continue;
            }

            if let Some(preset) = load_preset(&stack)? {
                if !preset.packages.is_empty() {
                    packages_by_preset.insert(stack.clone(), preset.packages.clone());
                    all_packages.extend(preset.packages);
                }
            }
        }
    }

    // Add custom packages
    if !config.custom_packages.is_empty() {
        packages_by_preset.insert("custom".to_string(), config.custom_packages.clone());
        all_packages.extend(config.custom_packages.clone());
    }

    // Remove duplicates while preserving order
    let mut seen = std::collections::HashSet::new();
    let unique_packages: Vec<String> = all_packages
        .into_iter()
        .filter(|pkg| seen.insert(pkg.clone()))
        .collect();

    Ok((unique_packages, packages_by_preset))
}

/// List all available presets
pub fn list_presets() -> Result<Vec<String>> {
    let presets_dir = get_presets_dir();
    let mut presets = Vec::new();

    if !presets_dir.exists() {
        return Ok(presets);
    }

    for entry in std::fs::read_dir(presets_dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().and_then(|s| s.to_str()) == Some("yml") {
            if let Some(name) = path.file_stem().and_then(|s| s.to_str()) {
                presets.push(name.to_string());
            }
        }
    }

    presets.sort();
    Ok(presets)
}

/// Get the active configuration name from ~/.capsule/active.txt
pub fn get_active_config_name() -> Result<String> {
    let active_file = get_capsule_dir().join("active.txt");

    if !active_file.exists() {
        std::fs::create_dir_all(get_capsule_dir())?;
        std::fs::write(&active_file, "default")?;
        return Ok("default".to_string());
    }

    Ok(std::fs::read_to_string(&active_file)?.trim().to_string())
}

/// Set the active configuration name
pub fn set_active_config_name(name: &str) -> Result<()> {
    let capsule_dir = get_capsule_dir();
    std::fs::create_dir_all(&capsule_dir)?;
    std::fs::write(capsule_dir.join("active.txt"), name)?;
    Ok(())
}

/// Get the path to a config file
pub fn get_config_file(name: Option<&str>) -> Result<PathBuf> {
    let name = match name {
        Some(n) => n.to_string(),
        None => get_active_config_name()?,
    };

    let configs_dir = get_capsule_dir().join("configs");
    std::fs::create_dir_all(&configs_dir)?;

    Ok(configs_dir.join(format!("{}.yml", name)))
}

/// List all user configuration files
pub fn list_all_configs() -> Result<Vec<String>> {
    let configs_dir = get_capsule_dir().join("configs");

    if !configs_dir.exists() {
        return Ok(Vec::new());
    }

    let mut names = Vec::new();
    for entry in std::fs::read_dir(configs_dir)? {
        let entry = entry?;
        let path = entry.path();

        if path.extension().and_then(|s| s.to_str()) == Some("yml") {
            if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                names.push(stem.to_string());
            }
        }
    }

    names.sort();
    Ok(names)
}

/// Built-in profile configurations
pub fn builtin_profiles() -> HashMap<String, Config> {
    let mut profiles = HashMap::new();

    profiles.insert(
        "dev".to_string(),
        Config {
            description: Some("Full-stack development environment".to_string()),
            presets: vec![
                "base".to_string(),
                "python".to_string(),
                "nodejs".to_string(),
                "docker".to_string(),
                "github".to_string(),
                "cli-tools".to_string(),
            ],
            custom_packages: vec!["tmux".to_string(), "htop".to_string(), "jq".to_string()],
            editor: Some("vim".to_string()),
        },
    );

    profiles.insert(
        "prod".to_string(),
        Config {
            description: Some("Production web server with security".to_string()),
            presets: vec![
                "base".to_string(),
                "webserver".to_string(),
                "security".to_string(),
                "monitoring".to_string(),
            ],
            custom_packages: vec!["fail2ban".to_string()],
            editor: Some("vim".to_string()),
        },
    );

    profiles.insert(
        "ml".to_string(),
        Config {
            description: Some("Machine learning workstation".to_string()),
            presets: vec![
                "base".to_string(),
                "python".to_string(),
                "machine-learning".to_string(),
                "ollama".to_string(),
            ],
            custom_packages: vec!["htop".to_string(), "nvtop".to_string()],
            editor: Some("vim".to_string()),
        },
    );

    profiles.insert(
        "ml-gpu".to_string(),
        Config {
            description: Some("ML workstation with GPU support".to_string()),
            presets: vec![
                "base".to_string(),
                "python".to_string(),
                "machine-learning".to_string(),
                "ollama".to_string(),
                "cuda".to_string(),
            ],
            custom_packages: vec!["htop".to_string(), "nvtop".to_string()],
            editor: Some("vim".to_string()),
        },
    );

    profiles.insert(
        "web".to_string(),
        Config {
            description: Some("Web development environment".to_string()),
            presets: vec![
                "base".to_string(),
                "nodejs".to_string(),
                "docker".to_string(),
                "github".to_string(),
            ],
            custom_packages: vec!["tmux".to_string()],
            editor: Some("vim".to_string()),
        },
    );

    profiles.insert(
        "minimal".to_string(),
        Config {
            description: Some("Minimal setup with essential tools only".to_string()),
            presets: vec!["base".to_string()],
            custom_packages: vec!["tmux".to_string(), "htop".to_string()],
            editor: Some("vim".to_string()),
        },
    );

    profiles
}

/// List built-in profile names
pub fn list_builtin_profiles() -> Vec<String> {
    let mut names: Vec<String> = builtin_profiles().keys().cloned().collect();
    names.sort();
    names
}

/// Check if a profile name is a built-in profile
pub fn is_builtin_profile(name: &str) -> bool {
    builtin_profiles().contains_key(name)
}

/// Get a built-in profile configuration
pub fn get_builtin_profile(name: &str) -> Option<Config> {
    builtin_profiles().get(name).cloned()
}

/// Ensure config file exists, creating default if needed
pub fn ensure_config(name: Option<&str>) -> Result<PathBuf> {
    let config_file = get_config_file(name)?;

    if !config_file.exists() {
        let default_config = Config::default();
        save_config(&default_config, name)?;
    }

    Ok(config_file)
}

/// Copy a profile from src to dst
pub fn copy_profile(src: &str, dst: &str) -> Result<()> {
    let src_config = load_config(Some(src))?;
    save_config(&src_config, Some(dst))?;
    Ok(())
}

/// Delete a user profile
pub fn delete_profile(name: &str) -> Result<()> {
    if is_builtin_profile(name) {
        anyhow::bail!("Cannot delete built-in profile: {}", name);
    }

    let config_file = get_config_file(Some(name))?;

    if !config_file.exists() {
        anyhow::bail!("Profile not found: {}", name);
    }

    // Don't allow deleting the active profile
    let active = get_active_config_name()?;
    if active == name {
        anyhow::bail!("Cannot delete the active profile. Switch to another profile first.");
    }

    std::fs::remove_file(&config_file)?;
    Ok(())
}

/// Add a preset (stack) to the configuration
pub fn add_preset(preset: &str, name: Option<&str>) -> Result<()> {
    let config_name = match name {
        Some(n) => n.to_string(),
        None => get_active_config_name()?,
    };

    if is_builtin_profile(&config_name) {
        anyhow::bail!(
            "Cannot modify built-in profile '{}'. Create a new profile or switch to a user profile.",
            config_name
        );
    }

    let mut config = load_config(Some(&config_name))?;

    if !config.presets.contains(&preset.to_string()) {
        config.presets.push(preset.to_string());
        save_config(&config, Some(&config_name))?;
    }

    Ok(())
}

/// Remove a preset (stack) from the configuration
pub fn remove_preset(preset: &str, name: Option<&str>) -> Result<()> {
    let config_name = match name {
        Some(n) => n.to_string(),
        None => get_active_config_name()?,
    };

    if is_builtin_profile(&config_name) {
        anyhow::bail!(
            "Cannot modify built-in profile '{}'. Create a new profile or switch to a user profile.",
            config_name
        );
    }

    let mut config = load_config(Some(&config_name))?;
    config.presets.retain(|p| p != preset);
    save_config(&config, Some(&config_name))?;

    Ok(())
}

/// Add custom packages to the configuration
pub fn add_packages(packages: &[String], name: Option<&str>) -> Result<()> {
    let config_name = match name {
        Some(n) => n.to_string(),
        None => get_active_config_name()?,
    };

    if is_builtin_profile(&config_name) {
        anyhow::bail!(
            "Cannot modify built-in profile '{}'. Create a new profile or switch to a user profile.",
            config_name
        );
    }

    let mut config = load_config(Some(&config_name))?;

    for package in packages {
        if !config.custom_packages.contains(package) {
            config.custom_packages.push(package.clone());
        }
    }

    save_config(&config, Some(&config_name))?;
    Ok(())
}

/// Remove custom packages from the configuration
pub fn remove_packages(packages: &[String], name: Option<&str>) -> Result<()> {
    let config_name = match name {
        Some(n) => n.to_string(),
        None => get_active_config_name()?,
    };

    if is_builtin_profile(&config_name) {
        anyhow::bail!(
            "Cannot modify built-in profile '{}'. Create a new profile or switch to a user profile.",
            config_name
        );
    }

    let mut config = load_config(Some(&config_name))?;

    for package in packages {
        config.custom_packages.retain(|p| p != package);
    }

    save_config(&config, Some(&config_name))?;
    Ok(())
}
