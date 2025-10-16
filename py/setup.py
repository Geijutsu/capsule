from setuptools import setup, find_packages

setup(
    name="capsule",
    version="0.1.0",
    description="User-friendly server configuration tool using Nix with named profiles and remote deployment",
    packages=["capsule_package"],
    install_requires=[
        "click>=8.0.0",
        "pyyaml>=5.1",
        "requests>=2.25.0",
        "boto3>=1.18.0",  # Optional, for AWS EC2 support
    ],
    entry_points={
        "console_scripts": [
            "capsule=capsule_package:cli",
        ],
    },
    include_package_data=True,
    package_data={
        'capsule_package': ['presets/*.nix', 'sprouts/*.nix', 'profiles/*.nix'],
    },
    python_requires=">=3.7",
)
