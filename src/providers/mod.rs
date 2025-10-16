use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

pub mod cherry;
pub mod hivelocity;
pub mod digitalocean;
pub mod vultr;
pub mod aws;
pub mod equinix;
pub mod linode;
pub mod scaleway;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProviderTemplate {
    pub id: String,
    pub name: String,
    pub provider: String,
    pub cpu: u32,
    pub memory_gb: u32,
    pub storage_gb: u32,
    pub bandwidth_tb: f64,
    pub price_hourly: f64,
    pub price_monthly: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gpu: Option<String>,
    pub regions: Vec<String>,
    pub features: Vec<String>,
}

impl ProviderTemplate {
    pub fn price_annual(&self) -> f64 {
        self.price_monthly * 12.0
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Instance {
    pub id: String,
    pub name: String,
    pub provider: String,
    pub template: String,
    pub region: String,
    pub status: String,
    pub ip_address: String,
    pub cost_hourly: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeployConfig {
    pub name: String,
    pub region: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub os: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ssh_keys: Option<Vec<String>>,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

pub trait Provider: Send + Sync {
    fn name(&self) -> &str;
    fn templates(&self) -> &[ProviderTemplate];
    fn regions(&self) -> &[String];

    fn deploy(&self, template_id: &str, config: &DeployConfig) -> Result<Instance>;
    fn list_instances(&self) -> Result<Vec<Instance>>;
    fn get_instance(&self, instance_id: &str) -> Result<Instance>;
    fn delete_instance(&self, instance_id: &str) -> Result<bool>;
    fn start_instance(&self, instance_id: &str) -> Result<bool>;
    fn stop_instance(&self, instance_id: &str) -> Result<bool>;

    fn get_template(&self, template_id: &str) -> Option<&ProviderTemplate> {
        self.templates().iter().find(|t| t.id == template_id)
    }

    fn validate_credentials(&self) -> Result<bool> {
        // Default implementation - can be overridden
        Ok(true)
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ProviderConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

pub struct ProviderManager {
    config_file: PathBuf,
    config: HashMap<String, ProviderConfig>,
    providers: HashMap<String, Box<dyn Provider>>,
}

impl ProviderManager {
    pub fn new(config_file: Option<PathBuf>) -> Result<Self> {
        let config_file = config_file.unwrap_or_else(|| {
            let home = home::home_dir().expect("Could not find home directory");
            home.join(".capsule").join("providers.yml")
        });

        let config = if config_file.exists() {
            let content = std::fs::read_to_string(&config_file)?;
            serde_yaml::from_str(&content)?
        } else {
            HashMap::new()
        };

        let mut manager = Self {
            config_file,
            config,
            providers: HashMap::new(),
        };

        manager.initialize_providers()?;
        Ok(manager)
    }

    fn initialize_providers(&mut self) -> Result<()> {
        // Initialize all providers - Cherry Servers first!
        let cherry_api_key = self.config
            .get("cherry")
            .and_then(|c| c.api_key.clone());
        self.providers.insert(
            "cherry".to_string(),
            Box::new(cherry::CherryServersProvider::new(cherry_api_key)),
        );

        let hivelocity_api_key = self.config
            .get("hivelocity")
            .and_then(|c| c.api_key.clone());
        self.providers.insert(
            "hivelocity".to_string(),
            Box::new(hivelocity::HivelocityProvider::new(hivelocity_api_key)),
        );

        let digitalocean_api_key = self.config
            .get("digitalocean")
            .and_then(|c| c.api_key.clone());
        self.providers.insert(
            "digitalocean".to_string(),
            Box::new(digitalocean::DigitalOceanProvider::new(digitalocean_api_key)),
        );

        let vultr_api_key = self.config
            .get("vultr")
            .and_then(|c| c.api_key.clone());
        self.providers.insert(
            "vultr".to_string(),
            Box::new(vultr::VultrProvider::new(vultr_api_key)),
        );

        let aws_api_key = self.config
            .get("aws")
            .and_then(|c| c.api_key.clone());
        self.providers.insert(
            "aws".to_string(),
            Box::new(aws::AWSProvider::new(aws_api_key)),
        );

        let equinix_api_key = self.config
            .get("equinix")
            .and_then(|c| c.api_key.clone());
        self.providers.insert(
            "equinix".to_string(),
            Box::new(equinix::EquinixProvider::new(equinix_api_key)),
        );

        let linode_api_key = self.config
            .get("linode")
            .and_then(|c| c.api_key.clone());
        self.providers.insert(
            "linode".to_string(),
            Box::new(linode::LinodeProvider::new(linode_api_key)),
        );

        let scaleway_api_key = self.config
            .get("scaleway")
            .and_then(|c| c.api_key.clone());
        self.providers.insert(
            "scaleway".to_string(),
            Box::new(scaleway::ScalewayProvider::new(scaleway_api_key)),
        );

        Ok(())
    }

    pub fn list_providers(&self) -> Vec<String> {
        let mut providers: Vec<String> = self.providers.keys().cloned().collect();
        // Sort providers, but Cherry Servers always first!
        providers.sort();
        if let Some(cherry_pos) = providers.iter().position(|p| p == "cherry") {
            providers.remove(cherry_pos);
            providers.insert(0, "cherry".to_string());
        }
        providers
    }

    pub fn get_provider(&self, name: &str) -> Option<&Box<dyn Provider>> {
        self.providers.get(name)
    }

    pub fn get_all_templates(&self) -> Vec<ProviderTemplate> {
        let mut templates = Vec::new();
        for provider in self.providers.values() {
            templates.extend(provider.templates().to_vec());
        }
        templates
    }

    pub fn compare_templates(
        &self,
        min_cpu: u32,
        min_memory: u32,
        max_price: f64,
    ) -> Vec<ProviderTemplate> {
        let mut templates: Vec<ProviderTemplate> = self.get_all_templates()
            .into_iter()
            .filter(|t| {
                t.cpu >= min_cpu &&
                t.memory_gb >= min_memory &&
                t.price_hourly <= max_price
            })
            .collect();

        templates.sort_by(|a, b| a.price_hourly.partial_cmp(&b.price_hourly).unwrap());
        templates
    }

    pub fn get_cheapest_option(&self, min_cpu: u32, min_memory: u32) -> Option<ProviderTemplate> {
        self.compare_templates(min_cpu, min_memory, f64::MAX).first().cloned()
    }

    pub fn get_gpu_templates(&self) -> Vec<ProviderTemplate> {
        self.get_all_templates()
            .into_iter()
            .filter(|t| t.gpu.is_some())
            .collect()
    }

    pub fn deploy_to_provider(
        &self,
        provider_name: &str,
        template_id: &str,
        config: &DeployConfig,
    ) -> Result<Instance> {
        let provider = self.get_provider(provider_name)
            .ok_or_else(|| anyhow::anyhow!("Provider {} not found", provider_name))?;

        provider.deploy(template_id, config)
    }

    pub fn configure_provider(&mut self, provider_name: String, api_key: String) -> Result<()> {
        if !self.providers.contains_key(&provider_name) {
            anyhow::bail!("Unknown provider: {}", provider_name);
        }

        self.config
            .entry(provider_name.clone())
            .or_insert_with(|| ProviderConfig {
                api_key: None,
                extra: HashMap::new(),
            })
            .api_key = Some(api_key);

        self.save_config()?;
        self.initialize_providers()?;

        println!("Configured {} provider", provider_name);
        Ok(())
    }

    fn save_config(&self) -> Result<()> {
        if let Some(parent) = self.config_file.parent() {
            std::fs::create_dir_all(parent)?;
        }

        let yaml = serde_yaml::to_string(&self.config)?;
        std::fs::write(&self.config_file, yaml)?;
        Ok(())
    }
}
