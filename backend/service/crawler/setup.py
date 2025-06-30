#!/usr/bin/env python3
"""
NEFAC Document Crawler Setup Script

This script sets up the complete NEFAC document crawler environment.
"""

import subprocess
import sys
from pathlib import Path


def install_requirements():
    """Install all required dependencies from the central requirements.txt file."""
    print("Installing all Python dependencies from central requirements.txt...")

    requirements_file = Path("requirements.txt")
    if requirements_file.exists():
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_file)])
        print("\n✅ Dependencies installed successfully!")
    else:
        print("❌ ERROR: requirements.txt not found. Cannot install dependencies.")
        sys.exit(1)

    print("\n📝 Note: The crawler includes Selenium-based scraping which requires Chrome/Chromium.")
    print("   If you don't have Chrome installed, the webdriver-manager will attempt to download it automatically.")
    print("   For headless environments, you may need to install Chrome/Chromium manually.")


def create_env_file():
    """Create .env file if it doesn't exist."""
    env_file = Path(".env")
    if not env_file.exists():
        print("Creating .env file...")
        with open(env_file, "w") as f:
            f.write("# NEFAC Document Crawler Configuration\n")
            f.write("# Copy this file and add your actual values\n\n")
            f.write("# Faust Secret Key for authenticated GraphQL access\n")
            f.write("# This enables enhanced content extraction and access to private content\n")
            f.write("FAUST_SECRET_KEY=your_faust_secret_key_here\n\n")
            f.write("# Webshare.io Residential Proxy Credentials (for YouTube crawling)\n")
            f.write("# See: https://www.webshare.io/\n")
            f.write("WEBSHARE_USERNAME=your_webshare_username\n")
            f.write("WEBSHARE_PASSWORD=your_webshare_password\n")
        print("Created .env file. Please edit it with your Faust secret key and optional Webshare credentials.")


def main():
    """Main setup function."""
    print("Setting up NEFAC Document Crawler...")

    try:
        install_requirements()
        create_env_file()
        print("\n✅ Setup completed successfully!")
        print("\nNext steps:")
        print("1. Edit .env file with your Faust secret key")
        print("2. Run: python nefac-document-crawler.py")
        print("3. Check the nefac_documents/ directory for results")

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
