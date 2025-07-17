#!/usr/bin/env python3
"""
AKS Deployment Impact Predictor - Web Dashboard
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
                # Parse real metrics
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

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting AKS Deployment Impact Predictor...")
    print("Dashboard available at: http://localhost:5000")
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)