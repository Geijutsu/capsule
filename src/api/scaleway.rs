/// Scaleway API Client
///
/// Provides API client for Scaleway's cloud infrastructure platform.
/// Uses X-Auth-Token header authentication.

use super::client::ApiClient;
use super::error::ApiResult;

/// Scaleway API client
pub struct ScalewayClient {
    client: ApiClient,
}

impl ScalewayClient {
    /// Create a new Scaleway API client
    ///
    /// # Arguments
    ///
    /// * `api_key` - Scaleway secret key
    ///
    /// # Example
    ///
    /// ```no_run
    /// use capsule::api::scaleway::ScalewayClient;
    ///
    /// let client = ScalewayClient::new("your-secret-key").unwrap();
    /// ```
    pub fn new(api_key: impl Into<String>) -> ApiResult<Self> {
        let client = ApiClient::builder("https://api.scaleway.com")
            .api_key_auth("X-Auth-Token", api_key)
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
        let client = ScalewayClient::new("test-key");
        assert!(client.is_ok());
    }
}
