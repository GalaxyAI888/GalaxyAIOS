import logging
import yaml
from typing import Dict, List, Optional, Tuple, Any
from kubernetes import client, utils
from kubernetes.client.rest import ApiException
from .k8s_client import KubernetesClient

logger = logging.getLogger(__name__)


class KubernetesServiceManager:
    """Kubernetes Service管理类"""
    
    def __init__(self, k8s_client: KubernetesClient):
        self.k8s_client = k8s_client
        self.core_v1 = k8s_client.core_v1
    
    def create_service_from_json(self, namespace: str, service_config: Dict[str, Any], 
                                custom_labels: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        """
        从JSON配置创建Service
        
        Args:
            namespace: 命名空间
            service_config: Service配置字典
            custom_labels: 自定义标签
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 确保是Service资源
            if service_config.get('kind') != 'Service':
                return False, f"配置不是Service类型，当前类型: {service_config.get('kind')}"
            
            # 设置命名空间 - 确保覆盖任何现有的命名空间
            if 'metadata' not in service_config:
                service_config['metadata'] = {}
            
            # 记录原始命名空间（如果存在）
            original_namespace = service_config['metadata'].get('namespace', 'None')
            if original_namespace != namespace:
                logger.info(f"Service命名空间将被覆盖: {original_namespace} -> {namespace}")
            
            # 强制设置命名空间
            service_config['metadata']['namespace'] = namespace
            
            # 添加自定义标签
            if custom_labels:
                if 'labels' not in service_config['metadata']:
                    service_config['metadata']['labels'] = {}
                service_config['metadata']['labels'].update(custom_labels)
            
            # 自动添加app标签：从service的selector中获取app标签
            if 'labels' not in service_config['metadata']:
                service_config['metadata']['labels'] = {}
            if 'spec' in service_config and 'selector' in service_config['spec']:
                selector = service_config['spec']['selector']
                if 'app' in selector:
                    # 如果selector中有app标签，也将其添加到metadata的labels中
                    service_config['metadata']['labels']['app'] = selector['app']
            
            # 使用官方方法：直接应用JSON配置
            logger.info(f"使用官方方法应用Service JSON配置到命名空间: {namespace}")
            utils.create_from_dict(
                self.k8s_client.core_v1.api_client,
                service_config,
                namespace=namespace,
                verbose=True
            )
            
            logger.info(f"Service创建成功: {service_config['metadata']['name']} in {namespace}")
            return True, f"Service {service_config['metadata']['name']} 创建成功"
            
        except ApiException as e:
            error_msg = f"创建Service失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"创建Service失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def create_service_from_yaml(self, namespace: str, yaml_source: str, 
                                custom_labels: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        """
        从YAML创建Service
        
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
            logger.info(f"Service YAML加载结果: success={success}, message={message}")
            if not success:
                return False, message
            
            # 确保是Service资源
            if yaml_data.get('kind') != 'Service':
                return False, f"YAML文件不是Service类型，当前类型: {yaml_data.get('kind')}"
            
            # 设置命名空间
            yaml_data['metadata']['namespace'] = namespace
            
            # 添加自定义标签
            if custom_labels:
                if 'labels' not in yaml_data['metadata']:
                    yaml_data['metadata']['labels'] = {}
                yaml_data['metadata']['labels'].update(custom_labels)
            
            # 自动添加app标签：从service的selector中获取app标签
            if 'labels' not in yaml_data['metadata']:
                yaml_data['metadata']['labels'] = {}
            if 'spec' in yaml_data and 'selector' in yaml_data['spec']:
                selector = yaml_data['spec']['selector']
                if 'app' in selector:
                    # 如果selector中有app标签，也将其添加到metadata的labels中
                    yaml_data['metadata']['labels']['app'] = selector['app']
            
            # 使用官方方法：直接应用YAML
            logger.info(f"使用官方方法应用Service YAML到命名空间: {namespace}")
            utils.create_from_dict(
                self.k8s_client.core_v1.api_client,
                yaml_data,
                namespace=namespace,
                verbose=True
            )
            
            logger.info(f"Service创建成功: {yaml_data['metadata']['name']} in {namespace}")
            return True, f"Service {yaml_data['metadata']['name']} 创建成功"
            
        except ApiException as e:
            error_msg = f"创建Service失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"创建Service失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_service(self, namespace: str, service_name: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        获取Service信息
        
        Args:
            namespace: 命名空间
            service_name: Service名称（可能是应用名称，会通过标签查找实际Service）
            
        Returns:
            (成功标志, 消息, Service信息)
        """
        try:
            # 首先尝试直接使用service_name
            try:
                service = self.core_v1.read_namespaced_service(
                    name=service_name,
                    namespace=namespace
                )
            except ApiException as e:
                if e.status == 404:  # Service not found
                    logger.info(f"Service {service_name} 不存在，尝试通过标签查找")
                    
                    # 通过标签查找Service
                    label_selector = f"app={service_name}"
                    services = self.core_v1.list_namespaced_service(
                        namespace=namespace,
                        label_selector=label_selector
                    )
                    
                    if services.items:
                        actual_service_name = services.items[0].metadata.name
                        logger.info(f"找到Service: {actual_service_name} (标签: {label_selector})")
                        
                        # 使用实际的Service名称获取信息
                        service = self.core_v1.read_namespaced_service(
                            name=actual_service_name,
                            namespace=namespace
                        )
                    else:
                        return False, f"未找到标签为 app={service_name} 的Service", None
                else:
                    raise e
            
            # 提取端口信息
            ports_info = []
            if service.spec.ports:
                for port in service.spec.ports:
                    port_info = {
                        'name': port.name,
                        'port': port.port,
                        'target_port': port.target_port,
                        'protocol': port.protocol,
                        'node_port': port.node_port
                    }
                    ports_info.append(port_info)
            
            service_info = {
                'name': service.metadata.name,
                'namespace': service.metadata.namespace,
                'labels': service.metadata.labels or {},
                'type': service.spec.type,
                'cluster_ip': service.spec.cluster_ip,
                'external_ips': service.spec.external_i_ps or [],
                'ports': ports_info,
                'selector': service.spec.selector or {},
                'creation_timestamp': service.metadata.creation_timestamp
            }
            
            return True, "获取Service信息成功", service_info
            
        except ApiException as e:
            if e.status == 404:
                return False, f"Service {service_name} 不存在", None
            error_msg = f"获取Service失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"获取Service失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def delete_service(self, namespace: str, service_name: str) -> Tuple[bool, str]:
        """
        删除Service
        
        Args:
            namespace: 命名空间
            service_name: Service名称（可能是应用名称，会通过标签查找实际Service）
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 首先尝试直接使用service_name
            try:
                self.core_v1.delete_namespaced_service(
                    name=service_name,
                    namespace=namespace
                )
                
                logger.info(f"Service删除成功: {service_name} in {namespace}")
                return True, f"Service {service_name} 删除成功"
                
            except ApiException as e:
                if e.status == 404:  # Service not found
                    logger.info(f"Service {service_name} 不存在，尝试通过标签查找")
                    
                    # 通过标签查找Service
                    label_selector = f"app={service_name}"
                    services = self.core_v1.list_namespaced_service(
                        namespace=namespace,
                        label_selector=label_selector
                    )
                    
                    if services.items:
                        actual_service_name = services.items[0].metadata.name
                        logger.info(f"找到Service: {actual_service_name} (标签: {label_selector})")
                        
                        # 使用实际的Service名称进行删除
                        self.core_v1.delete_namespaced_service(
                            name=actual_service_name,
                            namespace=namespace
                        )
                        
                        logger.info(f"Service删除成功: {actual_service_name} in {namespace}")
                        return True, f"Service {actual_service_name} 删除成功"
                    else:
                        return True, f"未找到标签为 app={service_name} 的Service，无需删除"
                else:
                    raise e
            
        except ApiException as e:
            if e.status == 404:
                return True, f"Service {service_name} 不存在，无需删除"
            error_msg = f"删除Service失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"删除Service失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def list_services(self, namespace: str, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出命名空间中的Services
        
        Args:
            namespace: 命名空间
            label_selector: 标签选择器
            
        Returns:
            Service列表
        """
        try:
            services = self.core_v1.list_namespaced_service(
                namespace=namespace,
                label_selector=label_selector
            )
            
            service_list = []
            for service in services.items:
                # 提取端口信息
                ports_info = []
                if service.spec.ports:
                    for port in service.spec.ports:
                        port_info = {
                            'name': port.name,
                            'port': port.port,
                            'target_port': port.target_port,
                            'protocol': port.protocol,
                            'node_port': port.node_port
                        }
                        ports_info.append(port_info)
                
                service_info = {
                    'name': service.metadata.name,
                    'namespace': service.metadata.namespace,
                    'labels': service.metadata.labels or {},
                    'type': service.spec.type,
                    'cluster_ip': service.spec.cluster_ip,
                    'external_ips': service.spec.external_i_ps or [],
                    'ports': ports_info,
                    'selector': service.spec.selector or {},
                    'creation_timestamp': service.metadata.creation_timestamp
                }
                service_list.append(service_info)
            
            return service_list
            
        except Exception as e:
            logger.error(f"列出Services失败: {e}")
            return []
    
    def get_service_endpoints(self, namespace: str, service_name: str) -> Tuple[bool, str, Optional[List[Dict]]]:
        """
        获取Service的端点信息
        
        Args:
            namespace: 命名空间
            service_name: Service名称
            
        Returns:
            (成功标志, 消息, 端点列表)
        """
        try:
            endpoints = self.core_v1.read_namespaced_endpoints(
                name=service_name,
                namespace=namespace
            )
            
            endpoint_list = []
            if endpoints.subsets:
                for subset in endpoints.subsets:
                    subset_info = {
                        'addresses': [],
                        'ports': []
                    }
                    
                    # 提取地址信息
                    if subset.addresses:
                        for address in subset.addresses:
                            addr_info = {
                                'ip': address.ip,
                                'hostname': address.hostname,
                                'node_name': address.node_name
                            }
                            subset_info['addresses'].append(addr_info)
                    
                    # 提取端口信息
                    if subset.ports:
                        for port in subset.ports:
                            port_info = {
                                'name': port.name,
                                'port': port.port,
                                'protocol': port.protocol
                            }
                            subset_info['ports'].append(port_info)
                    
                    endpoint_list.append(subset_info)
            
            return True, "获取端点信息成功", endpoint_list
            
        except ApiException as e:
            if e.status == 404:
                return False, f"Service {service_name} 的端点不存在", None
            error_msg = f"获取Service端点失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"获取Service端点失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def _dict_to_service(self, yaml_data: Dict, service: client.V1Service) -> None:
        """
        将字典数据转换为V1Service对象
        
        Args:
            yaml_data: YAML字典数据
            service: V1Service对象
        """
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
            service.metadata = metadata
        
        # 设置spec
        if 'spec' in yaml_data:
            spec = client.V1ServiceSpec()
            if 'type' in yaml_data['spec']:
                spec.type = yaml_data['spec']['type']
            if 'clusterIP' in yaml_data['spec']:
                spec.cluster_ip = yaml_data['spec']['clusterIP']
            if 'externalIPs' in yaml_data['spec']:
                spec.external_i_ps = yaml_data['spec']['externalIPs']
            if 'selector' in yaml_data['spec']:
                spec.selector = yaml_data['spec']['selector']
            if 'ports' in yaml_data['spec']:
                ports = []
                for port_data in yaml_data['spec']['ports']:
                    port = client.V1ServicePort()
                    if 'name' in port_data:
                        port.name = port_data['name']
                    if 'port' in port_data:
                        port.port = port_data['port']
                    if 'targetPort' in port_data:
                        port.target_port = port_data['targetPort']
                    if 'protocol' in port_data:
                        port.protocol = port_data['protocol']
                    if 'nodePort' in port_data:
                        port.node_port = port_data['nodePort']
                    ports.append(port)
                spec.ports = ports
            service.spec = spec

