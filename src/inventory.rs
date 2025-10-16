use crate::cost::{CostReport, DeploymentRecord};
use crate::xnode::XNode;
use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

const VERSION: &str = "1.0";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct XNodeEntry {
    pub id: String,
    pub name: String,
    pub provider: String,
    pub template: String,
    pub status: String,
    pub ip_address: String,
    pub ssh_port: u16,
    pub region: Option<String>,
    pub deployed_at: DateTime<Utc>,
    pub cost_hourly: f64,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InventoryMetadata {
    pub total_deployed: usize,
    pub total_running: usize,
    pub total_lifetime_cost: f64,
}

impl Default for InventoryMetadata {
    fn default() -> Self {
        Self {
            total_deployed: 0,
            total_running: 0,
            total_lifetime_cost: 0.0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct InventoryData {
    version: String,
    last_updated: DateTime<Utc>,
    xnodes: HashMap<String, XNodeEntry>,
    history: Vec<DeploymentRecord>,
    metadata: InventoryMetadata,
}

pub struct XNodeInventory {
    inventory_file: PathBuf,
    xnodes: HashMap<String, XNodeEntry>,
    history: Vec<DeploymentRecord>,
    metadata: InventoryMetadata,
}

impl XNodeInventory {
    pub fn new(inventory_file: Option<PathBuf>) -> Result<Self> {
        let inventory_file = inventory_file.unwrap_or_else(|| {
            let home = dirs::home_dir().expect("Failed to get home directory");
            home.join(".capsule").join("inventory.json")
        });

        let mut inventory = Self {
            inventory_file,
            xnodes: HashMap::new(),
            history: Vec::new(),
            metadata: InventoryMetadata::default(),
        };

        inventory.ensure_directory()?;
        inventory.load()?;

        Ok(inventory)
    }

    fn ensure_directory(&self) -> Result<()> {
        if let Some(parent) = self.inventory_file.parent() {
            fs::create_dir_all(parent)
                .context("Failed to create inventory directory")?;
        }
        Ok(())
    }

    fn backup_inventory(&self) -> Result<()> {
        if self.inventory_file.exists() {
            let backup_file = self.inventory_file.with_extension("json.backup");
            fs::copy(&self.inventory_file, &backup_file)
                .context("Failed to create inventory backup")?;
        }
        Ok(())
    }

    pub fn load(&mut self) -> Result<()> {
        if !self.inventory_file.exists() {
            return Ok(());
        }

        let contents = fs::read_to_string(&self.inventory_file)
            .context("Failed to read inventory file")?;

        let data: InventoryData = serde_json::from_str(&contents)
            .context("Failed to parse inventory JSON")?;

        self.xnodes = data.xnodes;
        self.history = data.history;
        self.metadata = data.metadata;

        Ok(())
    }

    pub fn save(&self) -> Result<()> {
        self.backup_inventory()?;

        let data = InventoryData {
            version: VERSION.to_string(),
            last_updated: Utc::now(),
            xnodes: self.xnodes.clone(),
            history: self.history.clone(),
            metadata: self.metadata.clone(),
        };

        let json = serde_json::to_string_pretty(&data)
            .context("Failed to serialize inventory")?;

        fs::write(&self.inventory_file, json)
            .context("Failed to write inventory file")?;

        Ok(())
    }

    pub fn add_xnode(
        &mut self,
        xnode: &XNode,
        provider: String,
        template: String,
        cost_hourly: f64,
        tags: Vec<String>,
    ) -> Result<()> {
        if self.xnodes.contains_key(&xnode.id) {
            anyhow::bail!("XNode with ID {} already exists in inventory", xnode.id);
        }

        let entry = XNodeEntry {
            id: xnode.id.clone(),
            name: xnode.name.clone(),
            provider: provider.clone(),
            template: template.clone(),
            status: xnode.status.clone(),
            ip_address: xnode.ip_address.clone(),
            ssh_port: xnode.ssh_port,
            region: xnode.region.clone(),
            deployed_at: xnode.created_at,
            cost_hourly,
            tags: tags.clone(),
            metadata: xnode.metadata.clone(),
        };

        self.xnodes.insert(xnode.id.clone(), entry);

        let record = DeploymentRecord::new(
            xnode.id.clone(),
            provider,
            template,
            xnode.created_at,
            xnode.region.clone(),
            Some(xnode.name.clone()),
            tags,
        );
        self.history.push(record);

        self.metadata.total_deployed += 1;
        if xnode.status == "running" {
            self.metadata.total_running += 1;
        }

        self.save()?;
        Ok(())
    }

    pub fn remove_xnode(&mut self, xnode_id: &str) -> Result<()> {
        let entry = self.xnodes.get(xnode_id)
            .ok_or_else(|| anyhow::anyhow!("XNode {} not found in inventory", xnode_id))?
            .clone();

        // Update history record
        for record in &mut self.history {
            if record.xnode_id == xnode_id && record.is_active() {
                record.terminated_at = Some(Utc::now());
                record.uptime_hours = record.calculate_uptime();
                record.total_cost = record.uptime_hours * entry.cost_hourly;
                self.metadata.total_lifetime_cost += record.total_cost;
                break;
            }
        }

        // Update running count
        if entry.status == "running" {
            self.metadata.total_running = self.metadata.total_running.saturating_sub(1);
        }

        self.xnodes.remove(xnode_id);
        self.save()?;
        Ok(())
    }

    pub fn get_xnode(&self, xnode_id: &str) -> Option<&XNodeEntry> {
        self.xnodes.get(xnode_id)
    }

    pub fn update_xnode(&mut self, xnode_id: &str, updates: XNodeUpdate) -> Result<()> {
        let entry = self.xnodes.get_mut(xnode_id)
            .ok_or_else(|| anyhow::anyhow!("XNode {} not found in inventory", xnode_id))?;

        let old_status = entry.status.clone();

        if let Some(status) = updates.status {
            entry.status = status.clone();

            // Update running count if status changed
            if old_status != status {
                if old_status == "running" {
                    self.metadata.total_running = self.metadata.total_running.saturating_sub(1);
                }
                if status == "running" {
                    self.metadata.total_running += 1;
                }
            }
        }

        if let Some(ip_address) = updates.ip_address {
            entry.ip_address = ip_address;
        }

        if let Some(region) = updates.region {
            entry.region = Some(region);
        }

        if let Some(cost_hourly) = updates.cost_hourly {
            entry.cost_hourly = cost_hourly;
        }

        self.save()?;
        Ok(())
    }

    pub fn list_all(&self) -> Vec<&XNodeEntry> {
        self.xnodes.values().collect()
    }

    pub fn list_by_provider(&self, provider: &str) -> Vec<&XNodeEntry> {
        self.xnodes
            .values()
            .filter(|xnode| xnode.provider == provider)
            .collect()
    }

    pub fn list_by_status(&self, status: &str) -> Vec<&XNodeEntry> {
        self.xnodes
            .values()
            .filter(|xnode| xnode.status == status)
            .collect()
    }

    pub fn list_by_tags(&self, tags: &[String], match_all: bool) -> Vec<&XNodeEntry> {
        self.xnodes
            .values()
            .filter(|xnode| {
                let xnode_tags: std::collections::HashSet<_> = xnode.tags.iter().collect();
                let search_tags: std::collections::HashSet<_> = tags.iter().collect();

                if match_all {
                    search_tags.is_subset(&xnode_tags)
                } else {
                    !xnode_tags.is_disjoint(&search_tags)
                }
            })
            .collect()
    }

    pub fn search(&self, query: &str) -> Vec<&XNodeEntry> {
        let query_lower = query.to_lowercase();
        self.xnodes
            .values()
            .filter(|xnode| {
                xnode.name.to_lowercase().contains(&query_lower)
                    || xnode.id.to_lowercase().contains(&query_lower)
            })
            .collect()
    }

    pub fn get_total_cost(&self) -> HashMap<String, f64> {
        let total_hourly: f64 = self.xnodes
            .values()
            .filter(|xnode| xnode.status == "running")
            .map(|xnode| xnode.cost_hourly)
            .sum();

        let mut costs = HashMap::new();
        costs.insert("hourly".to_string(), total_hourly);
        costs.insert("daily".to_string(), total_hourly * 24.0);
        costs.insert("monthly".to_string(), total_hourly * 24.0 * 30.0);
        costs.insert("annual".to_string(), total_hourly * 24.0 * 365.0);
        costs
    }

    pub fn get_cost_report(&self) -> CostReport {
        let mut by_provider: HashMap<String, f64> = HashMap::new();
        let mut by_region: HashMap<String, f64> = HashMap::new();
        let mut active_count = 0;

        for xnode in self.xnodes.values() {
            if xnode.status == "running" {
                let cost = xnode.cost_hourly;
                *by_provider.entry(xnode.provider.clone()).or_insert(0.0) += cost;

                if let Some(ref region) = xnode.region {
                    *by_region.entry(region.clone()).or_insert(0.0) += cost;
                } else {
                    *by_region.entry("unknown".to_string()).or_insert(0.0) += cost;
                }

                active_count += 1;
            }
        }

        let costs = self.get_total_cost();
        let total_hourly = costs.get("hourly").copied().unwrap_or(0.0);

        CostReport::new(
            total_hourly,
            by_provider,
            by_region,
            active_count,
            self.xnodes.len(),
        )
    }

    pub fn get_statistics(&self) -> InventoryStatistics {
        let mut status_distribution: HashMap<String, usize> = HashMap::new();
        let mut provider_distribution: HashMap<String, usize> = HashMap::new();
        let mut region_distribution: HashMap<String, usize> = HashMap::new();

        for xnode in self.xnodes.values() {
            *status_distribution.entry(xnode.status.clone()).or_insert(0) += 1;
            *provider_distribution.entry(xnode.provider.clone()).or_insert(0) += 1;

            let region = xnode.region.clone().unwrap_or_else(|| "unknown".to_string());
            *region_distribution.entry(region).or_insert(0) += 1;
        }

        let active_history: Vec<_> = self.history
            .iter()
            .filter(|r| r.is_active())
            .collect();

        let terminated: Vec<_> = self.history
            .iter()
            .filter(|r| !r.is_active())
            .collect();

        let avg_uptime = if !terminated.is_empty() {
            terminated.iter().map(|r| r.uptime_hours).sum::<f64>() / terminated.len() as f64
        } else {
            0.0
        };

        let mut sorted_by_cost: Vec<_> = self.xnodes.values().collect();
        sorted_by_cost.sort_by(|a, b| b.cost_hourly.partial_cmp(&a.cost_hourly).unwrap());

        let most_expensive: Vec<MostExpensiveXNode> = sorted_by_cost
            .iter()
            .take(5)
            .map(|x| MostExpensiveXNode {
                id: x.id.clone(),
                name: x.name.clone(),
                cost_hourly: x.cost_hourly,
            })
            .collect();

        let mut longest_running: Vec<LongestRunningXNode> = active_history
            .iter()
            .map(|r| {
                let uptime = r.calculate_uptime();
                LongestRunningXNode {
                    id: r.xnode_id.clone(),
                    name: r.name.clone().unwrap_or_default(),
                    uptime_hours: uptime,
                    uptime_days: uptime / 24.0,
                }
            })
            .collect();
        longest_running.sort_by(|a, b| b.uptime_hours.partial_cmp(&a.uptime_hours).unwrap());
        longest_running.truncate(5);

        InventoryStatistics {
            total_xnodes: self.xnodes.len(),
            status_distribution,
            provider_distribution,
            region_distribution,
            total_deployments: self.history.len(),
            active_deployments: active_history.len(),
            terminated_deployments: terminated.len(),
            average_uptime_hours: avg_uptime,
            lifetime_cost: self.metadata.total_lifetime_cost,
            most_expensive,
            longest_running,
        }
    }

    pub fn export_csv(&self, filename: &str) -> Result<()> {
        use std::io::Write;

        let file = fs::File::create(filename)
            .context("Failed to create CSV file")?;
        let mut writer = std::io::BufWriter::new(file);

        // Write header
        writeln!(
            writer,
            "id,name,provider,status,ip_address,region,deployed_at,cost_hourly,tags"
        )?;

        // Write rows
        for xnode in self.xnodes.values() {
            let region = xnode.region.as_deref().unwrap_or("");
            let tags = xnode.tags.join(",");
            writeln!(
                writer,
                "{},{},{},{},{},{},{},{:.2},{}",
                xnode.id,
                xnode.name,
                xnode.provider,
                xnode.status,
                xnode.ip_address,
                region,
                xnode.deployed_at.to_rfc3339(),
                xnode.cost_hourly,
                tags
            )?;
        }

        Ok(())
    }

    pub fn import_csv(&mut self, filename: &str) -> Result<usize> {
        use std::io::BufRead;

        let file = fs::File::open(filename)
            .context("Failed to open CSV file")?;
        let reader = std::io::BufReader::new(file);

        let mut imported = 0;
        let mut lines = reader.lines();

        // Skip header
        lines.next();

        for line in lines {
            let line = line?;
            let parts: Vec<&str> = line.split(',').collect();

            if parts.len() < 8 {
                continue;
            }

            let xnode_id = parts[0].to_string();

            // Skip if already exists
            if self.xnodes.contains_key(&xnode_id) {
                continue;
            }

            let deployed_at = DateTime::parse_from_rfc3339(parts[6])
                .unwrap_or_else(|_| Utc::now().into())
                .with_timezone(&Utc);

            let tags = if parts.len() > 8 {
                parts[8].split(',').map(|s| s.trim().to_string()).collect()
            } else {
                Vec::new()
            };

            let xnode = XNode {
                id: xnode_id,
                name: parts[1].to_string(),
                status: parts[3].to_string(),
                ip_address: parts[4].to_string(),
                ssh_port: 22,
                tunnel_port: None,
                created_at: deployed_at,
                region: if parts[5].is_empty() {
                    None
                } else {
                    Some(parts[5].to_string())
                },
                metadata: HashMap::new(),
            };

            let cost_hourly = parts[7].parse::<f64>().unwrap_or(0.0);

            self.add_xnode(
                &xnode,
                parts[2].to_string(),
                "imported".to_string(),
                cost_hourly,
                tags,
            )?;

            imported += 1;
        }

        Ok(imported)
    }

    pub fn get_deployment_history(
        &self,
        xnode_id: Option<&str>,
        provider: Option<&str>,
        limit: Option<usize>,
    ) -> Vec<&DeploymentRecord> {
        let mut records: Vec<_> = self.history.iter().collect();

        // Apply filters
        if let Some(id) = xnode_id {
            records.retain(|r| r.xnode_id == id);
        }

        if let Some(prov) = provider {
            records.retain(|r| r.provider == prov);
        }

        // Sort by deployment time (newest first)
        records.sort_by(|a, b| b.deployed_at.cmp(&a.deployed_at));

        // Apply limit
        if let Some(limit) = limit {
            records.truncate(limit);
        }

        records
    }

    pub fn cleanup_old_history(&mut self, days: u64) -> Result<usize> {
        let cutoff = Utc::now() - chrono::Duration::days(days as i64);
        let original_count = self.history.len();

        self.history.retain(|record| {
            record.is_active()
                || record
                    .terminated_at
                    .map(|t| t > cutoff)
                    .unwrap_or(false)
        });

        let removed = original_count - self.history.len();

        if removed > 0 {
            self.save()?;
        }

        Ok(removed)
    }
}

#[derive(Debug, Clone)]
pub struct XNodeUpdate {
    pub status: Option<String>,
    pub ip_address: Option<String>,
    pub region: Option<String>,
    pub cost_hourly: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InventoryStatistics {
    pub total_xnodes: usize,
    pub status_distribution: HashMap<String, usize>,
    pub provider_distribution: HashMap<String, usize>,
    pub region_distribution: HashMap<String, usize>,
    pub total_deployments: usize,
    pub active_deployments: usize,
    pub terminated_deployments: usize,
    pub average_uptime_hours: f64,
    pub lifetime_cost: f64,
    pub most_expensive: Vec<MostExpensiveXNode>,
    pub longest_running: Vec<LongestRunningXNode>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MostExpensiveXNode {
    pub id: String,
    pub name: String,
    pub cost_hourly: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LongestRunningXNode {
    pub id: String,
    pub name: String,
    pub uptime_hours: f64,
    pub uptime_days: f64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_inventory_creation() {
        let temp_dir = TempDir::new().unwrap();
        let inventory_file = temp_dir.path().join("inventory.json");

        let inventory = XNodeInventory::new(Some(inventory_file.clone())).unwrap();
        assert_eq!(inventory.xnodes.len(), 0);
        assert_eq!(inventory.metadata.total_deployed, 0);
    }

    #[test]
    fn test_add_and_remove_xnode() {
        let temp_dir = TempDir::new().unwrap();
        let inventory_file = temp_dir.path().join("inventory.json");

        let mut inventory = XNodeInventory::new(Some(inventory_file)).unwrap();

        let xnode = XNode::new(
            "test-1".to_string(),
            "Test Node".to_string(),
            "running".to_string(),
            "192.168.1.1".to_string(),
        );

        inventory
            .add_xnode(&xnode, "test-provider".to_string(), "default".to_string(), 1.5, vec![])
            .unwrap();

        assert_eq!(inventory.xnodes.len(), 1);
        assert_eq!(inventory.metadata.total_deployed, 1);
        assert_eq!(inventory.metadata.total_running, 1);

        inventory.remove_xnode("test-1").unwrap();
        assert_eq!(inventory.xnodes.len(), 0);
        assert_eq!(inventory.metadata.total_running, 0);
    }
}
