#!/usr/bin/env python3
"""
Test suite for provider API integrations

Includes mock responses for testing without actual API calls
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from capsule_package.providers import (
    HivelocityProvider,
    DigitalOceanProvider,
    VultrProvider,
    AWSProvider,
    EquinixMetalProvider,
    ProviderManager,
)
from capsule_package.api_clients import APIError


# Mock API responses
MOCK_RESPONSES = {
    'hivelocity_devices': {
        'devices': [
            {
                'deviceId': '12345',
                'hostname': 'test-server',
                'status': 'active',
                'primaryIp': '203.0.113.1',
                'location': 'atlanta',
                'createdAt': '2024-01-01T00:00:00Z'
            }
        ]
    },
    'digitalocean_droplets': {
        'droplets': [
            {
                'id': 12345,
                'name': 'test-droplet',
                'status': 'active',
                'networks': {
                    'v4': [
                        {'type': 'public', 'ip_address': '167.172.1.1'}
                    ]
                },
                'region': {'slug': 'nyc1'},
                'created_at': '2024-01-01T00:00:00Z'
            }
        ]
    },
    'vultr_instances': {
        'instances': [
            {
                'id': 'abc-123',
                'label': 'test-instance',
                'status': 'active',
                'main_ip': '45.76.1.1',
                'region': 'ewr',
                'date_created': '2024-01-01T00:00:00Z'
            }
        ]
    },
    'equinix_devices': {
        'devices': [
            {
                'id': 'xyz-789',
                'hostname': 'test-metal',
                'state': 'active',
                'ip_addresses': [
                    {
                        'public': True,
                        'address_family': 4,
                        'address': '147.75.1.1'
                    }
                ],
                'metro': {'code': 'da'},
                'created_at': '2024-01-01T00:00:00Z'
            }
        ]
    }
}


class TestHivelocityProvider(unittest.TestCase):
    """Test Hivelocity provider integration"""

    def setUp(self):
        self.provider = HivelocityProvider('hivelocity', 'test_api_key')

    @patch('capsule_package.api_clients.HivelocityAPIClient.get')
    def test_list_instances(self, mock_get):
        """Test listing Hivelocity instances"""
        mock_get.return_value = MOCK_RESPONSES['hivelocity_devices']

        instances = self.provider.list_instances()

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0]['id'], '12345')
        self.assertEqual(instances[0]['name'], 'test-server')
        self.assertEqual(instances[0]['provider'], 'hivelocity')

    @patch('capsule_package.api_clients.HivelocityAPIClient.post')
    def test_deploy_instance(self, mock_post):
        """Test deploying a Hivelocity instance"""
        mock_post.return_value = {
            'deviceId': '99999',
            'status': 'deploying',
            'primaryIp': '203.0.113.100'
        }

        config = {'name': 'new-server', 'region': 'atlanta'}
        result = self.provider.deploy('hive-small', config)

        self.assertEqual(result['id'], '99999')
        self.assertEqual(result['provider'], 'hivelocity')
        self.assertEqual(result['status'], 'deploying')


class TestDigitalOceanProvider(unittest.TestCase):
    """Test DigitalOcean provider integration"""

    def setUp(self):
        self.provider = DigitalOceanProvider('digitalocean', 'test_api_key')

    @patch('capsule_package.api_clients.DigitalOceanAPIClient.get')
    def test_list_instances(self, mock_get):
        """Test listing DigitalOcean droplets"""
        mock_get.return_value = MOCK_RESPONSES['digitalocean_droplets']

        instances = self.provider.list_instances()

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0]['id'], '12345')
        self.assertEqual(instances[0]['name'], 'test-droplet')
        self.assertEqual(instances[0]['provider'], 'digitalocean')
        self.assertEqual(instances[0]['ip_address'], '167.172.1.1')

    @patch('capsule_package.api_clients.DigitalOceanAPIClient.post')
    def test_deploy_droplet(self, mock_post):
        """Test deploying a DigitalOcean droplet"""
        mock_post.return_value = {
            'droplet': {
                'id': 99999,
                'name': 'new-droplet',
                'status': 'new',
                'region': {'slug': 'nyc1'}
            }
        }

        config = {'name': 'new-droplet', 'region': 'nyc1'}
        result = self.provider.deploy('do-basic-1', config)

        self.assertEqual(result['id'], '99999')
        self.assertEqual(result['provider'], 'digitalocean')


class TestVultrProvider(unittest.TestCase):
    """Test Vultr provider integration"""

    def setUp(self):
        self.provider = VultrProvider('vultr', 'test_api_key')

    @patch('capsule_package.api_clients.VultrAPIClient.get')
    def test_list_instances(self, mock_get):
        """Test listing Vultr instances"""
        mock_get.return_value = MOCK_RESPONSES['vultr_instances']

        instances = self.provider.list_instances()

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0]['id'], 'abc-123')
        self.assertEqual(instances[0]['name'], 'test-instance')
        self.assertEqual(instances[0]['provider'], 'vultr')

    @patch('capsule_package.api_clients.VultrAPIClient.post')
    def test_deploy_instance(self, mock_post):
        """Test deploying a Vultr instance"""
        mock_post.return_value = {
            'instance': {
                'id': 'new-123',
                'label': 'new-instance',
                'status': 'pending',
                'region': 'ewr',
                'main_ip': ''
            }
        }

        config = {'name': 'new-instance', 'region': 'ewr'}
        result = self.provider.deploy('vultr-vc2-1', config)

        self.assertEqual(result['id'], 'new-123')
        self.assertEqual(result['provider'], 'vultr')


class TestAWSProvider(unittest.TestCase):
    """Test AWS EC2 provider integration"""

    def setUp(self):
        # Mock boto3 if not available
        if not hasattr(sys.modules, 'boto3'):
            sys.modules['boto3'] = MagicMock()

        self.provider = AWSProvider('aws', 'test_access_key')

    @patch('boto3.client')
    def test_deploy_instance(self, mock_boto_client):
        """Test deploying an AWS EC2 instance"""
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2

        mock_ec2.run_instances.return_value = {
            'Instances': [{
                'InstanceId': 'i-12345',
                'State': {'Name': 'pending'},
                'PublicIpAddress': ''
            }]
        }

        self.provider.ec2_client = mock_ec2

        config = {'name': 'new-instance', 'region': 'us-east-1'}
        result = self.provider.deploy('aws-t3-micro', config)

        self.assertEqual(result['id'], 'i-12345')
        self.assertEqual(result['provider'], 'aws')


class TestEquinixMetalProvider(unittest.TestCase):
    """Test Equinix Metal provider integration"""

    def setUp(self):
        self.provider = EquinixMetalProvider('equinix', 'test_api_key')

    @patch('capsule_package.api_clients.EquinixMetalAPIClient.get')
    def test_list_instances(self, mock_get):
        """Test listing Equinix Metal devices"""
        mock_get.return_value = MOCK_RESPONSES['equinix_devices']

        instances = self.provider.list_instances()

        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0]['id'], 'xyz-789')
        self.assertEqual(instances[0]['name'], 'test-metal')
        self.assertEqual(instances[0]['provider'], 'equinix')


class TestProviderManager(unittest.TestCase):
    """Test Provider Manager"""

    def setUp(self):
        self.manager = ProviderManager()

    def test_list_providers(self):
        """Test listing all providers"""
        providers = self.manager.list_providers()

        self.assertIn('hivelocity', providers)
        self.assertIn('digitalocean', providers)
        self.assertIn('vultr', providers)
        self.assertIn('aws', providers)
        self.assertIn('equinix', providers)

    def test_get_provider(self):
        """Test getting a specific provider"""
        provider = self.manager.get_provider('hivelocity')

        self.assertIsNotNone(provider)
        self.assertIsInstance(provider, HivelocityProvider)

    def test_get_cheapest_option(self):
        """Test finding cheapest option"""
        cheapest = self.manager.get_cheapest_option(min_cpu=1, min_memory=1)

        self.assertIsNotNone(cheapest)
        self.assertGreater(cheapest.cpu, 0)

    def test_compare_templates(self):
        """Test comparing templates across providers"""
        templates = self.manager.compare_templates(min_cpu=4, min_memory=8, max_price=0.10)

        for template in templates:
            self.assertGreaterEqual(template.cpu, 4)
            self.assertGreaterEqual(template.memory_gb, 8)
            self.assertLessEqual(template.price_hourly, 0.10)


class TestAPIErrorHandling(unittest.TestCase):
    """Test API error handling"""

    def setUp(self):
        self.provider = HivelocityProvider('hivelocity', 'test_api_key')

    @patch('capsule_package.api_clients.HivelocityAPIClient.get')
    def test_api_error_handling(self, mock_get):
        """Test handling of API errors"""
        mock_get.side_effect = APIError("Connection failed", status_code=500)

        instances = self.provider.list_instances()

        # Should return empty list on error, not raise exception
        self.assertEqual(instances, [])


if __name__ == '__main__':
    unittest.main()
