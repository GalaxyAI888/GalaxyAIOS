import logging
import yaml
from typing import Dict, List, Optional, Tuple, Any
from kubernetes import client, utils
from kubernetes.client.rest import ApiException
from .k8s_client import KubernetesClient

logger = logging.getLogger(__name__)


class KubernetesDeploymentManager:
    """Kubernetes Deployment管理类"""
    
    def __init__(self, k8s_client: KubernetesClient):
        self.k8s_client = k8s_client
        self.apps_v1 = k8s_client.apps_v1
        self.core_v1 = k8s_client.core_v1
    
    def create_deployment_from_yaml(self, namespace: str, yaml_source: str, 
                                   custom_labels: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        """
        从YAML创建Deployment
        
        Args:
            namespace: 命名空间
            yaml_source: YAML文件源（URL或本地路径）
            custom_labels: 自定义标签
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 加载YAML
            success, message, yaml_data = self.k8s_client.load_yaml(yaml_source)
            logger.info(f"Deployment YAML加载结果: success={success}, message={message}")
            if not success:
                return False, message
            
            # 确保是Deployment资源
            if yaml_data.get('kind') != 'Deployment':
                return False, f"YAML文件不是Deployment类型，当前类型: {yaml_data.get('kind')}"
            
            # 设置命名空间
            yaml_data['metadata']['namespace'] = namespace
            
            # 添加自定义标签（避免覆盖 YAML 的 app/selector 标签）
            if custom_labels:
                # 过滤掉 app 键，防止与 Service selector 冲突
                safe_labels = {k: v for k, v in custom_labels.items() if k != 'app'}
                if safe_labels:
                    if 'labels' not in yaml_data['metadata']:
                        yaml_data['metadata']['labels'] = {}
                    yaml_data['metadata']['labels'].update(safe_labels)
                    # 仅追加到 Pod 模板标签，不触碰 spec.selector.matchLabels
                    if 'template' in yaml_data['spec']:
                        if 'metadata' not in yaml_data['spec']['template']:
                            yaml_data['spec']['template']['metadata'] = {}
                        if 'labels' not in yaml_data['spec']['template']['metadata']:
                            yaml_data['spec']['template']['metadata']['labels'] = {}
                        yaml_data['spec']['template']['metadata']['labels'].update(safe_labels)
            
            # 使用官方方法：直接应用YAML
            logger.info(f"使用官方方法应用YAML到命名空间: {namespace}")
            utils.create_from_dict(
                self.k8s_client.apps_v1.api_client,
                yaml_data,
                namespace=namespace,
                verbose=True
            )
            
            logger.info(f"Deployment创建成功: {yaml_data['metadata']['name']} in {namespace}")
            return True, f"Deployment {yaml_data['metadata']['name']} 创建成功"
            
        except ApiException as e:
            error_msg = f"创建Deployment失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"创建Deployment失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def create_deployment_from_json(self, namespace: str, deployment_config: Dict[str, Any], 
                                   custom_labels: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        """
        从JSON配置创建Deployment
        
        Args:
            namespace: 命名空间
            deployment_config: Deployment配置字典
            custom_labels: 自定义标签
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 确保是Deployment资源
            if deployment_config.get('kind') != 'Deployment':
                return False, f"配置不是Deployment类型，当前类型: {deployment_config.get('kind')}"
            
            # 设置命名空间 - 确保覆盖任何现有的命名空间
            if 'metadata' not in deployment_config:
                deployment_config['metadata'] = {}
            
            # 记录原始命名空间（如果存在）
            original_namespace = deployment_config['metadata'].get('namespace', 'None')
            if original_namespace != namespace:
                logger.info(f"Deployment命名空间将被覆盖: {original_namespace} -> {namespace}")
            
            # 强制设置命名空间
            deployment_config['metadata']['namespace'] = namespace
            
            # 添加自定义标签（避免覆盖 YAML 的 app/selector 标签）
            if custom_labels:
                # 过滤掉 app 键，防止与 Service selector 冲突
                safe_labels = {k: v for k, v in custom_labels.items() if k != 'app'}
                if safe_labels:
                    if 'labels' not in deployment_config['metadata']:
                        deployment_config['metadata']['labels'] = {}
                    deployment_config['metadata']['labels'].update(safe_labels)
                    # 仅追加到 Pod 模板标签，不触碰 spec.selector.matchLabels
                    if 'spec' in deployment_config and 'template' in deployment_config['spec']:
                        if 'metadata' not in deployment_config['spec']['template']:
                            deployment_config['spec']['template']['metadata'] = {}
                        if 'labels' not in deployment_config['spec']['template']['metadata']:
                            deployment_config['spec']['template']['metadata']['labels'] = {}
                        deployment_config['spec']['template']['metadata']['labels'].update(safe_labels)
            
            # 使用官方方法：直接应用JSON配置
            logger.info(f"使用官方方法应用JSON配置到命名空间: {namespace}")
            utils.create_from_dict(
                self.k8s_client.apps_v1.api_client,
                deployment_config,
                namespace=namespace,
                verbose=True
            )
            
            logger.info(f"Deployment创建成功: {deployment_config['metadata']['name']} in {namespace}")
            return True, f"Deployment {deployment_config['metadata']['name']} 创建成功"
            
        except ApiException as e:
            error_msg = f"创建Deployment失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"创建Deployment失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def update_deployment_from_yaml(self, namespace: str, deployment_name: str, 
                                   yaml_source: str) -> Tuple[bool, str]:
        """
        从YAML更新Deployment
        
        Args:
            namespace: 命名空间
            deployment_name: Deployment名称
            yaml_source: YAML文件源（URL或本地路径）
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 加载YAML
            success, message, yaml_data = self.k8s_client.load_yaml(yaml_source)
            if not success:
                return False, message
            
            # 设置命名空间和名称
            yaml_data['metadata']['namespace'] = namespace
            yaml_data['metadata']['name'] = deployment_name
            
            # 创建Deployment对象
            deployment = client.V1Deployment()
            self._dict_to_deployment(yaml_data, deployment)
            
            # 更新Deployment
            result = self.apps_v1.replace_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=deployment
            )
            
            logger.info(f"Deployment更新成功: {result.metadata.name} in {namespace}")
            return True, f"Deployment {result.metadata.name} 更新成功"
            
        except ApiException as e:
            error_msg = f"更新Deployment失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"更新Deployment失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_deployment(self, namespace: str, deployment_name: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        获取Deployment信息
        
        Args:
            namespace: 命名空间
            deployment_name: Deployment名称（可能是应用名称，会通过标签查找实际Deployment）
            
        Returns:
            (成功标志, 消息, Deployment信息)
        """
        try:
            # 首先尝试直接使用deployment_name
            try:
                deployment = self.apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=namespace
                )
            except ApiException as e:
                if e.status == 404:  # Deployment not found
                    logger.info(f"Deployment {deployment_name} 不存在，尝试通过标签查找")
                    
                    # 通过标签查找Deployment
                    label_selector = f"app={deployment_name}"
                    deployments = self.apps_v1.list_namespaced_deployment(
                        namespace=namespace,
                        label_selector=label_selector
                    )
                    
                    if deployments.items:
                        actual_deployment_name = deployments.items[0].metadata.name
                        logger.info(f"找到Deployment: {actual_deployment_name} (标签: {label_selector})")
                        
                        # 使用实际的Deployment名称获取信息
                        deployment = self.apps_v1.read_namespaced_deployment(
                            name=actual_deployment_name,
                            namespace=namespace
                        )
                    else:
                        return False, f"未找到标签为 app={deployment_name} 的Deployment", None
                else:
                    raise e
            
            deployment_info = {
                'name': deployment.metadata.name,
                'namespace': deployment.metadata.namespace,
                'labels': deployment.metadata.labels or {},
                'replicas': deployment.spec.replicas,
                'ready_replicas': deployment.status.ready_replicas or 0,
                'available_replicas': deployment.status.available_replicas or 0,
                'creation_timestamp': deployment.metadata.creation_timestamp,
                'status': 'Running' if deployment.status.ready_replicas == deployment.spec.replicas else 'Not Ready'
            }
            
            return True, "获取Deployment信息成功", deployment_info
            
        except ApiException as e:
            if e.status == 404:
                return False, f"Deployment {deployment_name} 不存在", None
            error_msg = f"获取Deployment失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"获取Deployment失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def delete_deployment(self, namespace: str, deployment_name: str) -> Tuple[bool, str]:
        """
        删除Deployment
        
        Args:
            namespace: 命名空间
            deployment_name: Deployment名称（可能是应用名称，会通过标签查找实际Deployment）
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 首先尝试直接使用deployment_name
            try:
                self.apps_v1.delete_namespaced_deployment(
                    name=deployment_name,
                    namespace=namespace
                )
                
                logger.info(f"Deployment删除成功: {deployment_name} in {namespace}")
                return True, f"Deployment {deployment_name} 删除成功"
                
            except ApiException as e:
                if e.status == 404:  # Deployment not found
                    logger.info(f"Deployment {deployment_name} 不存在，尝试通过标签查找")
                    
                    # 通过标签查找Deployment
                    label_selector = f"app={deployment_name}"
                    deployments = self.apps_v1.list_namespaced_deployment(
                        namespace=namespace,
                        label_selector=label_selector
                    )
                    
                    if deployments.items:
                        actual_deployment_name = deployments.items[0].metadata.name
                        logger.info(f"找到Deployment: {actual_deployment_name} (标签: {label_selector})")
                        
                        # 使用实际的Deployment名称进行删除
                        self.apps_v1.delete_namespaced_deployment(
                            name=actual_deployment_name,
                            namespace=namespace
                        )
                        
                        logger.info(f"Deployment删除成功: {actual_deployment_name} in {namespace}")
                        return True, f"Deployment {actual_deployment_name} 删除成功"
                    else:
                        return True, f"未找到标签为 app={deployment_name} 的Deployment，无需删除"
                else:
                    raise e
            
        except ApiException as e:
            if e.status == 404:
                return True, f"Deployment {deployment_name} 不存在，无需删除"
            error_msg = f"删除Deployment失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"删除Deployment失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def scale_deployment(self, namespace: str, deployment_name: str, replicas: int) -> Tuple[bool, str]:
        """
        扩缩容Deployment
        
        Args:
            namespace: 命名空间
            deployment_name: Deployment名称（可能是应用名称，会通过标签查找实际Deployment）
            replicas: 副本数
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 首先尝试直接使用deployment_name
            try:
                # 创建Scale对象
                scale = client.V1Scale(
                    metadata=client.V1ObjectMeta(
                        name=deployment_name,
                        namespace=namespace
                    ),
                    spec=client.V1ScaleSpec(replicas=replicas)
                )
                
                self.apps_v1.patch_namespaced_deployment_scale(
                    name=deployment_name,
                    namespace=namespace,
                    body=scale
                )
                
                logger.info(f"Deployment扩缩容成功: {deployment_name} -> {replicas} replicas")
                return True, f"Deployment {deployment_name} 扩缩容到 {replicas} 个副本"
                
            except ApiException as e:
                if e.status == 404:  # Deployment not found
                    logger.info(f"Deployment {deployment_name} 不存在，尝试通过标签查找")
                    
                    # 通过标签查找Deployment
                    label_selector = f"app={deployment_name}"
                    deployments = self.apps_v1.list_namespaced_deployment(
                        namespace=namespace,
                        label_selector=label_selector
                    )
                    
                    if deployments.items:
                        actual_deployment_name = deployments.items[0].metadata.name
                        logger.info(f"找到Deployment: {actual_deployment_name} (标签: {label_selector})")
                        
                        # 使用实际的Deployment名称进行扩缩容
                        scale = client.V1Scale(
                            metadata=client.V1ObjectMeta(
                                name=actual_deployment_name,
                                namespace=namespace
                            ),
                            spec=client.V1ScaleSpec(replicas=replicas)
                        )
                        
                        self.apps_v1.patch_namespaced_deployment_scale(
                            name=actual_deployment_name,
                            namespace=namespace,
                            body=scale
                        )
                        
                        logger.info(f"Deployment扩缩容成功: {actual_deployment_name} -> {replicas} replicas")
                        return True, f"Deployment {actual_deployment_name} 扩缩容到 {replicas} 个副本"
                    else:
                        return False, f"未找到标签为 app={deployment_name} 的Deployment"
                else:
                    raise e
            
        except ApiException as e:
            error_msg = f"扩缩容Deployment失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"扩缩容Deployment失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def list_deployments(self, namespace: str, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出命名空间中的Deployments
        
        Args:
            namespace: 命名空间
            label_selector: 标签选择器
            
        Returns:
            Deployment列表
        """
        try:
            deployments = self.apps_v1.list_namespaced_deployment(
                namespace=namespace,
                label_selector=label_selector
            )
            
            deployment_list = []
            for deployment in deployments.items:
                deployment_info = {
                    'name': deployment.metadata.name,
                    'namespace': deployment.metadata.namespace,
                    'labels': deployment.metadata.labels or {},
                    'replicas': deployment.spec.replicas,
                    'ready_replicas': deployment.status.ready_replicas or 0,
                    'available_replicas': deployment.status.available_replicas or 0,
                    'creation_timestamp': deployment.metadata.creation_timestamp,
                    'status': 'Running' if deployment.status.ready_replicas == deployment.spec.replicas else 'Not Ready'
                }
                deployment_list.append(deployment_info)
            
            return deployment_list
            
        except Exception as e:
            logger.error(f"列出Deployments失败: {e}")
            return []
    
    def _dict_to_deployment(self, yaml_data: Dict, deployment: client.V1Deployment) -> None:
        """
        将字典数据转换为V1Deployment对象
        
        Args:
            yaml_data: YAML字典数据
            deployment: V1Deployment对象
        """
        logger.info(f"_dict_to_deployment: 输入spec={yaml_data.get('spec')}")
        # 设置metadata
        if 'metadata' in yaml_data:
            metadata = client.V1ObjectMeta()
            if 'name' in yaml_data['metadata']:
                metadata.name = yaml_data['metadata']['name']
            if 'namespace' in yaml_data['metadata']:
                metadata.namespace = yaml_data['metadata']['namespace']
            if 'labels' in yaml_data['metadata']:
                metadata.labels = yaml_data['metadata']['labels']
            if 'annotations' in yaml_data['metadata']:
                metadata.annotations = yaml_data['metadata']['annotations']
            deployment.metadata = metadata
        
        # 设置spec
        if 'spec' in yaml_data:
            spec = client.V1DeploymentSpec()
            if 'replicas' in yaml_data['spec']:
                spec.replicas = yaml_data['spec']['replicas']
            if 'selector' in yaml_data['spec']:
                selector = client.V1LabelSelector()
                if 'matchLabels' in yaml_data['spec']['selector']:
                    selector.match_labels = yaml_data['spec']['selector']['matchLabels']
                spec.selector = selector
            logger.info(f"_dict_to_deployment: 初步selector={getattr(spec, 'selector', None)}")
            if 'template' in yaml_data['spec']:
                template = client.V1PodTemplateSpec()
                # 设置pod模板metadata
                if 'metadata' in yaml_data['spec']['template']:
                    pod_metadata = client.V1ObjectMeta()
                    if 'labels' in yaml_data['spec']['template']['metadata']:
                        pod_metadata.labels = yaml_data['spec']['template']['metadata']['labels']
                    if 'annotations' in yaml_data['spec']['template']['metadata']:
                        pod_metadata.annotations = yaml_data['spec']['template']['metadata']['annotations']
                    template.metadata = pod_metadata
                # 设置pod模板spec
                if 'spec' in yaml_data['spec']['template']:
                    pod_spec = self._dict_to_pod_spec(yaml_data['spec']['template']['spec'])
                    template.spec = pod_spec
                spec.template = template
            # 兜底：如果 selector 为空，尝试使用 template.metadata.labels
            if spec.selector is None or getattr(spec.selector, 'match_labels', None) in (None, {}):
                template_labels = None
                try:
                    template_labels = spec.template.metadata.labels if spec.template and spec.template.metadata else None
                except Exception:
                    template_labels = None
                if template_labels:
                    logger.info(f"_dict_to_deployment: 兜底使用 template.labels 作为 selector: {template_labels}")
                    selector = client.V1LabelSelector(match_labels=template_labels)
                    spec.selector = selector
            # 再次记录 selector
            logger.info(f"_dict_to_deployment: 最终selector={getattr(spec, 'selector', None)}")
            deployment.spec = spec
    
    def _dict_to_pod_spec(self, pod_spec_data: Dict) -> client.V1PodSpec:
        """
        将字典数据转换为V1PodSpec对象
        
        Args:
            pod_spec_data: Pod spec字典数据
            
        Returns:
            V1PodSpec对象
        """
        pod_spec = client.V1PodSpec()
        
        if 'containers' in pod_spec_data:
            containers = []
            for container_data in pod_spec_data['containers']:
                container = client.V1Container()
                if 'name' in container_data:
                    container.name = container_data['name']
                if 'image' in container_data:
                    container.image = container_data['image']
                if 'ports' in container_data:
                    ports = []
                    for port_data in container_data['ports']:
                        port = client.V1ContainerPort()
                        if 'containerPort' in port_data:
                            port.container_port = port_data['containerPort']
                        if 'protocol' in port_data:
                            port.protocol = port_data['protocol']
                        ports.append(port)
                    container.ports = ports
                if 'env' in container_data:
                    env_vars = []
                    for env_data in container_data['env']:
                        env_var = client.V1EnvVar()
                        if 'name' in env_data:
                            env_var.name = env_data['name']
                        if 'value' in env_data:
                            env_var.value = env_data['value']
                        env_vars.append(env_var)
                    container.env = env_vars
                if 'volumeMounts' in container_data:
                    volume_mounts = []
                    for vm_data in container_data['volumeMounts']:
                        vm = client.V1VolumeMount()
                        if 'name' in vm_data:
                            vm.name = vm_data['name']
                        if 'mountPath' in vm_data:
                            vm.mount_path = vm_data['mountPath']
                        if 'readOnly' in vm_data:
                            vm.read_only = vm_data['readOnly']
                        volume_mounts.append(vm)
                    container.volume_mounts = volume_mounts
                if 'resources' in container_data:
                    resources = client.V1ResourceRequirements()
                    if 'limits' in container_data['resources']:
                        resources.limits = container_data['resources']['limits']
                    if 'requests' in container_data['resources']:
                        resources.requests = container_data['resources']['requests']
                    container.resources = resources
                containers.append(container)
            pod_spec.containers = containers
        
        if 'volumes' in pod_spec_data:
            volumes = []
            for volume_data in pod_spec_data['volumes']:
                volume = client.V1Volume()
                if 'name' in volume_data:
                    volume.name = volume_data['name']
                if 'hostPath' in volume_data:
                    host_path = client.V1HostPathVolumeSource()
                    if 'path' in volume_data['hostPath']:
                        host_path.path = volume_data['hostPath']['path']
                    volume.host_path = host_path
                if 'persistentVolumeClaim' in volume_data:
                    pvc = client.V1PersistentVolumeClaimVolumeSource()
                    if 'claimName' in volume_data['persistentVolumeClaim']:
                        pvc.claim_name = volume_data['persistentVolumeClaim']['claimName']
                    volume.persistent_volume_claim = pvc
                volumes.append(volume)
            pod_spec.volumes = volumes
        
        # 支持所有其他 pod spec 字段
        # 注意：_dict_to_pod_spec 主要用于 update 操作，create 操作直接使用 create_from_dict
        # 通过 Python 的 setattr 动态设置所有未处理字段，以支持 Kubernetes 的所有特性
        for key, value in pod_spec_data.items():
            if key not in ['containers', 'volumes']:
                if hasattr(pod_spec, key):
                    try:
                        setattr(pod_spec, key, value)
                    except Exception as e:
                        logger.warning(f"无法设置 pod_spec.{key}: {e}")
        
        return pod_spec

