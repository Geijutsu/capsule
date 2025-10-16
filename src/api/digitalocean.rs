/// DigitalOcean API Client
///
/// Provides API client for DigitalOcean's cloud infrastructure platform.
/// Uses Bearer token authentication.

use super::client::ApiClient;
use super::error::ApiResult;

/// DigitalOcean API client
pub struct DigitalOceanClient {
    client: ApiClient,
}

impl DigitalOceanClient {
    /// Create a new DigitalOcean API client
    ///
    /// # Arguments
    ///
    /// * `api_key` - DigitalOcean API token
    ///
    /// # Example
    ///
    /// ```no_run
    /// use capsule::api::digitalocean::DigitalOceanClient;
    ///
    /// let client = DigitalOceanClient::new("your-api-token").unwrap();
    /// ```
    pub fn new(api_key: impl Into<String>) -> ApiResult<Self> {
        let client = ApiClient::builder("https://api.digitalocean.com/v2")
            .bearer_auth(api_key)
            .build()?;

        Ok(Self { client })
    }

    /// Get reference to underlying API client
    pub fn client(&self) -> &ApiClient {
        &self.client
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_client_creation() {
        let client = DigitalOceanClient::new("test-token");
        assert!(client.is_ok());
    }
}
