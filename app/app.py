#!/usr/bin/env python3
"""
AKS Deployment Impact Predictor - Enhanced Web Dashboard
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import subprocess
import json
import os
import time
import threading
from datetime import datetime
import yaml

app = Flask(__name__)
app.config['SECRET_KEY'] = 'aks-predictor-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

class AKSPredictor:
    def __init__(self):
        self.monitoring = False
        
    def run_kubectl_command(self, command):
        """Execute kubectl command and return result"""
        try:
            result = subprocess.run(
                f"kubectl {command}",
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return {"success": True, "output": result.stdout}
            else:
                return {"success": False, "error": result.stderr}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_cluster_capacity(self):
        """Get current cluster capacity and usage"""
        try:
            # Get nodes information
            nodes_result = self.run_kubectl_command("get nodes -o json")
            if not nodes_result["success"]:
                return {"error": "Failed to get nodes info", "details": nodes_result["error"]}
            
            nodes_data = json.loads(nodes_result["output"])
            
            total_cpu = 0
            total_memory_kb = 0
            total_pods = 0
            node_count = 0
            
            for node in nodes_data.get("items", []):
                capacity = node.get("status", {}).get("capacity", {})
                cpu = int(capacity.get("cpu", 0))
                memory_str = capacity.get("memory", "0Ki")
                memory_kb = int(memory_str.replace("Ki", ""))
                pods = int(capacity.get("pods", 0))
                
                total_cpu += cpu
                total_memory_kb += memory_kb
                total_pods += pods
                node_count += 1
            
            # Get running pods count
            pods_result = self.run_kubectl_command("get pods --all-namespaces --field-selector=status.phase=Running --no-headers")
            running_pods = 0
            if pods_result["success"]:
                lines = [line for line in pods_result["output"].strip().split('\n') if line.strip()]
                running_pods = len(lines)
            
            # Try to get real metrics
            metrics_available = False
            current_cpu_usage = 0
            current_memory_usage = 0
            
            cpu_metrics = self.run_kubectl_command("top nodes --no-headers")
            if cpu_metrics["success"] and cpu_metrics["output"].strip():
                metrics_available = True
                for line in cpu_metrics["output"].strip().split('\n'):
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 3:
                            cpu_str = parts[1].replace('m', '')
                            memory_str = parts[2]
                            try:
                                current_cpu_usage += int(cpu_str) if 'm' in parts[1] else int(cpu_str) * 1000
                                if 'Gi' in memory_str:
                                    current_memory_usage += int(memory_str.replace('Gi', '')) * 1024
                                else:
                                    current_memory_usage += int(memory_str.replace('Mi', ''))
                            except:
                                pass
            
            if not metrics_available:
                # Estimate usage
                current_cpu_usage = running_pods * 100  # 100m per pod estimate
                current_memory_usage = running_pods * 128  # 128Mi per pod estimate
            
            total_memory_mb = total_memory_kb // 1024
            
            return {
                "timestamp": datetime.now().isoformat(),
                "node_count": node_count,
                "total_capacity": {
                    "cpu_cores": total_cpu,
                    "memory_mb": total_memory_mb,
                    "max_pods": total_pods
                },
                "current_usage": {
                    "running_pods": running_pods,
                    "cpu_millicores": current_cpu_usage,
                    "memory_mb": current_memory_usage
                },
                "utilization_percentage": {
                    "cpu": round((current_cpu_usage / 1000) / total_cpu * 100, 1) if total_cpu > 0 else 0,
                    "memory": round(current_memory_usage / total_memory_mb * 100, 1) if total_memory_mb > 0 else 0,
                    "pods": round(running_pods / total_pods * 100, 1) if total_pods > 0 else 0
                },
                "metrics_available": metrics_available
            }
            
        except Exception as e:
            return {"error": str(e)}

    def analyze_deployment_yaml(self, yaml_content):
        """Analyze deployment YAML and predict impact"""
        try:
            # Parse YAML
            deployment_data = yaml.safe_load(yaml_content)
            
            if deployment_data.get("kind") != "Deployment":
                return {"error": "Only Deployment resources are supported"}
            
            # Extract deployment info
            replicas = deployment_data.get("spec", {}).get("replicas", 1)
            containers = deployment_data.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            
            total_cpu_per_pod = 0
            total_memory_per_pod = 0
            
            for container in containers:
                resources = container.get("resources", {}).get("requests", {})
                
                # Parse CPU
                cpu_request = resources.get("cpu", "100m")
                if cpu_request.endswith("m"):
                    cpu_millicores = int(cpu_request[:-1])
                else:
                    cpu_millicores = int(float(cpu_request) * 1000)
                
                # Parse Memory
                memory_request = resources.get("memory", "128Mi")
                if memory_request.endswith("Mi"):
                    memory_mb = int(memory_request[:-2])
                elif memory_request.endswith("Gi"):
                    memory_mb = int(memory_request[:-2]) * 1024
                else:
                    memory_mb = 128
                
                total_cpu_per_pod += cpu_millicores
                total_memory_per_pod += memory_mb
            
            # Get current cluster state
            cluster_state = self.get_cluster_capacity()
            if "error" in cluster_state:
                return cluster_state
            
            # Calculate impact
            total_deployment_cpu = total_cpu_per_pod * replicas
            total_deployment_memory = total_memory_per_pod * replicas
            
            # Predict new utilization
            new_cpu_usage = cluster_state["current_usage"]["cpu_millicores"] + total_deployment_cpu
            new_memory_usage = cluster_state["current_usage"]["memory_mb"] + total_deployment_memory
            new_pods = cluster_state["current_usage"]["running_pods"] + replicas
            
            # Calculate new percentages
            new_cpu_percent = round((new_cpu_usage / 1000) / cluster_state["total_capacity"]["cpu_cores"] * 100, 1)
            new_memory_percent = round(new_memory_usage / cluster_state["total_capacity"]["memory_mb"] * 100, 1)
            new_pods_percent = round(new_pods / cluster_state["total_capacity"]["max_pods"] * 100, 1)
            
            # Calculate risk score
            risk_score = 0
            if new_cpu_percent > 80: risk_score += 40
            elif new_cpu_percent > 60: risk_score += 25
            
            if new_memory_percent > 80: risk_score += 40
            elif new_memory_percent > 60: risk_score += 25
            
            if new_pods_percent > 90: risk_score += 20
            elif new_pods_percent > 75: risk_score += 15
            
            # Determine risk level
            if risk_score >= 70:
                risk_level = "HIGH"
                risk_color = "#dc3545"
                risk_icon = "🚨"
            elif risk_score >= 40:
                risk_level = "MEDIUM"
                risk_color = "#ffc107"
                risk_icon = "⚠️"
            else:
                risk_level = "LOW"
                risk_color = "#28a745"
                risk_icon = "✅"
            
            # Generate recommendations
            recommendations = []
            if new_cpu_percent > 80:
                recommendations.append("🔴 HIGH CPU: Consider scaling cluster nodes or reducing CPU requests")
            elif new_cpu_percent > 60:
                recommendations.append("🟡 Monitor CPU usage closely after deployment")
            
            if new_memory_percent > 80:
                recommendations.append("🔴 HIGH MEMORY: Consider adding nodes or reducing memory requests")
            elif new_memory_percent > 60:
                recommendations.append("🟡 Monitor memory usage closely after deployment")
            
            if new_pods_percent > 90:
                recommendations.append("🔴 POD LIMIT: Scale cluster nodes immediately")
            elif new_pods_percent > 80:
                recommendations.append("🟡 Pod capacity approaching limit")
            
            if risk_score >= 70:
                recommendations.extend([
                    "🚨 Deploy during off-peak hours",
                    "🚨 Have rollback plan ready",
                    "🚨 Monitor cluster closely during deployment"
                ])
            elif risk_score >= 40:
                recommendations.extend([
                    "⚠️ Monitor deployment progress carefully",
                    "⚠️ Consider gradual rollout"
                ])
            else:
                recommendations.extend([
                    "✅ Deployment should proceed safely",
                    "✅ Low risk of resource contention"
                ])
            
            return {
                "deployment_info": {
                    "name": deployment_data.get("metadata", {}).get("name", "unknown"),
                    "replicas": replicas,
                    "cpu_per_pod": total_cpu_per_pod,
                    "memory_per_pod": total_memory_per_pod
                },
                "cluster_state": cluster_state,
                "predicted_impact": {
                    "total_cpu_millicores": total_deployment_cpu,
                    "total_memory_mb": total_deployment_memory,
                    "additional_pods": replicas
                },
                "predicted_utilization": {
                    "cpu_percent": new_cpu_percent,
                    "memory_percent": new_memory_percent,
                    "pods_percent": new_pods_percent
                },
                "risk_assessment": {
                    "score": risk_score,
                    "level": risk_level,
                    "color": risk_color,
                    "icon": risk_icon
                },
                "recommendations": recommendations,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}

# Global predictor instance
predictor = AKSPredictor()

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/cluster/status')
def cluster_status():
    """Get current cluster status"""
    try:
        cluster_state = predictor.get_cluster_capacity()
        return jsonify(cluster_state)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/predict', methods=['POST'])
def predict_deployment():
    """Predict deployment impact"""
    try:
        data = request.get_json()
        if not data or 'yaml' not in data:
            return jsonify({"error": "YAML content required"}), 400
        
        yaml_content = data['yaml']
        prediction = predictor.analyze_deployment_yaml(yaml_content)
        
        return jsonify(prediction)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/examples')
def get_examples():
    """Get example deployment YAMLs"""
    examples = {
        "low_risk": {
            "name": "Low Risk - Simple Nginx",
            "yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-low-risk
  labels:
    app: nginx-low
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx-low
  template:
    metadata:
      labels:
        app: nginx-low
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "100m"
"""
        },
        "medium_risk": {
            "name": "Medium Risk - Multi-replica App",
            "yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: app-medium-risk
  labels:
    app: medium-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: medium-app
  template:
    metadata:
      labels:
        app: medium-app
    spec:
      containers:
      - name: web-app
        image: nginx:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "400m"
"""
        },
        "high_risk": {
            "name": "High Risk - Resource Intensive",
            "yaml": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: heavy-app-high-risk
  labels:
    app: heavy-app
spec:
  replicas: 5
  selector:
    matchLabels:
      app: heavy-app
  template:
    metadata:
      labels:
        app: heavy-app
    spec:
      containers:
      - name: heavy-container
        image: nginx:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
"""
        }
    }
    return jsonify(examples)

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting AKS Deployment Impact Predictor...")
    print("Dashboard available at: http://localhost:5000")
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)
