use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostReport {
    pub total_hourly: f64,
    pub total_daily: f64,
    pub total_monthly: f64,
    pub projected_annual: f64,
    pub by_provider: HashMap<String, f64>,
    pub by_region: HashMap<String, f64>,
    pub active_count: usize,
    pub total_count: usize,
}

impl CostReport {
    pub fn new(
        total_hourly: f64,
        by_provider: HashMap<String, f64>,
        by_region: HashMap<String, f64>,
        active_count: usize,
        total_count: usize,
    ) -> Self {
        Self {
            total_hourly,
            total_daily: total_hourly * 24.0,
            total_monthly: total_hourly * 24.0 * 30.0,
            projected_annual: total_hourly * 24.0 * 365.0,
            by_provider,
            by_region,
            active_count,
            total_count,
        }
    }

    pub fn generate_report(&self) -> String {
        let mut lines = vec![
            "============================================================".to_string(),
            "XNODE INVENTORY COST REPORT".to_string(),
            "============================================================".to_string(),
            format!("Generated: {}", Utc::now().format("%Y-%m-%d %H:%M:%S")),
            String::new(),
            "SUMMARY".to_string(),
            "------------------------------------------------------------".to_string(),
            format!("Active xNodes:    {}", self.active_count),
            format!("Total xNodes:     {}", self.total_count),
            String::new(),
            "COST OVERVIEW".to_string(),
            "------------------------------------------------------------".to_string(),
            format!("Hourly:           ${:.2}", self.total_hourly),
            format!("Daily:            ${:.2}", self.total_daily),
            format!("Monthly:          ${:.2}", self.total_monthly),
            format!("Annual (proj.):   ${:.2}", self.projected_annual),
            String::new(),
            "BY PROVIDER".to_string(),
            "------------------------------------------------------------".to_string(),
        ];

        if self.by_provider.is_empty() {
            lines.push("  No data available".to_string());
        } else {
            let mut providers: Vec<_> = self.by_provider.iter().collect();
            providers.sort_by(|a, b| b.1.partial_cmp(a.1).unwrap());
            for (provider, cost) in providers {
                lines.push(format!("  {:<20} ${:.2}/hour", provider, cost));
            }
        }

        lines.push(String::new());
        lines.push("BY REGION".to_string());
        lines.push("------------------------------------------------------------".to_string());

        if self.by_region.is_empty() {
            lines.push("  No data available".to_string());
        } else {
            let mut regions: Vec<_> = self.by_region.iter().collect();
            regions.sort_by(|a, b| b.1.partial_cmp(a.1).unwrap());
            for (region, cost) in regions {
                lines.push(format!("  {:<20} ${:.2}/hour", region, cost));
            }
        }

        lines.push("============================================================".to_string());

        lines.join("\n")
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeploymentRecord {
    pub xnode_id: String,
    pub provider: String,
    pub template: String,
    pub deployed_at: DateTime<Utc>,
    pub terminated_at: Option<DateTime<Utc>>,
    pub total_cost: f64,
    pub uptime_hours: f64,
    pub region: Option<String>,
    pub name: Option<String>,
    #[serde(default)]
    pub tags: Vec<String>,
}

impl DeploymentRecord {
    pub fn new(
        xnode_id: String,
        provider: String,
        template: String,
        deployed_at: DateTime<Utc>,
        region: Option<String>,
        name: Option<String>,
        tags: Vec<String>,
    ) -> Self {
        Self {
            xnode_id,
            provider,
            template,
            deployed_at,
            terminated_at: None,
            total_cost: 0.0,
            uptime_hours: 0.0,
            region,
            name,
            tags,
        }
    }

    pub fn calculate_uptime(&self) -> f64 {
        let end_time = self.terminated_at.unwrap_or_else(Utc::now);
        let duration = end_time.signed_duration_since(self.deployed_at);
        duration.num_seconds() as f64 / 3600.0
    }

    pub fn is_active(&self) -> bool {
        self.terminated_at.is_none()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cost_report_calculations() {
        let report = CostReport::new(
            10.0,
            HashMap::new(),
            HashMap::new(),
            5,
            10,
        );

        assert_eq!(report.total_hourly, 10.0);
        assert_eq!(report.total_daily, 240.0);
        assert_eq!(report.total_monthly, 7200.0);
        assert_eq!(report.projected_annual, 87600.0);
    }

    #[test]
    fn test_deployment_record_uptime() {
        let now = Utc::now();
        let deployed = now - chrono::Duration::hours(5);

        let record = DeploymentRecord::new(
            "test-id".to_string(),
            "test-provider".to_string(),
            "default".to_string(),
            deployed,
            None,
            Some("test".to_string()),
            vec![],
        );

        let uptime = record.calculate_uptime();
        assert!((uptime - 5.0).abs() < 0.1);
    }
}
