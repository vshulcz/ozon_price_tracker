# Documentation

> [🇷🇺 Русская версия](./README.md)

## Deployment Guides

- [Production deployment with K3s and ArgoCD](./DEPLOYMENT-en.md)

## Overview

This documentation covers the complete setup process for deploying the Ozon Price Tracker bot using Kubernetes (K3s) and GitOps practices with ArgoCD.

### What's Covered

- K3s installation and configuration
- ArgoCD setup for GitOps continuous delivery
- Secret management (manual, outside Git)
- Production and development environments
- Database backup and restoration
- Monitoring and troubleshooting
- CI/CD integration with GitHub Actions

### Architecture

The project uses a GitOps approach where:
- All Kubernetes manifests are stored in the `k8s/` directory
- ArgoCD monitors the `main` branch for changes
- Changes are automatically synced to the cluster
- Pull requests are automatically deployed to the dev environment for testing

### Requirements

- Fresh Ubuntu/Debian server (4GB+ RAM, 20GB+ disk)
- Root/sudo access
- Basic knowledge of Kubernetes and Docker
- GitHub repository with CI/CD workflows configured
