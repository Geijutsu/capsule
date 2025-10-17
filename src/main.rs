use anyhow::Result;
use clap::{Parser, Subcommand};
use colored::*;

use capsule::config::*;
use capsule::openmesh::{handle_openmesh_command, handle_xnode_command, OpenMeshCommands, XnodeCommands};
use capsule::ui::*;
use capsule::datastore::DataStore;

mod server;

#[derive(Parser)]
#[command(name = "capsule")]
#[command(version = "0.1.0")]
#[command(about = "🌱 Capsule - User-friendly server configuration tool", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Show current configuration
    Show,

    /// List available technology stacks
    Stacks,

    /// Add a technology stack to current profile
    Add {
        /// Stack name to add
        stack: String,
    },

    /// Remove a technology stack from current profile
    Remove {
        /// Stack name to remove
        stack: String,
    },

    /// List all profiles
    Profiles,

    /// Profile management commands
    Profile {
        #[command(subcommand)]
        command: ProfileCommands,
    },

    /// Package management commands
    Pkg {
        #[command(subcommand)]
        command: PkgCommands,
    },

    /// OpenMesh xNode deployment and management
    Openmesh {
        #[command(subcommand)]
        command: Option<OpenMeshCommands>,
    },

    /// 🌐 xNode deployment and management (alias for 'openmesh xnode')
    Xnode {
        #[command(subcommand)]
        command: XnodeCommands,
    },

    /// 💾 Embedded key-value datastore
    Data {
        #[command(subcommand)]
        command: DataCommands,
    },

    /// 📸 Server snapshot and restore
    Server {
        #[command(subcommand)]
        command: ServerCommands,
    },

    /// 📤 Send capsule binary to remote server
    Send {
        /// Remote server (user@host or host)
        server: String,

        /// Remote installation path
        #[arg(short, long, default_value = "/usr/local/bin/capsule")]
        path: String,
    },
}

#[derive(Subcommand)]
enum ServerCommands {
    /// Create a server snapshot with Nix configuration
    Pack {
        /// Output directory for snapshot
        #[arg(default_value = "./capsule-snapshot")]
        output: std::path::PathBuf,
    },

    /// Restore server from snapshot
    Unpack {
        /// Snapshot directory to restore from
        snapshot: std::path::PathBuf,

        /// Dry run - show what would be done
        #[arg(long)]
        dry_run: bool,
    },

    /// Validate snapshot integrity with checksums
    Validate {
        /// Snapshot directory to validate
        snapshot: std::path::PathBuf,

        /// Verbose output showing all file checks
        #[arg(short, long)]
        verbose: bool,
    },
}

#[derive(Subcommand)]
enum DataCommands {
    /// Get a value by key
    Get {
        /// Key to retrieve
        key: String,
    },

    /// Set a key-value pair
    Set {
        /// Key to store
        key: String,
        /// Value to store (or use --file)
        value: Option<String>,
        /// Store contents of a file
        #[arg(short, long)]
        file: Option<std::path::PathBuf>,
    },

    /// Delete a key
    Delete {
        /// Key to delete
        key: String,
    },

    /// List all keys
    Keys,

    /// List all key-value pairs
    List,

    /// Get file and save to disk
    GetFile {
        /// Key to retrieve
        key: String,
        /// Output file path
        #[arg(short, long)]
        output: std::path::PathBuf,
    },

    /// Store a file
    SetFile {
        /// Key to store under
        key: String,
        /// Input file path
        file: std::path::PathBuf,
    },

    /// Show database statistics
    Stats,

    /// Export all data to directory
    Export {
        /// Output directory
        output: std::path::PathBuf,
    },

    /// Clear all data (WARNING: destructive!)
    Clear {
        /// Confirm deletion
        #[arg(long)]
        confirm: bool,
    },
}

#[derive(Subcommand)]
enum ProfileCommands {
    /// Create a new profile
    New {
        /// Profile name
        name: String,
    },

    /// Switch to a different profile
    Use {
        /// Profile name
        name: String,
    },

    /// Copy a profile
    Copy {
        /// Source profile name
        src: String,
        /// Destination profile name
        dst: String,
    },

    /// Delete a profile
    Delete {
        /// Profile name
        name: String,
    },
}

#[derive(Subcommand)]
enum PkgCommands {
    /// Add custom packages
    Add {
        /// Package names
        packages: Vec<String>,
    },

    /// Remove custom packages
    Remove {
        /// Package names
        packages: Vec<String>,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        None => show_overview()?,
        Some(Commands::Show) => show_config()?,
        Some(Commands::Stacks) => list_stacks()?,
        Some(Commands::Add { stack }) => add_stack(&stack)?,
        Some(Commands::Remove { stack }) => remove_stack(&stack)?,
        Some(Commands::Profiles) => list_profiles()?,
        Some(Commands::Profile { command }) => handle_profile_command(command)?,
        Some(Commands::Pkg { command }) => handle_pkg_command(command)?,
        Some(Commands::Openmesh { command }) => {
            if let Some(cmd) = command {
                handle_openmesh_command(cmd)?;
            } else {
                // Show beautiful overview when no subcommand provided
                handle_openmesh_command(OpenMeshCommands::Overview)?;
            }
        }
        Some(Commands::Xnode { command }) => {
            // Alias for openmesh xnode
            handle_xnode_command(command)?;
        }
        Some(Commands::Data { command }) => handle_data_command(command)?,
        Some(Commands::Server { command }) => handle_server_command(command)?,
        Some(Commands::Send { server, path }) => handle_send_command(&server, &path)?,
    }

    Ok(())
}

fn show_overview() -> Result<()> {
    print_logo();

    let active_name = get_active_config_name()?;
    println!(
        "  {} {}\n",
        "Active Profile:".white(),
        active_name.green().bold()
    );

    section_header("🚀 Quick Start");
    println!(
        "    {} {} {}",
        "▸".green().bold(),
        "capsule stacks".cyan().bold(),
        "          List available stacks".white()
    );
    println!(
        "    {} {} {} {}",
        "▸".green().bold(),
        "capsule add".cyan().bold(),
        "<stack>".cyan(),
        "         Add a technology stack".white()
    );
    println!(
        "    {} {} {}",
        "▸".green().bold(),
        "capsule show".cyan().bold(),
        "           View configuration".white()
    );
    println!(
        "    {} {} {}",
        "▸".green().bold(),
        "capsule setup".cyan().bold(),
        "           Install packages".white()
    );

    section_header("📁 Configuration Profiles");
    println!(
        "    {} {} {}",
        "○".cyan(),
        "capsule profiles".cyan().bold(),
        "        List all profiles".white()
    );
    println!(
        "    {} {} {} {}",
        "○".cyan(),
        "capsule profile new".cyan().bold(),
        "<name>".cyan(),
        "    Create new profile".white()
    );
    println!(
        "    {} {} {} {}",
        "○".cyan(),
        "capsule profile use".cyan().bold(),
        "<name>".cyan(),
        "    Switch profile".white()
    );

    section_header("🔧 Main Commands");
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "bootstrap".cyan().bold(),
        "          Install dependencies".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "config".cyan().bold(),
        "             Manage configuration".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "setup".cyan().bold(),
        "              Install configured packages".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "check".cyan().bold(),
        "              Dry run / preview changes".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "preview".cyan().bold(),
        "            Show generated configuration".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "list".cyan().bold(),
        "               List package status".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "plant".cyan().bold(),
        "              Deploy to remote server".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "docs".cyan().bold(),
        "               Interactive documentation".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "update".cyan().bold(),
        "             Update to latest version".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "backup".cyan().bold(),
        "             Backup package list".white()
    );
    println!(
        "    {} {} {}",
        "•".magenta().bold(),
        "restore".cyan().bold(),
        "            Restore from backup".white()
    );

    section_header("🌱 Sprouts (Quick Install)");
    println!(
        "    {} {} {}",
        "▸".green().bold(),
        "sprouts".cyan().bold(),
        "           List available sprouts".white()
    );
    println!(
        "    {} {} {} {}",
        "▸".green().bold(),
        "sprout".cyan().bold(),
        "<name>".cyan(),
        "      Install a sprout".white()
    );

    divider();
    println!();
    println!(
        "  {} Run {} for detailed command list",
        "💡 Tip:".cyan(),
        "capsule --help".cyan().bold()
    );
    println!();

    Ok(())
}

fn show_config() -> Result<()> {
    let active_name = get_active_config_name()?;
    let config = load_config(None)?;

    header("⚙  CONFIGURATION");

    println!(
        "  {} {}\n",
        "Active Profile:".white(),
        active_name.cyan().bold()
    );

    section_header("Technology Stacks");
    if !config.presets.is_empty() {
        for preset in &config.presets {
            if preset == "base" {
                preset_item(preset, "(core packages)", true);
            } else {
                // In a real implementation, we'd load preset data from files
                preset_item(preset, "", true);
            }
        }
    } else {
        println!("{}", "  No stacks configured".white());
    }

    if !config.custom_packages.is_empty() {
        section_header("Individual Packages");
        for pkg in &config.custom_packages {
            package_item(pkg);
        }
    }

    section_header("Settings");
    let editor_value = config.editor.as_deref().unwrap_or("vim");
    info_line("Editor", &editor_value.cyan().to_string());

    // Show config source
    if is_builtin_profile(&active_name) {
        info_line(
            "Source",
            &"Built-in profile (read-only)".yellow().to_string(),
        );
    } else {
        let config_path = get_config_file(None)?;
        info_line("Config File", &config_path.display().to_string().white());
    }
    println!();

    Ok(())
}

fn list_stacks() -> Result<()> {
    header("📦 TECHNOLOGY STACKS");

    section_header("Languages & Runtimes 🔧");
    println!("  {} {:14} {}", "○".cyan(), "python", "Python 3.x development".white());
    println!("  {} {:14} {}", "○".cyan(), "nodejs", "Node.js & npm".white());
    println!("  {} {:14} {}", "○".cyan(), "golang", "Go programming language".white());
    println!("  {} {:14} {}", "○".cyan(), "rust", "Rust programming language".white());

    section_header("Development Tools 🛠");
    println!("  {} {:14} {}", "○".cyan(), "devtools", "General dev utilities".white());
    println!("  {} {:14} {}", "○".cyan(), "cli-tools", "CLI productivity tools".white());
    println!("  {} {:14} {}", "○".cyan(), "github", "GitHub CLI & tools".white());

    section_header("Infrastructure 🏗");
    println!("  {} {:14} {}", "○".cyan(), "docker", "Docker & docker-compose".white());
    println!("  {} {:14} {}", "○".cyan(), "database", "PostgreSQL, MySQL, Redis".white());
    println!("  {} {:14} {}", "○".cyan(), "webserver", "Nginx, Apache".white());

    section_header("Security & Monitoring 🔒");
    println!("  {} {:14} {}", "○".cyan(), "security", "Security tools".white());
    println!("  {} {:14} {}", "○".cyan(), "monitoring", "System monitoring".white());

    section_header("AI/ML 🤖");
    println!("  {} {:14} {}", "○".cyan(), "machine-learning", "ML frameworks & tools".white());
    println!("  {} {:14} {}", "○".cyan(), "ollama", "Local LLM runtime".white());
    println!("  {} {:14} {}", "○".cyan(), "cuda", "NVIDIA CUDA support".white());

    divider();
    println!();
    println!(
        "  {} Use {} to add a stack",
        "💡 Tip:".cyan(),
        "capsule add <stack>".cyan().bold()
    );
    println!();

    Ok(())
}

fn add_stack(stack: &str) -> Result<()> {
    let active_name = get_active_config_name()?;

    if is_builtin_profile(&active_name) {
        error(&format!(
            "Cannot modify built-in profile '{}'. Create a new profile first.",
            active_name
        ));
        return Ok(());
    }

    add_preset(stack, None)?;
    success(&format!("Added stack '{}' to profile '{}'", stack, active_name));

    Ok(())
}

fn remove_stack(stack: &str) -> Result<()> {
    let active_name = get_active_config_name()?;

    if is_builtin_profile(&active_name) {
        error(&format!(
            "Cannot modify built-in profile '{}'. Create a new profile first.",
            active_name
        ));
        return Ok(());
    }

    remove_preset(stack, None)?;
    success(&format!(
        "Removed stack '{}' from profile '{}'",
        stack, active_name
    ));

    Ok(())
}

fn list_profiles() -> Result<()> {
    header("📁 CONFIGURATION PROFILES");

    let active = get_active_config_name()?;

    section_header("Built-in Profiles");
    for name in list_builtin_profiles() {
        let is_active = name == active;
        if let Some(profile) = get_builtin_profile(&name) {
            let desc = profile.description.unwrap_or_default();
            preset_item(&name, &desc, is_active);
        }
    }

    let user_configs = list_all_configs()?;
    if !user_configs.is_empty() {
        section_header("User Profiles");
        for name in user_configs {
            let is_active = name == active;
            preset_item(&name, "", is_active);
        }
    }

    divider();
    println!();
    println!(
        "  {} Active profile: {}",
        "▸".cyan(),
        active.green().bold()
    );
    println!(
        "  {} Use {} to switch profiles",
        "💡 Tip:".cyan(),
        "capsule profile use <name>".cyan().bold()
    );
    println!();

    Ok(())
}

fn handle_profile_command(command: ProfileCommands) -> Result<()> {
    match command {
        ProfileCommands::New { name } => {
            ensure_config(Some(&name))?;
            success(&format!("Created new profile '{}'", name));
        }
        ProfileCommands::Use { name } => {
            // Check if profile exists (either built-in or user)
            if !is_builtin_profile(&name) {
                let user_configs = list_all_configs()?;
                if !user_configs.contains(&name) {
                    error(&format!("Profile '{}' not found", name));
                    return Ok(());
                }
            }

            set_active_config_name(&name)?;
            success(&format!("Switched to profile '{}'", name));
        }
        ProfileCommands::Copy { src, dst } => {
            copy_profile(&src, &dst)?;
            success(&format!("Copied profile '{}' to '{}'", src, dst));
        }
        ProfileCommands::Delete { name } => {
            delete_profile(&name)?;
            success(&format!("Deleted profile '{}'", name));
        }
    }

    Ok(())
}

fn handle_pkg_command(command: PkgCommands) -> Result<()> {
    let active_name = get_active_config_name()?;

    if is_builtin_profile(&active_name) {
        error(&format!(
            "Cannot modify built-in profile '{}'. Create a new profile first.",
            active_name
        ));
        return Ok(());
    }

    match command {
        PkgCommands::Add { packages } => {
            add_packages(&packages, None)?;
            success(&format!(
                "Added {} package(s) to profile '{}'",
                packages.len(),
                active_name
            ));
        }
        PkgCommands::Remove { packages } => {
            remove_packages(&packages, None)?;
            success(&format!(
                "Removed {} package(s) from profile '{}'",
                packages.len(),
                active_name
            ));
        }
    }

    Ok(())
}

fn handle_data_command(command: DataCommands) -> Result<()> {
    let ds = DataStore::new()?;

    match command {
        DataCommands::Get { key } => {
            if let Some(value) = ds.get(&key)? {
                // Try to print as UTF-8 string, otherwise hex
                match String::from_utf8(value.clone()) {
                    Ok(s) => println!("{}", s),
                    Err(_) => {
                        println!("{}", "Binary data (hex):".yellow());
                        for byte in value {
                            print!("{:02x}", byte);
                        }
                        println!();
                    }
                }
            } else {
                error(&format!("Key '{}' not found", key));
            }
        }

        DataCommands::Set { key, value, file } => {
            if let Some(file_path) = file {
                ds.set_file(&key, &file_path)?;
                let metadata = std::fs::metadata(&file_path)?;
                success(&format!("Stored file '{}' ({} bytes) as key '{}'", 
                    file_path.display(), metadata.len(), key));
            } else if let Some(val) = value {
                ds.set(&key, val.as_bytes())?;
                success(&format!("Stored key '{}' ({} bytes)", key, val.len()));
            } else {
                error("Must provide either value or --file");
            }
        }

        DataCommands::Delete { key } => {
            if ds.delete(&key)? {
                success(&format!("Deleted key '{}'", key));
            } else {
                error(&format!("Key '{}' not found", key));
            }
        }

        DataCommands::Keys => {
            let keys = ds.list_keys()?;
            if keys.is_empty() {
                println!("{}", "No keys stored".yellow());
            } else {
                header("💾 STORED KEYS");
                for key in keys {
                    println!("  {} {}", "▸".cyan(), key.white());
                }
                println!();
            }
        }

        DataCommands::List => {
            let items = ds.list_all()?;
            if items.is_empty() {
                println!("{}", "No data stored".yellow());
            } else {
                header("💾 KEY-VALUE STORE");
                
                use prettytable::{Table, Row, Cell, format};
                let mut table = Table::new();
                table.set_format(*format::consts::FORMAT_NO_LINESEP_WITH_TITLE);

                table.add_row(Row::new(vec![
                    Cell::new("Key").style_spec("Fb"),
                    Cell::new("Size").style_spec("Fb"),
                    Cell::new("Compressed").style_spec("Fb"),
                ]));

                for (key, size, compressed) in items {
                    let size_str = if size < 1024 {
                        format!("{} B", size)
                    } else if size < 1024 * 1024 {
                        format!("{:.1} KB", size as f64 / 1024.0)
                    } else {
                        format!("{:.1} MB", size as f64 / (1024.0 * 1024.0))
                    };

                    table.add_row(Row::new(vec![
                        Cell::new(&key).style_spec("Fc"),
                        Cell::new(&size_str).style_spec("Fg"),
                        Cell::new(if compressed { "✓" } else { "-" }),
                    ]));
                }

                table.printstd();
                println!();

                let (count, disk_size) = ds.stats()?;
                println!("{} {} keys • {} on disk", 
                    "▸".green().bold(), 
                    count,
                    if disk_size < 1024 {
                        format!("{} B", disk_size)
                    } else if disk_size < 1024 * 1024 {
                        format!("{:.1} KB", disk_size as f64 / 1024.0)
                    } else {
                        format!("{:.1} MB", disk_size as f64 / (1024.0 * 1024.0))
                    }
                );
                println!();
            }
        }

        DataCommands::GetFile { key, output } => {
            if ds.get_file(&key, &output)? {
                success(&format!("Exported key '{}' to '{}'", key, output.display()));
            } else {
                error(&format!("Key '{}' not found", key));
            }
        }

        DataCommands::SetFile { key, file } => {
            ds.set_file(&key, &file)?;
            let metadata = std::fs::metadata(&file)?;
            success(&format!("Stored file '{}' ({} bytes) as key '{}'", 
                file.display(), metadata.len(), key));
        }

        DataCommands::Stats => {
            let (count, disk_size) = ds.stats()?;
            header("💾 DATASTORE STATISTICS");
            
            println!("  {} {}", "Total keys:".white().bold(), count.to_string().cyan());
            println!("  {} {}", "Disk usage:".white().bold(), 
                if disk_size < 1024 {
                    format!("{} B", disk_size).cyan().to_string()
                } else if disk_size < 1024 * 1024 {
                    format!("{:.2} KB", disk_size as f64 / 1024.0).cyan().to_string()
                } else {
                    format!("{:.2} MB", disk_size as f64 / (1024.0 * 1024.0)).cyan().to_string()
                }
            );
            
            let data_dir = home::home_dir()
                .ok_or_else(|| anyhow::anyhow!("Could not find home directory"))?
                .join(".capsule").join("data");
            println!("  {} {}", "Location:".white().bold(), data_dir.display().to_string().cyan());
            println!();
        }

        DataCommands::Export { output } => {
            std::fs::create_dir_all(&output)?;
            let count = ds.export(&output)?;
            success(&format!("Exported {} keys to '{}'", count, output.display()));
        }

        DataCommands::Clear { confirm } => {
            if !confirm {
                error("This will delete ALL data. Use --confirm to proceed.");
                return Ok(());
            }
            
            let count = ds.clear()?;
            success(&format!("Cleared {} keys from datastore", count));
        }
    }

    Ok(())
}

fn handle_server_command(command: ServerCommands) -> Result<()> {
    match command {
        ServerCommands::Pack { output } => {
            server::pack(&output)?;
        }
        ServerCommands::Unpack { snapshot, dry_run } => {
            server::unpack(&snapshot, dry_run)?;
        }
        ServerCommands::Validate { snapshot, verbose } => {
            server::validate(&snapshot, verbose)?;
        }
    }

    Ok(())
}

fn handle_send_command(server: &str, remote_path: &str) -> Result<()> {
    use anyhow::Context;
    use std::process::Command;

    println!("{}", "📤 Sending capsule binary to remote server...".cyan().bold());
    println!();

    // Get the current binary path
    let binary_path = std::env::current_exe()
        .context("Failed to locate capsule binary")?;

    println!("{} Binary location: {}",
        "▸".green().bold(),
        binary_path.display().to_string().cyan());

    // Check binary size
    let metadata = std::fs::metadata(&binary_path)
        .context("Failed to read binary metadata")?;
    let size_mb = metadata.len() as f64 / (1024.0 * 1024.0);

    println!("{} Binary size: {:.2} MB",
        "▸".green().bold(),
        size_mb.to_string().cyan());
    println!();

    // Use SCP to transfer the binary
    println!("{} Transferring to {}...",
        "▸".green().bold(),
        server.cyan());

    let temp_path = format!("/tmp/capsule-{}", std::process::id());

    let scp_status = Command::new("scp")
        .arg(&binary_path)
        .arg(format!("{}:{}", server, temp_path))
        .status()
        .context("Failed to execute scp")?;

    if !scp_status.success() {
        anyhow::bail!("SCP transfer failed");
    }

    println!("{} Transfer complete", "  ✓".green());
    println!();

    // Install to remote path
    println!("{} Installing to {}...",
        "▸".green().bold(),
        remote_path.cyan());

    let install_cmd = format!(
        "sudo mv {} {} && sudo chmod +x {}",
        temp_path, remote_path, remote_path
    );

    let ssh_status = Command::new("ssh")
        .arg(server)
        .arg(&install_cmd)
        .status()
        .context("Failed to execute ssh")?;

    if !ssh_status.success() {
        anyhow::bail!("Remote installation failed");
    }

    println!("{} Installation complete", "  ✓".green());
    println!();

    // Verify installation
    println!("{} Verifying installation...", "▸".green().bold());

    let verify_cmd = format!("{} --version", remote_path);
    let verify_status = Command::new("ssh")
        .arg(server)
        .arg(&verify_cmd)
        .status()
        .context("Failed to verify installation")?;

    if !verify_status.success() {
        println!("{} {} (binary installed but may not be in PATH)",
            "  !".yellow(),
            "Warning: verification failed".yellow());
    } else {
        println!("{} Capsule is ready on remote server", "  ✓".green());
    }
    println!();

    println!("{} Capsule successfully deployed to {}",
        "✅".green(),
        server.green().bold());
    println!();
    println!("{} Connect: {} {}",
        "💡 Tip:".yellow(),
        "ssh".cyan().bold(),
        server.cyan());
    println!("{} Run: {} {}",
        "💡 Tip:".yellow(),
        "ssh".cyan().bold(),
        format!("{} 'capsule --help'", server).cyan());
    println!();

    Ok(())
}
