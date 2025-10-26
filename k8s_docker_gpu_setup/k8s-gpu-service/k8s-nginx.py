import yaml
import json

from kubernetes import client, config
config.load_kube_config(config_file='/home/jincm/.kube/config')
v1 = client.CoreV1Api()
api_instance = client.AppsV1Api()
namespace = 'default'

# with open('ali3.yaml','r',encoding='utf8') as file:#utf8可识别中文
#    fff=yaml.safe_load(file)

deployment_manifest = {
  "apiVersion": "apps/v1",
  "kind": "Deployment",
  "metadata": {
    "name": "nginx1",
    "labels": {
      "app": "nginx1"
    }
  },
  "spec": {
    "replicas": 1,
    "selector": {
      "matchLabels": {
        "app": "nginx1"
      }
    },
    "template": {
      "metadata": {
        "labels": {
          "app": "nginx1"
        }
      },
      "spec": {
        "containers": [
          {
            "name": "nginx1",
            "image": "nginx:latest",
            "ports": [
                {
                    "containerPort": 80
                }
            ]
          },
        ]
      }
    }
  }
}

# 部署Deployment
resp = api_instance.create_namespaced_deployment(body=deployment_manifest, namespace=namespace)
print(resp)


#service

# 创建 Service
service_manifest = {
  "apiVersion": "v1",
  "kind": "Service",
  "metadata": {
    "name": "nginx-service"
  },
  "spec": {
    "type": "NodePort",
    "ports": [
      {
        "port": 80,
        "targetPort": 80,
        "nodePort": 30080
      }
    ],
    "selector": {
      "app": "nginx1"
    }
  }
}

resp = v1.create_namespaced_service(body=service_manifest, namespace=namespace)
print("Service created. status='%s'" % resp)


