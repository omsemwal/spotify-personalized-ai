# ☸️ Kubernetes Deployment Guide & Tasks

**Folder**: `infrastructure/kubernetes/`  
**Purpose**: Production Kubernetes deployment manifests, secrets, and Helm charts for deploying the system on cloud clusters (AWS EKS, GCP GKE, Azure AKS, or local Minikube).

---

## 📋 What We Do Inside
1. **Manifests (`/manifests`)**:
   - `Deployment`, `Service`, `ConfigMap`, `Secret`, and `HorizontalPodAutoscaler` YAML definitions for each microservice.
2. **Helm Charts (`/helm`)**:
   - Helm chart packaging for single-command system installation and environment configuration (`values-dev.yaml`, `values-prod.yaml`).
