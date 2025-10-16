# API Integration for OpenMesh Providers

This document describes the real API integration implemented for the capsule OpenMesh xNode deployment system.

## Overview

The capsule package now includes full API integration for deploying and managing instances across multiple cloud and bare metal providers:

- **Hivelocity** - Bare metal servers
- **DigitalOcean** - Cloud droplets
- **Vultr** - Cloud compute instances
- **AWS EC2** - Cloud instances
- **Equinix Metal** - Bare metal servers

## Architecture

### API Client Module (`api_clients.py`)

The base `APIClient` class provides common functionality:

- **Automatic retries** with exponential backoff
- **Rate limit handling** with configurable delays
- **Standardized error handling** with custom exceptions
- **Session management** with connection pooling
- **Request/response logging** for debugging

Provider-specific clients extend the base class:
- `HivelocityAPIClient` - Uses X-API-Key header
- `DigitalOceanAPIClient` - Uses Bearer token
- `VultrAPIClient` - Uses Bearer token
- `EquinixMetalAPIClient` - Uses X-Auth-Token header
- AWS uses boto3 SDK directly

### Provider Classes (`providers.py`)

Each provider class implements:

1. **Initialization** - Sets up API client with credentials
2. **Template definitions** - Available instance types and pricing
3. **Region definitions** - Available datacenter locations
4. **Core operations**:
   - `deploy()` - Create new instance
   - `list_instances()` - List all instances
   - `get_instance()` - Get instance details
   - `delete_instance()` - Terminate instance
   - `start_instance()` - Power on instance
   - `stop_instance()` - Power off instance

## Configuration

### API Keys

Set API keys via environment variables or configuration file:

```bash
# Environment variables
export HIVELOCITY_API_KEY="your-key-here"
export DIGITALOCEAN_API_KEY="your-token-here"
export VULTR_API_KEY="your-key-here"
export EQUINIX_API_KEY="your-token-here"

# AWS credentials (standard boto3 configuration)
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
```

Or use the configuration file at `~/.capsule/providers.yml`:

```yaml
hivelocity:
  api_key: "your-key-here"
digitalocean:
  api_key: "your-token-here"
vultr:
  api_key: "your-key-here"
equinix:
  api_key: "your-token-here"
```

### Installation

Install with API integration dependencies:

```bash
cd capsule
pip install -e .
```

This installs:
- `requests>=2.25.0` - HTTP client for API calls
- `boto3>=1.18.0` - AWS SDK (optional)

## Usage Examples

### Basic Deployment

```python
from capsule_package.providers import ProviderManager

# Initialize manager
manager = ProviderManager()

# Deploy to DigitalOcean
config = {
    'name': 'my-xnode',
    'region': 'nyc1',
    'ssh_keys': ['your-ssh-key-id'],
}

result = manager.deploy_to_provider('digitalocean', 'do-basic-2', config)
print(f"Deployed instance: {result['id']}")
```

### List Instances

```python
# List all instances from a provider
provider = manager.get_provider('hivelocity')
instances = provider.list_instances()

for instance in instances:
    print(f"{instance['name']}: {instance['status']} - {instance['ip_address']}")
```

### Instance Lifecycle Management

```python
provider = manager.get_provider('vultr')

# Get instance details
instance = provider.get_instance('instance-id')

# Stop instance
provider.stop_instance('instance-id')

# Start instance
provider.start_instance('instance-id')

# Delete instance
provider.delete_instance('instance-id')
```

### Find Best Pricing

```python
# Find cheapest option meeting requirements
cheapest = manager.get_cheapest_option(min_cpu=4, min_memory=8)
print(f"{cheapest.name} ({cheapest.provider}): ${cheapest.price_hourly}/hr")

# Compare templates across providers
templates = manager.compare_templates(
    min_cpu=4,
    min_memory=8,
    max_price=0.10
)

for t in templates:
    print(f"{t.provider:15} {t.name:20} ${t.price_hourly:.3f}/hr")
```

## API Endpoints

### Hivelocity

- **Base URL**: `https://core.hivelocity.net/api/v2`
- **Auth**: `X-API-Key` header
- **Endpoints**:
  - `POST /device/order` - Create server
  - `GET /device` - List servers
  - `GET /device/{id}` - Get server details
  - `DELETE /device/{id}` - Delete server
  - `POST /device/{id}/power` - Power control

### DigitalOcean

- **Base URL**: `https://api.digitalocean.com/v2`
- **Auth**: `Authorization: Bearer {token}` header
- **Endpoints**:
  - `POST /droplets` - Create droplet
  - `GET /droplets` - List droplets
  - `GET /droplets/{id}` - Get droplet details
  - `DELETE /droplets/{id}` - Delete droplet
  - `POST /droplets/{id}/actions` - Perform action

### Vultr

- **Base URL**: `https://api.vultr.com/v2`
- **Auth**: `Authorization: Bearer {token}` header
- **Endpoints**:
  - `POST /instances` - Create instance
  - `GET /instances` - List instances
  - `GET /instances/{id}` - Get instance details
  - `DELETE /instances/{id}` - Delete instance
  - `POST /instances/{id}/start` - Start instance
  - `POST /instances/{id}/halt` - Stop instance

### AWS EC2

- **SDK**: boto3
- **Auth**: AWS credentials (env vars or ~/.aws/credentials)
- **Methods**:
  - `run_instances()` - Launch instance
  - `describe_instances()` - List/get instances
  - `terminate_instances()` - Delete instance
  - `start_instances()` - Start instance
  - `stop_instances()` - Stop instance

### Equinix Metal

- **Base URL**: `https://api.equinix.com/metal/v1`
- **Auth**: `X-Auth-Token` header
- **Endpoints**:
  - `POST /projects/{id}/devices` - Create device
  - `GET /devices` - List devices
  - `GET /devices/{id}` - Get device details
  - `DELETE /devices/{id}` - Delete device
  - `POST /devices/{id}/actions` - Perform action

## Error Handling

The API client provides comprehensive error handling:

### Exception Types

- `APIError` - Base exception for all API errors
- `AuthenticationError` - Authentication failed (401, 403)
- `RateLimitError` - Rate limit exceeded (429)
- `ResourceNotFoundError` - Resource not found (404)

### Example

```python
from capsule_package.api_clients import APIError, AuthenticationError

try:
    result = provider.deploy('template-id', config)
except AuthenticationError as e:
    print(f"Invalid API key: {e.message}")
except APIError as e:
    print(f"API error ({e.status_code}): {e.message}")
```

### Retry Logic

The API client automatically retries failed requests:

- **Max retries**: 3 (configurable)
- **Backoff strategy**: Exponential
- **Retry on**: 429, 500, 502, 503, 504 status codes
- **Rate limiting**: Automatic delay when rate limited

## Testing

Run the test suite:

```bash
cd capsule
python -m pytest tests/test_providers.py -v
```

The test suite includes:
- Mock API responses for all providers
- Unit tests for each provider class
- Integration tests for ProviderManager
- Error handling tests

### Mock Responses

The test suite uses mock API responses to avoid making real API calls:

```python
MOCK_RESPONSES = {
    'hivelocity_devices': {...},
    'digitalocean_droplets': {...},
    'vultr_instances': {...},
    'equinix_devices': {...}
}
```

## Rate Limiting

Each provider has different rate limits:

- **Hivelocity**: ~100 requests/minute
- **DigitalOcean**: 5000 requests/hour
- **Vultr**: 1000 requests/hour
- **AWS**: Varies by operation
- **Equinix**: 100 requests/minute

The API client handles rate limiting automatically with exponential backoff.

## Logging

Enable debug logging to see API requests/responses:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('capsule_package')
logger.setLevel(logging.DEBUG)
```

This will log:
- Request URLs and payloads
- Response status codes and data
- Error messages and stack traces
- Rate limit delays and retries

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use environment variables** or secure configuration
3. **Rotate keys regularly**
4. **Use read-only keys** when possible
5. **Implement IP allowlisting** where supported
6. **Monitor API usage** for anomalies

## Roadmap

Future enhancements:

- [ ] Async/await support for concurrent operations
- [ ] Linode API integration
- [ ] Scaleway API integration
- [ ] Webhook support for deployment events
- [ ] Cost tracking and budget alerts
- [ ] Multi-region deployment orchestration
- [ ] Backup and snapshot management
- [ ] Network configuration (VPCs, firewalls)

## Support

For issues or questions:

1. Check provider API documentation
2. Review error logs with DEBUG level
3. Verify API key permissions
4. Test with simple operations first

## References

- [Hivelocity API Docs](https://core.hivelocity.net/api-docs/)
- [DigitalOcean API Docs](https://docs.digitalocean.com/reference/api/)
- [Vultr API Docs](https://www.vultr.com/api/)
- [AWS EC2 Boto3 Docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html)
- [Equinix Metal API Docs](https://deploy.equinix.com/developers/api/)
