use anyhow::Result;
use colored::*;
use prettytable::{Table, Row, Cell, format};
use std::collections::HashMap;

use crate::providers::{ProviderManager, DeployConfig};

pub fn handle_openmesh_command(command: OpenMeshCommands) -> Result<()> {
    match command {
        OpenMeshCommands::Overview => show_openmesh_overview()?,
        OpenMeshCommands::Providers => list_providers()?,
        OpenMeshCommands::Xnode { command } => handle_xnode_command(command)?,
        OpenMeshCommands::Provider { command } => handle_provider_command(command)?,
    }
    Ok(())
}

fn show_openmesh_overview() -> Result<()> {
    println!();
    println!("{}", "╔═══════════════════════════════════════════════════════════════════════╗".cyan());
    println!("{}", "║                                                                       ║".cyan());
    println!("{}              {}  OPENMESH XNODE DEPLOYMENT PLATFORM  {}              {}", "║".cyan(), "🌐".cyan(), "🌐".cyan(), "║".cyan());
    println!("{}", "║                                                                       ║".cyan());
    println!("{}", "║   Deploy and manage infrastructure across 8 cloud providers with     ║".cyan());
    println!("{}", "║   a unified, beautiful CLI interface.                                ║".cyan());
    println!("{}", "║                                                                       ║".cyan());
    println!("{}", "╚═══════════════════════════════════════════════════════════════════════╝".cyan());
    println!();

    println!("{}", "  📋 QUICK START".green().bold());
    println!();
    println!("    {}  {}  {}", "1.".cyan().bold(), "capsule openmesh providers".white().bold(), "→ Browse 8 cloud providers".white());
    println!("    {}  {}  {}", "2.".cyan().bold(), "capsule openmesh xnode templates".white().bold(), "→ View 36 instance templates".white());
    println!("    {}  {}  {}", "3.".cyan().bold(), "capsule openmesh xnode deploy".white().bold(), "→ Launch your xNode".white());
    println!();

    println!("{}", "  🏗️  MAIN COMMANDS".green().bold());
    println!();
    println!("    {}  {}  {}", "▸".cyan(), "providers".white().bold(), "List all cloud providers with pricing".white());
    println!("    {}  {}  {}", "▸".cyan(), "xnode".white().bold(), "Complete xNode lifecycle management".white());
    println!("    {}  {}  {}", "▸".cyan(), "provider".white().bold(), "Configure API credentials".white());
    println!();

    println!("{}", "  🚀 DEPLOYMENT OPTIONS".green().bold());
    println!();

    use prettytable::{Table, Row, Cell, format};
    let mut table = Table::new();
    table.set_format(*format::consts::FORMAT_CLEAN);

    table.add_row(Row::new(vec![
        Cell::new("Type").style_spec("Fc"),
        Cell::new("Count").style_spec("Fg"),
        Cell::new("Examples").style_spec("Fw"),
    ]));

    table.add_row(Row::new(vec![
        Cell::new("🍒 Providers"),
        Cell::new("8"),
        Cell::new("Cherry, AWS, DigitalOcean, Hivelocity, Vultr..."),
    ]));

    table.add_row(Row::new(vec![
        Cell::new("📦 Templates"),
        Cell::new("36"),
        Cell::new("Budget to Enterprise GPU ($0.08-$3.30/hr)"),
    ]));

    table.add_row(Row::new(vec![
        Cell::new("🌍 Regions"),
        Cell::new("50+"),
        Cell::new("Global coverage (US, EU, APAC)"),
    ]));

    table.add_row(Row::new(vec![
        Cell::new("🎮 GPU Options"),
        Cell::new("7"),
        Cell::new("RTX A4000/A5000, Tesla V100, H100"),
    ]));

    table.printstd();
    println!();

    println!("{}", "  💡 PRO TIPS".yellow().bold());
    println!();
    println!("    {}  Use {} for smart instance selection", "•".yellow(), "capsule openmesh xnode deploy --budget 0.5".cyan());
    println!("    {}  Filter GPU templates with {}", "•".yellow(), "capsule openmesh xnode templates --gpu".cyan());
    println!("    {}  Export inventory with {}", "•".yellow(), "capsule openmesh xnode export".cyan());
    println!();

    println!("{}", "  🔗 DETAILED HELP".white().bold());
    println!();
    println!("    {}  {}", "→".cyan(), "capsule openmesh xnode --help       Full xNode commands".white());
    println!("    {}  {}", "→".cyan(), "capsule openmesh provider --help    Provider configuration".white());
    println!();

    Ok(())
}

fn handle_xnode_command(command: XnodeCommands) -> Result<()> {
    match command {
        XnodeCommands::Providers => list_providers()?,
        XnodeCommands::Templates { gpu } => list_templates(gpu)?,
        XnodeCommands::Deploy {
            provider,
            template,
            name,
            region,
            budget,
            min_cpu,
            min_memory,
        } => deploy_instance(provider, template, name, region, budget, min_cpu, min_memory)?,
        XnodeCommands::List { status, provider } => {
            println!("{} xNodes list (filtered by status: {:?}, provider: {:?})", "→".cyan(), status, provider);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        XnodeCommands::Inventory { provider, status } => {
            println!("{} Inventory feature (filtered by provider: {:?}, status: {:?})", "→".cyan(), provider, status);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        XnodeCommands::CostReport => {
            println!("{} Cost report", "→".cyan());
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        XnodeCommands::Stats => {
            println!("{} Inventory statistics", "→".cyan());
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        XnodeCommands::Export { filename } => {
            println!("{} Export to {}", "→".cyan(), filename);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        XnodeCommands::Import { filename } => {
            println!("{} Import from {}", "→".cyan(), filename);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        XnodeCommands::History { xnode_id, provider, limit } => {
            println!("{} Deployment history (xnode_id: {:?}, provider: {:?}, limit: {:?})", "→".cyan(), xnode_id, provider, limit);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        XnodeCommands::Cleanup { days } => {
            println!("{} Cleanup deployment history older than {} days", "→".cyan(), days);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
    }
    Ok(())
}

#[derive(clap::Subcommand)]
pub enum OpenMeshCommands {
    /// Show OpenMesh overview and quick start
    #[command(hide = true)]
    Overview,

    /// 🍒 List all available cloud providers
    Providers,

    /// 🌐 xNode deployment and management
    #[command(after_help = "\n\
╔═══════════════════════════════════════════════════════════════╗\n\
║              🌐  OPENMESH XNODE MANAGEMENT  🌐                ║\n\
╚═══════════════════════════════════════════════════════════════╝\n\
\n\
  Deploy and manage OpenMesh xNode infrastructure across multiple\n\
  cloud providers with a unified interface.\n\
\n\
  Quick Start:\n\
    • capsule openmesh xnode providers    → List all cloud providers\n\
    • capsule openmesh xnode templates    → Browse instance templates\n\
    • capsule openmesh xnode deploy       → Deploy a new xNode\n\
    • capsule openmesh xnode list         → View all deployed xNodes\n\
\n\
  Features:\n\
    ✓ 8 cloud providers (Cherry Servers, AWS, DigitalOcean, etc.)\n\
    ✓ 31+ instance templates (budget to enterprise GPU)\n\
    ✓ 50+ datacenter regions worldwide\n\
    ✓ Smart deployment with auto-selection\n\
    ✓ Cost tracking and analytics\n\
")]
    Xnode {
        #[command(subcommand)]
        command: XnodeCommands,
    },

    /// 🔧 Provider configuration
    Provider {
        #[command(subcommand)]
        command: ProviderSubcommands,
    },
}

#[derive(clap::Subcommand)]
#[command(after_help = "\n\
╔═══════════════════════════════════════════════════════════════╗\n\
║                    🌐  XNODE COMMANDS  🌐                     ║\n\
╚═══════════════════════════════════════════════════════════════╝\n\
\n\
  📋 Discovery & Planning:\n\
    providers       List cloud providers and capabilities\n\
    templates       Browse instance templates and pricing\n\
\n\
  🚀 Deployment:\n\
    deploy          Launch new xNode instances\n\
                    Example: --provider hivelocity --template small\n\
\n\
  📊 Management:\n\
    list (ls)       View all deployed xNodes\n\
    inventory       Detailed xNode inventory\n\
    stats           Show deployment statistics\n\
\n\
  💰 Cost Analysis:\n\
    cost-report     Generate cost breakdown\n\
    export          Export data to CSV\n\
    import          Import inventory from CSV\n\
\n\
  🔍 History:\n\
    history         View deployment history\n\
    cleanup         Remove old history records\n\
\n\
  💡 Tips:\n\
    • Use --help on any command for detailed options\n\
    • Smart deployment: omit provider/template for auto-selection\n\
    • Filter commands support --provider and --status flags\n\
")]
pub enum XnodeCommands {
    /// List all available cloud providers
    Providers,

    /// List and compare instance templates
    Templates {
        /// Show only GPU templates
        #[arg(long)]
        gpu: bool,
    },

    /// Deploy a new xNode instance
    Deploy {
        /// Provider name (e.g., hivelocity, digitalocean)
        #[arg(short, long)]
        provider: Option<String>,

        /// Template ID
        #[arg(short, long)]
        template: Option<String>,

        /// Instance name
        #[arg(short, long)]
        name: Option<String>,

        /// Region
        #[arg(short, long)]
        region: Option<String>,

        /// Maximum hourly budget
        #[arg(long)]
        budget: Option<f64>,

        /// Minimum CPU cores
        #[arg(long)]
        min_cpu: Option<u32>,

        /// Minimum memory (GB)
        #[arg(long)]
        min_memory: Option<u32>,
    },

    /// List all deployed xNodes
    #[command(alias = "ls")]
    List {
        /// Filter by status
        #[arg(long)]
        status: Option<String>,

        /// Filter by provider
        #[arg(long)]
        provider: Option<String>,
    },

    /// View detailed xNode inventory
    Inventory {
        /// Filter by provider
        #[arg(long)]
        provider: Option<String>,

        /// Filter by status
        #[arg(long)]
        status: Option<String>,
    },

    /// Generate cost analysis report
    #[command(name = "cost-report")]
    CostReport,

    /// Show inventory statistics
    Stats,

    /// Export inventory to CSV
    Export {
        /// Output filename
        #[arg(default_value = "inventory.csv")]
        filename: String,
    },

    /// Import inventory from CSV
    Import {
        /// Input filename
        filename: String,
    },

    /// Show deployment history
    History {
        /// Filter by xNode ID
        #[arg(long)]
        xnode_id: Option<String>,

        /// Filter by provider
        #[arg(long)]
        provider: Option<String>,

        /// Limit number of records
        #[arg(long)]
        limit: Option<usize>,
    },

    /// Cleanup old deployment history
    Cleanup {
        /// Number of days to retain
        #[arg(default_value = "90")]
        days: u64,
    },
}

#[derive(clap::Subcommand)]
pub enum ProviderSubcommands {
    /// Configure provider credentials
    Configure {
        /// Provider name
        name: String,
        /// API key
        #[arg(short, long)]
        api_key: String,
    },
}

fn list_providers() -> Result<()> {
    // ASCII art header
    println!();
    println!("{}", "╔═══════════════════════════════════════════════════════════════╗".cyan());
    println!("{}", "║           🌐  OPENMESH CLOUD PROVIDERS  🌐                   ║".cyan().bold());
    println!("{}", "╚═══════════════════════════════════════════════════════════════╝".cyan());
    println!();

    let manager = ProviderManager::new(None)?;
    let providers = manager.list_providers();

    let mut table = Table::new();
    table.set_format(*format::consts::FORMAT_NO_LINESEP_WITH_TITLE);

    table.add_row(Row::new(vec![
        Cell::new("Provider").style_spec("Fb"),
        Cell::new("Type").style_spec("Fb"),
        Cell::new("CPU Range").style_spec("Fb"),
        Cell::new("Memory").style_spec("Fb"),
        Cell::new("Regions").style_spec("Fb"),
        Cell::new("Price/hr").style_spec("Fb"),
        Cell::new("GPU").style_spec("Fb"),
    ]));

    for provider_name in &providers {
        if let Some(provider) = manager.get_provider(provider_name) {
            let templates = provider.templates();
            let regions = provider.regions();

            let min_price = templates.iter()
                .map(|t| t.price_hourly)
                .min_by(|a, b| a.partial_cmp(b).unwrap())
                .unwrap_or(0.0);

            let max_price = templates.iter()
                .map(|t| t.price_hourly)
                .max_by(|a, b| a.partial_cmp(b).unwrap())
                .unwrap_or(0.0);

            let min_cpu = templates.iter().map(|t| t.cpu).min().unwrap_or(0);
            let max_cpu = templates.iter().map(|t| t.cpu).max().unwrap_or(0);

            let min_mem = templates.iter().map(|t| t.memory_gb).min().unwrap_or(0);
            let max_mem = templates.iter().map(|t| t.memory_gb).max().unwrap_or(0);

            let has_gpu = templates.iter().any(|t| t.gpu.is_some());
            let gpu_count = templates.iter().filter(|t| t.gpu.is_some()).count();

            // Determine instance type
            let has_bare_metal = templates.iter().any(|t| t.features.contains(&"bare-metal".to_string()));
            let has_cloud = templates.iter().any(|t| !t.features.contains(&"bare-metal".to_string()));
            let instance_type = if has_bare_metal && has_cloud {
                "Mixed"
            } else if has_bare_metal {
                "Bare Metal"
            } else {
                "Cloud"
            };

            // Cherry Servers gets just the emoji, no special colors
            let display_name = if provider_name == "cherry" {
                format!("🍒 {}", provider_name)
            } else {
                provider_name.clone()
            };

            table.add_row(Row::new(vec![
                Cell::new(&display_name).style_spec("Fc"),
                Cell::new(instance_type),
                Cell::new(&format!("{}-{} cores", min_cpu, max_cpu)),
                Cell::new(&format!("{}-{}GB", min_mem, max_mem)),
                Cell::new(&regions.len().to_string()),
                Cell::new(&format!("${:.3}-${:.2}", min_price, max_price)).style_spec("Fg"),
                Cell::new(&if has_gpu { format!("{} ✓", gpu_count) } else { "-".to_string() }),
            ]));
        }
    }

    table.printstd();

    println!();
    println!("{}", "─────────────────────────────────────────────────────────────────".cyan());
    println!("{} {} providers • {} total templates • {} with GPU",
        "▸".green().bold(),
        providers.len(),
        manager.get_all_templates().len(),
        manager.get_gpu_templates().len()
    );
    println!("{} Use {} to view detailed templates", "💡".cyan(), "capsule openmesh xnode templates".cyan().bold());
    println!("{} Configure credentials: {}", "🔧".cyan(), "capsule openmesh provider configure <name> --api-key <key>".cyan().bold());
    println!();

    Ok(())
}

fn handle_provider_command(command: ProviderSubcommands) -> Result<()> {
    match command {
        ProviderSubcommands::Configure { name, api_key } => {
            let mut manager = ProviderManager::new(None)?;
            manager.configure_provider(name.clone(), api_key)?;
            println!("{} Configured provider: {}", "✓".green(), name.cyan());
        }
    }
    Ok(())
}

fn list_templates(gpu_only: bool) -> Result<()> {
    let manager = ProviderManager::new(None)?;
    let templates = if gpu_only {
        manager.get_gpu_templates()
    } else {
        manager.get_all_templates()
    };

    // ASCII art header
    println!();
    if gpu_only {
        println!("{}", "╔═══════════════════════════════════════════════════════════════╗".cyan());
        println!("{}", "║              🎮  GPU INSTANCE TEMPLATES  🎮                   ║".cyan().bold());
        println!("{}", "╚═══════════════════════════════════════════════════════════════╝".cyan());
    } else {
        println!("{}", "╔═══════════════════════════════════════════════════════════════╗".cyan());
        println!("{}", "║             📦  XNODE INSTANCE TEMPLATES  📦                  ║".cyan().bold());
        println!("{}", "╚═══════════════════════════════════════════════════════════════╝".cyan());
    }
    println!();

    let mut table = Table::new();
    table.set_format(*format::consts::FORMAT_NO_LINESEP_WITH_TITLE);

    table.add_row(Row::new(vec![
        Cell::new("Provider").style_spec("Fb"),
        Cell::new("Template").style_spec("Fb"),
        Cell::new("CPU").style_spec("Fb"),
        Cell::new("Memory").style_spec("Fb"),
        Cell::new("Storage").style_spec("Fb"),
        Cell::new("GPU").style_spec("Fb"),
        Cell::new("Price/hr").style_spec("Fb"),
        Cell::new("Price/mo").style_spec("Fb"),
    ]));

    for template in &templates {
        table.add_row(Row::new(vec![
            Cell::new(&template.provider).style_spec("Fc"),
            Cell::new(&template.name),
            Cell::new(&format!("{} cores", template.cpu)),
            Cell::new(&format!("{} GB", template.memory_gb)),
            Cell::new(&format!("{} GB", template.storage_gb)),
            Cell::new(&template.gpu.as_deref().unwrap_or("-")),
            Cell::new(&format!("${:.3}", template.price_hourly)).style_spec("Fg"),
            Cell::new(&format!("${:.2}", template.price_monthly)).style_spec("Fy"),
        ]));
    }

    table.printstd();

    println!();
    println!("{}", "─────────────────────────────────────────────────────────────────".cyan());
    println!("{} {} templates available", "▸".green().bold(), templates.len());
    println!("{} Deploy with: {}", "🚀".cyan(), "capsule openmesh xnode deploy --provider <name> --template <id>".cyan().bold());
    if !gpu_only {
        println!("{} GPU only: {}", "💡".cyan(), "capsule openmesh xnode templates --gpu".cyan().bold());
    }
    println!();

    Ok(())
}

fn deploy_instance(
    provider: Option<String>,
    template: Option<String>,
    name: Option<String>,
    region: Option<String>,
    budget: Option<f64>,
    min_cpu: Option<u32>,
    min_memory: Option<u32>,
) -> Result<()> {
    let manager = ProviderManager::new(None)?;

    // Smart deployment: find best option based on constraints
    let (selected_provider, selected_template) = if provider.is_some() && template.is_some() {
        (provider.unwrap(), template.unwrap())
    } else {
        // Find cheapest option matching requirements
        let matching = manager.compare_templates(
            min_cpu.unwrap_or(1),
            min_memory.unwrap_or(1),
            budget.unwrap_or(f64::MAX),
        );

        if matching.is_empty() {
            anyhow::bail!("No templates found matching your requirements");
        }

        let best = &matching[0];
        println!("{} Auto-selected: {} - {} (${:.3}/hr)",
            "→".cyan(),
            best.provider.cyan(),
            best.name.cyan(),
            best.price_hourly
        );

        (best.provider.clone(), best.id.clone())
    };

    let instance_name = name.unwrap_or_else(|| "xnode-instance".to_string());

    // Get default region for provider
    let selected_region = if let Some(r) = region {
        r
    } else {
        let provider_obj = manager.get_provider(&selected_provider)
            .ok_or_else(|| anyhow::anyhow!("Provider not found"))?;
        provider_obj.regions()[0].clone()
    };

    let config = DeployConfig {
        name: instance_name.clone(),
        region: selected_region,
        os: Some("ubuntu-20.04".to_string()),
        ssh_keys: None,
        extra: HashMap::new(),
    };

    // ASCII art header
    println!();
    println!("{}", "╔═══════════════════════════════════════════════════════════════╗".cyan());
    println!("{}", "║              🚀  DEPLOYING XNODE INSTANCE  🚀                 ║".cyan().bold());
    println!("{}", "╚═══════════════════════════════════════════════════════════════╝".cyan());
    println!();
    println!("  {} {}", "Provider:".white().bold(), selected_provider.cyan());
    println!("  {} {}", "Template:".white().bold(), selected_template.cyan());
    println!("  {} {}", "Name:".white().bold(), config.name.cyan());
    println!("  {} {}", "Region:".white().bold(), config.region.cyan());
    println!();
    println!("{} Provisioning instance...", "▸".green().bold());

    let instance = manager.deploy_to_provider(&selected_provider, &selected_template, &config)?;

    println!();
    println!("{}", "─────────────────────────────────────────────────────────────────".green());
    println!("{} Instance deployed successfully!", "✓".green().bold());
    println!();
    println!("  {} {}", "Instance ID:".white().bold(), instance.id.cyan());
    println!("  {} {}", "Status:".white().bold(), instance.status.yellow());
    println!("  {} ${:.3}/hr (${:.2}/mo)",
        "Cost:".white().bold(),
        instance.cost_hourly,
        instance.cost_hourly * 730.0
    );
    println!();
    println!("{} Use {} to view all instances", "💡".cyan(), "capsule openmesh xnode list".cyan().bold());
    println!();

    Ok(())
}
