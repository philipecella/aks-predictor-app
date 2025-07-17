# 🔮 AKS Deployment Impact Predictor

A real-time web dashboard that predicts Kubernetes deployment impact before it happens.

## Features

- 📊 **Real-time cluster monitoring** with beautiful charts
- 🎯 **Deployment impact prediction** with risk assessment
- ⚠️ **Risk scoring** (LOW/MEDIUM/HIGH) with specific recommendations
- 🚨 **Proactive alerts** for resource contention
- 📈 **Historical tracking** and trends

## Architecture

- **Frontend**: Modern HTML5 dashboard with Chart.js
- **Backend**: Python Flask API with real-time data
- **Infrastructure**: Azure Kubernetes Service (AKS) + Azure Container Registry (ACR)
- **CI/CD**: GitHub Actions for automated deployment

## Quick Start

### Prerequisites
- Azure subscription with AKS cluster
- Azure Container Registry
- GitHub repository with Azure credentials

### Deployment

1. **Fork this repository**
2. **Set up GitHub secrets** in your repository's Environment "Prod":
   - `CLIENT_ID`
   - `CLIENT_SECRET` 
   - `TENANT_ID`
   - `SUBSCRIPTION_ID`

3. **Update configuration** in `.github/workflows/deploy.yml`:
   - Change `ACR_NAME` to your ACR name
   - Update `RESOURCE_GROUP` and `AKS_CLUSTER` names

4. **Push to main branch** - GitHub Actions will automatically:
   - Build Docker image
   - Push to ACR
   - Deploy to AKS
   - Run health checks

### Usage

1. **Access the dashboard** at your AKS LoadBalancer IP
2. **Monitor cluster** status and resource utilization
3. **Test deployment impact**:
   - Paste Kubernetes YAML
   - Click "Predict Impact"
   - Review risk assessment and recommendations

## Demo Scenarios

- **Low Risk**: Single nginx pod (50m CPU, 64Mi RAM)
- **Medium Risk**: 3-replica application (200m CPU, 256Mi RAM each)
- **High Risk**: 5-replica resource-intensive app (500m CPU, 1Gi RAM each)

## API Endpoints

- `GET /` - Main dashboard
- `GET /api/cluster/status` - Cluster capacity and usage
- `POST /api/predict` - Deployment impact prediction
- `GET /api/examples` - Example deployment YAMLs
- `GET /health` - Health check

## Contributing

1. Fork the repository
2. Create feature branch
3. Submit pull request

## License

MIT License