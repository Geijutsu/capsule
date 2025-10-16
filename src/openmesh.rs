use anyhow::Result;
use colored::*;
use prettytable::{Table, Row, Cell, format};
use std::collections::HashMap;

use crate::providers::{ProviderManager, DeployConfig};

pub fn handle_openmesh_command(command: OpenMeshCommands) -> Result<()> {
    match command {
        OpenMeshCommands::Providers => list_providers()?,
        OpenMeshCommands::Provider { command } => handle_provider_command(command)?,
        OpenMeshCommands::Templates { gpu } => list_templates(gpu)?,
        OpenMeshCommands::Deploy {
            provider,
            template,
            name,
            region,
            budget,
            min_cpu,
            min_memory,
        } => deploy_instance(provider, template, name, region, budget, min_cpu, min_memory)?,
        OpenMeshCommands::Inventory { provider, status } => {
            println!("{} Inventory feature (filtered by provider: {:?}, status: {:?})", "→".cyan(), provider, status);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        OpenMeshCommands::Xnodes { status, provider } => {
            println!("{} xNodes list (filtered by status: {:?}, provider: {:?})", "→".cyan(), status, provider);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        OpenMeshCommands::CostReport => {
            println!("{} Cost report", "→".cyan());
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        OpenMeshCommands::Stats => {
            println!("{} Inventory statistics", "→".cyan());
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        OpenMeshCommands::Export { filename } => {
            println!("{} Export to {}", "→".cyan(), filename);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        OpenMeshCommands::Import { filename } => {
            println!("{} Import from {}", "→".cyan(), filename);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        OpenMeshCommands::History { xnode_id, provider, limit } => {
            println!("{} Deployment history (xnode_id: {:?}, provider: {:?}, limit: {:?})", "→".cyan(), xnode_id, provider, limit);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
        OpenMeshCommands::Cleanup { days } => {
            println!("{} Cleanup deployment history older than {} days", "→".cyan(), days);
            println!("{}", "This feature is not yet implemented.".yellow());
        },
    }
    Ok(())
}

#[derive(clap::Subcommand)]
pub enum OpenMeshCommands {
    /// List all available providers
    Providers,

    /// Configure a provider
    Provider {
        #[command(subcommand)]
        command: ProviderSubcommands,
    },

    /// List and compare templates across providers
    Templates {
        /// Show only GPU templates
        #[arg(long)]
        gpu: bool,
    },

    /// Deploy an instance
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

    /// View xNode inventory
    Inventory {
        /// Filter by provider
        #[arg(long)]
        provider: Option<String>,

        /// Filter by status
        #[arg(long)]
        status: Option<String>,
    },

    /// List all xNodes
    Xnodes {
        /// Filter by status
        #[arg(long)]
        status: Option<String>,

        /// Filter by provider
        #[arg(long)]
        provider: Option<String>,
    },

    /// Generate cost report
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
    println!("\n{}", "OPENMESH PROVIDERS".cyan().bold());
    println!("{}\n", "=".repeat(60).cyan());

    let manager = ProviderManager::new(None)?;
    let providers = manager.list_providers();

    let mut table = Table::new();
    table.set_format(*format::consts::FORMAT_NO_LINESEP_WITH_TITLE);

    table.add_row(Row::new(vec![
        Cell::new("Provider").style_spec("Fb"),
        Cell::new("Templates").style_spec("Fb"),
        Cell::new("Regions").style_spec("Fb"),
        Cell::new("Price Range").style_spec("Fb"),
        Cell::new("GPU").style_spec("Fb"),
    ]));

    for provider_name in providers {
        if let Some(provider) = manager.get_provider(&provider_name) {
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

            let has_gpu = templates.iter().any(|t| t.gpu.is_some());

            table.add_row(Row::new(vec![
                Cell::new(&provider_name).style_spec("Fc"),
                Cell::new(&templates.len().to_string()),
                Cell::new(&regions.len().to_string()),
                Cell::new(&format!("${:.3} - ${:.2}/hr", min_price, max_price)),
                Cell::new(if has_gpu { "✓" } else { "-" }),
            ]));
        }
    }

    table.printstd();
    println!("\n{}", format!("Use {} to configure credentials", "capsule openmesh provider configure <name> --api-key <key>".cyan()));
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

    println!("\n{}", if gpu_only { "GPU TEMPLATES" } else { "ALL TEMPLATES" }.cyan().bold());
    println!("{}\n", "=".repeat(100).cyan());

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
    println!("\n{} templates found\n", templates.len());

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

    println!("\n{}", "DEPLOYING INSTANCE".cyan().bold());
    println!("{}", "=".repeat(60).cyan());
    println!("  Provider:  {}", selected_provider.cyan());
    println!("  Template:  {}", selected_template.cyan());
    println!("  Name:      {}", config.name.cyan());
    println!("  Region:    {}", config.region.cyan());
    println!();

    let instance = manager.deploy_to_provider(&selected_provider, &selected_template, &config)?;

    println!("{} Instance deployed successfully!", "✓".green());
    println!("  ID:        {}", instance.id.cyan());
    println!("  Status:    {}", instance.status.yellow());
    println!("  Cost:      ${:.3}/hr (${:.2}/mo)",
        instance.cost_hourly,
        instance.cost_hourly * 730.0
    );
    println!();

    Ok(())
}
