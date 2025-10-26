from kubernetes import client, config
from kubernetes.stream import stream
import yaml

# kubeconfig.yaml保存的路径
config_file="/etc/rancher/k3s/k3s.yaml"
#config_file="kubeconfig.yaml"
config.kube_config.load_kube_config(config_file=config_file)
#获取API的CoreV1Api和BatchV1Api版本对象
Api_Instance = client.CoreV1Api()
Api_Batch = client.BatchV1Api()

# 指定命名空间
namespace = 'default'

# 获取 Pod 列表
pod_list = Api_Instance.list_namespaced_pod(namespace)

print(pod_list)
print("aa")
# 遍历 Pod 列表
for pod in pod_list.items:
    print(f'{pod.metadata.namespace}/{pod.metadata.name}')
