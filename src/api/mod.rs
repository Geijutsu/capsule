/// API Client Module for Provider Integrations
///
/// Provides base API client functionality for making HTTP requests to various
/// cloud and bare metal provider APIs with proper error handling, retries,
/// rate limiting, and logging.
///
/// # Architecture
///
/// The module is organized as follows:
///
/// - `error`: Error types for API operations
/// - `client`: Base API client with retry logic and rate limiting
/// - Provider-specific clients: `digitalocean`, `hivelocity`, `vultr`, `linode`, `scaleway`, `equinix`, `aws`
///
/// # Features
///
/// - **Automatic Retries**: Exponential backoff for failed requests (max 3 retries)
/// - **Rate Limit Handling**: Automatic detection and waiting for 429 responses
/// - **Connection Pooling**: Efficient HTTP connection reuse
/// - **Standardized Error Handling**: Consistent error types across all providers
/// - **Request Logging**: Debug logging for all API operations
///
/// # Example
///
/// ```no_run
/// use capsule::api::digitalocean::DigitalOceanClient;
/// use serde_json::json;
///
/// #[tokio::main]
/// async fn main() -> Result<(), Box<dyn std::error::Error>> {
///     let client = DigitalOceanClient::new("your-api-token")?;
///
///     // Make API requests using the client
///     let response: serde_json::Value = client
///         .client()
///         .get("/droplets", None)
///         .await?;
///
///     Ok(())
/// }
/// ```

pub mod error;
pub mod client;

// Provider-specific clients
pub mod aws;
pub mod digitalocean;
pub mod equinix;
pub mod hivelocity;
pub mod linode;
pub mod scaleway;
pub mod vultr;

// Re-export commonly used types
pub use error::{ApiError, ApiResult};
pub use client::{ApiClient, AuthMethod};

// Re-export provider clients
pub use aws::AwsClient;
pub use digitalocean::DigitalOceanClient;
pub use equinix::EquinixMetalClient;
pub use hivelocity::HivelocityClient;
pub use linode::LinodeClient;
pub use scaleway::ScalewayClient;
pub use vultr::VultrClient;

/// Provider enum for identifying cloud/bare metal providers
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Provider {
    Aws,
    DigitalOcean,
    Equinix,
    Hivelocity,
    Linode,
    Scaleway,
    Vultr,
}

impl Provider {
    /// Get provider name as string
    pub fn as_str(&self) -> &'static str {
        match self {
            Provider::Aws => "aws",
            Provider::DigitalOcean => "digitalocean",
            Provider::Equinix => "equinix",
            Provider::Hivelocity => "hivelocity",
            Provider::Linode => "linode",
            Provider::Scaleway => "scaleway",
            Provider::Vultr => "vultr",
        }
    }

    /// Parse provider from string
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "aws" => Some(Provider::Aws),
            "digitalocean" | "do" => Some(Provider::DigitalOcean),
            "equinix" | "equinix-metal" => Some(Provider::Equinix),
            "hivelocity" => Some(Provider::Hivelocity),
            "linode" => Some(Provider::Linode),
            "scaleway" => Some(Provider::Scaleway),
            "vultr" => Some(Provider::Vultr),
            _ => None,
        }
    }

    /// Get all supported providers
    pub fn all() -> Vec<Provider> {
        vec![
            Provider::Aws,
            Provider::DigitalOcean,
            Provider::Equinix,
            Provider::Hivelocity,
            Provider::Linode,
            Provider::Scaleway,
            Provider::Vultr,
        ]
    }
}

impl std::fmt::Display for Provider {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_provider_parsing() {
        assert_eq!(Provider::from_str("aws"), Some(Provider::Aws));
        assert_eq!(Provider::from_str("digitalocean"), Some(Provider::DigitalOcean));
        assert_eq!(Provider::from_str("do"), Some(Provider::DigitalOcean));
        assert_eq!(Provider::from_str("hivelocity"), Some(Provider::Hivelocity));
        assert_eq!(Provider::from_str("invalid"), None);
    }

    #[test]
    fn test_provider_display() {
        assert_eq!(Provider::Aws.to_string(), "aws");
        assert_eq!(Provider::DigitalOcean.to_string(), "digitalocean");
    }

    #[test]
    fn test_provider_all() {
        let providers = Provider::all();
        assert_eq!(providers.len(), 7);
    }
}
