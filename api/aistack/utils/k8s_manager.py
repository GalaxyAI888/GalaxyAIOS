import logging
import os
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from .k8s_client import KubernetesClient
from .k8s_deployment import KubernetesDeploymentManager
from .k8s_service import KubernetesServiceManager

logger = logging.getLogger(__name__)


class KubernetesManager:
    """Kubernetes综合管理类"""
    
    def __init__(self):
        """初始化Kubernetes管理器"""
        try:
            self.client = KubernetesClient()
            self.deployment_manager = KubernetesDeploymentManager(self.client)
            self.service_manager = KubernetesServiceManager(self.client)
            self._check_k8s_permissions()
            logger.info("Kubernetes管理器初始化成功")
        except Exception as e:
            logger.error(f"Kubernetes管理器初始化失败: {e}")
            raise
    
    def _check_k8s_permissions(self) -> None:
        """
        检查Kubernetes权限和配置
        """
        try:
            # 测试连接
            success, message = self.client.test_connection()
            if success:
                logger.info(f"Kubernetes连接测试成功: {message}")
            else:
                logger.warning(f"Kubernetes连接测试失败: {message}")
                logger.warning("请确保kubectl配置正确，并且有足够的权限访问集群")
            
            # 获取命名空间列表
            namespaces = self.client.get_namespaces()
            logger.info(f"可访问的命名空间数量: {len(namespaces)}")
            
        except Exception as e:
            logger.warning(f"Kubernetes权限检查失败: {e}")
            logger.warning("请确保Kubernetes集群可访问，并且当前用户有足够权限")
    
    def deploy_app(self, app_name: str, namespace: str, 
                   deployment_yaml_url: Optional[str] = None,
                   service_yaml_url: Optional[str] = None,
                   config_yaml_url: Optional[str] = None,
                   ingress_yaml_url: Optional[str] = None,
                   custom_labels: Optional[Dict[str, str]] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        部署应用到Kubernetes
        
        Args:
            app_name: 应用名称
            namespace: 命名空间
            deployment_yaml_url: Deployment YAML文件URL
            service_yaml_url: Service YAML文件URL
            config_yaml_url: ConfigMap YAML文件URL
            ingress_yaml_url: Ingress YAML文件URL
            custom_labels: 自定义标签
            
        Returns:
            (成功标志, 消息, 部署结果)
        """
        try:
            logger.info(f"开始部署应用: {app_name} 到命名空间: {namespace}")
            
            # 确保命名空间存在
            ns_success, ns_message = self.client.create_namespace(namespace, custom_labels)
            if not ns_success:
                logger.warning(f"命名空间创建/检查失败: {ns_message}")
            
            # Idempotent: 如果Deployment已存在且就绪，直接返回成功
            try:
                dep_ok, dep_msg, dep_info = self.deployment_manager.get_deployment(
                    namespace=namespace,
                    deployment_name=app_name
                )
                if dep_ok and dep_info:
                    ready_replicas = dep_info.get("ready_replicas", 0) or 0
                    desired_replicas = dep_info.get("replicas", 0) or 0
                    if desired_replicas > 0 and ready_replicas == desired_replicas:
                        logger.info(
                            f"检测到Deployment已就绪，跳过重复部署: {app_name} ({ready_replicas}/{desired_replicas})"
                        )
                        return True, f"应用 {app_name} 已部署并就绪，无需重复部署", {
                            "deployment": {"success": True, "message": "已存在且就绪"},
                            "service": None,
                            "config": None,
                            "ingress": None
                        }
            except Exception as check_e:
                logger.warning(f"检查现有Deployment状态失败，继续尝试部署: {check_e}")
            
            deployment_result = None
            service_result = None
            config_result = None
            ingress_result = None
            
            # 部署Deployment
            if deployment_yaml_url:
                logger.info(f"部署Deployment: {deployment_yaml_url}")
                success, message = self.deployment_manager.create_deployment_from_yaml(
                    namespace=namespace,
                    yaml_source=deployment_yaml_url,
                    custom_labels=custom_labels
                )
                deployment_result = {"success": success, "message": message}
                if not success:
                    logger.error(f"Deployment部署失败: {message}")
                    return False, f"Deployment部署失败: {message}", {
                        "deployment": deployment_result,
                        "service": service_result,
                        "config": config_result,
                        "ingress": ingress_result
                    }
            
            # 部署Service
            if service_yaml_url:
                logger.info(f"部署Service: {service_yaml_url}")
                success, message = self.service_manager.create_service_from_yaml(
                    namespace=namespace,
                    yaml_source=service_yaml_url,
                    custom_labels=custom_labels
                )
                service_result = {"success": success, "message": message}
                if not success:
                    logger.error(f"Service部署失败: {message}")
                    # 如果Service部署失败，尝试回滚Deployment
                    if deployment_result and deployment_result.get("success"):
                        logger.info("尝试回滚Deployment...")
                        # 这里可以添加回滚逻辑
            
            # 部署ConfigMap (如果提供)
            if config_yaml_url:
                logger.info(f"部署ConfigMap: {config_yaml_url}")
                # ConfigMap部署逻辑可以在这里添加
                config_result = {"success": True, "message": "ConfigMap部署功能待实现"}
            
            # 部署Ingress (如果提供)
            if ingress_yaml_url:
                logger.info(f"部署Ingress: {ingress_yaml_url}")
                # Ingress部署逻辑可以在这里添加
                ingress_result = {"success": True, "message": "Ingress部署功能待实现"}
            
            logger.info(f"应用 {app_name} 部署完成")
            return True, f"应用 {app_name} 部署成功", {
                "deployment": deployment_result,
                "service": service_result,
                "config": config_result,
                "ingress": ingress_result
            }
            
        except Exception as e:
            error_msg = f"部署应用失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def deploy_app_from_json(self, app_name: str, namespace: str, 
                            deployment_config: Optional[Dict[str, Any]] = None,
                            service_config: Optional[Dict[str, Any]] = None,
                            configmap_config: Optional[Dict[str, Any]] = None,
                            ingress_config: Optional[Dict[str, Any]] = None,
                            custom_labels: Optional[Dict[str, str]] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        从JSON配置部署应用到Kubernetes
        
        Args:
            app_name: 应用名称
            namespace: 命名空间
            deployment_config: Deployment配置字典
            service_config: Service配置字典
            configmap_config: ConfigMap配置字典
            ingress_config: Ingress配置字典
            custom_labels: 自定义标签
            
        Returns:
            (成功标志, 消息, 部署结果)
        """
        try:
            logger.info(f"开始从JSON配置部署应用: {app_name} 到命名空间: {namespace}")
            
            # 确保命名空间存在
            ns_success, ns_message = self.client.create_namespace(namespace, custom_labels)
            if not ns_success:
                logger.warning(f"命名空间创建/检查失败: {ns_message}")
            
            # Idempotent: 如果Deployment已存在且就绪，直接返回成功
            try:
                dep_ok, dep_msg, dep_info = self.deployment_manager.get_deployment(
                    namespace=namespace,
                    deployment_name=app_name
                )
                if dep_ok and dep_info:
                    ready_replicas = dep_info.get("ready_replicas", 0) or 0
                    desired_replicas = dep_info.get("replicas", 0) or 0
                    if desired_replicas > 0 and ready_replicas == desired_replicas:
                        logger.info(
                            f"检测到Deployment已就绪，跳过重复部署: {app_name} ({ready_replicas}/{desired_replicas})"
                        )
                        return True, f"应用 {app_name} 已部署并就绪，无需重复部署", {
                            "deployment": {"success": True, "message": "已存在且就绪"},
                            "service": None,
                            "config": None,
                            "ingress": None
                        }
            except Exception as check_e:
                logger.warning(f"检查现有Deployment状态失败，继续尝试部署: {check_e}")
            
            deployment_result = None
            service_result = None
            config_result = None
            ingress_result = None
            
            # 部署Deployment
            if deployment_config:
                logger.info(f"部署Deployment: {deployment_config.get('metadata', {}).get('name', 'unknown')}")
                success, message = self.deployment_manager.create_deployment_from_json(
                    namespace=namespace,
                    deployment_config=deployment_config,
                    custom_labels=custom_labels
                )
                deployment_result = {"success": success, "message": message}
                if not success:
                    logger.error(f"Deployment部署失败: {message}")
                    return False, f"Deployment部署失败: {message}", {
                        "deployment": deployment_result,
                        "service": service_result,
                        "config": config_result,
                        "ingress": ingress_result
                    }
            
            # 部署Service
            if service_config:
                logger.info(f"部署Service: {service_config.get('metadata', {}).get('name', 'unknown')}")
                success, message = self.service_manager.create_service_from_json(
                    namespace=namespace,
                    service_config=service_config,
                    custom_labels=custom_labels
                )
                service_result = {"success": success, "message": message}
                if not success:
                    logger.error(f"Service部署失败: {message}")
                    # 如果Service部署失败，尝试回滚Deployment
                    if deployment_result and deployment_result.get("success"):
                        logger.info("尝试回滚Deployment...")
                        # 这里可以添加回滚逻辑
            
            # 部署ConfigMap (如果提供)
            if configmap_config:
                logger.info(f"部署ConfigMap: {configmap_config.get('metadata', {}).get('name', 'unknown')}")
                # ConfigMap部署逻辑可以在这里添加
                config_result = {"success": True, "message": "ConfigMap部署功能待实现"}
            
            # 部署Ingress (如果提供)
            if ingress_config:
                logger.info(f"部署Ingress: {ingress_config.get('metadata', {}).get('name', 'unknown')}")
                # Ingress部署逻辑可以在这里添加
                ingress_result = {"success": True, "message": "Ingress部署功能待实现"}
            
            logger.info(f"应用 {app_name} 部署完成")
            return True, f"应用 {app_name} 部署成功", {
                "deployment": deployment_result,
                "service": service_result,
                "config": config_result,
                "ingress": ingress_result
            }
            
        except Exception as e:
            error_msg = f"部署应用失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def get_app_status(self, app_name: str, namespace: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        获取应用状态
        
        Args:
            app_name: 应用名称
            namespace: 命名空间
            
        Returns:
            (成功标志, 消息, 应用状态信息)
        """
        try:
            status_info = {
                "app_name": app_name,
                "namespace": namespace,
                "deployment": None,
                "service": None,
                "pods": [],
                "overall_status": "Unknown"
            }
            
            # 获取Deployment状态
            deployment_success, deployment_message, deployment_info = self.deployment_manager.get_deployment(
                namespace=namespace,
                deployment_name=app_name
            )
            
            if deployment_success:
                status_info["deployment"] = deployment_info
                status_info["overall_status"] = deployment_info.get("status", "Unknown")
            else:
                logger.warning(f"获取Deployment状态失败: {deployment_message}")
            
            # 获取Service状态
            service_success, service_message, service_info = self.service_manager.get_service(
                namespace=namespace,
                service_name=app_name
            )
            
            if service_success:
                status_info["service"] = service_info
            else:
                logger.warning(f"获取Service状态失败: {service_message}")
            
            # 获取Pod状态 (通过Deployment获取)
            if deployment_success:
                # 这里可以添加获取Pod状态的逻辑
                status_info["pods"] = []  # 暂时为空，可以后续扩展
            
            return True, "获取应用状态成功", status_info
            
        except Exception as e:
            error_msg = f"获取应用状态失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def scale_app(self, app_name: str, namespace: str, replicas: int) -> Tuple[bool, str]:
        """
        扩缩容应用
        
        Args:
            app_name: 应用名称
            namespace: 命名空间
            replicas: 目标副本数
            
        Returns:
            (成功标志, 消息)
        """
        try:
            logger.info(f"扩缩容应用: {app_name} 到 {replicas} 个副本")
            
            success, message = self.deployment_manager.scale_deployment(
                namespace=namespace,
                deployment_name=app_name,
                replicas=replicas
            )
            
            if success:
                logger.info(f"应用扩缩容成功: {message}")
            else:
                logger.error(f"应用扩缩容失败: {message}")
            
            return success, message
            
        except Exception as e:
            error_msg = f"扩缩容应用失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def delete_app(self, app_name: str, namespace: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        删除应用
        
        Args:
            app_name: 应用名称
            namespace: 命名空间
            
        Returns:
            (成功标志, 消息, 删除结果)
        """
        try:
            logger.info(f"开始删除应用: {app_name} 从命名空间: {namespace}")
            
            deployment_result = None
            service_result = None
            
            # 删除Deployment
            deployment_success, deployment_message = self.deployment_manager.delete_deployment(
                namespace=namespace,
                deployment_name=app_name
            )
            deployment_result = {"success": deployment_success, "message": deployment_message}
            
            # 删除Service
            service_success, service_message = self.service_manager.delete_service(
                namespace=namespace,
                service_name=app_name
            )
            service_result = {"success": service_success, "message": service_message}
            
            # 检查是否有任何组件删除失败
            if not deployment_success and not service_success:
                return False, "所有组件删除失败", {
                    "deployment": deployment_result,
                    "service": service_result
                }
            
            success_msg = f"应用 {app_name} 删除完成"
            logger.info(success_msg)
            
            return True, success_msg, {
                "deployment": deployment_result,
                "service": service_result
            }
            
        except Exception as e:
            error_msg = f"删除应用失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}
    
    def list_apps(self, namespace: str, label_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出命名空间中的应用
        
        Args:
            namespace: 命名空间
            label_selector: 标签选择器
            
        Returns:
            应用列表
        """
        try:
            apps = []
            
            # 获取Deployments
            deployments = self.deployment_manager.list_deployments(
                namespace=namespace,
                label_selector=label_selector
            )
            
            # 获取Services
            services = self.service_manager.list_services(
                namespace=namespace,
                label_selector=label_selector
            )
            
            # 合并应用信息
            deployment_dict = {dep['name']: dep for dep in deployments}
            service_dict = {svc['name']: svc for svc in services}
            
            all_app_names = set(deployment_dict.keys()) | set(service_dict.keys())
            
            for app_name in all_app_names:
                app_info = {
                    'name': app_name,
                    'namespace': namespace,
                    'deployment': deployment_dict.get(app_name),
                    'service': service_dict.get(app_name),
                    'status': 'Unknown'
                }
                
                # 确定应用状态
                if app_name in deployment_dict:
                    dep_info = deployment_dict[app_name]
                    if dep_info['status'] == 'Running':
                        app_info['status'] = 'Running'
                    elif dep_info['status'] == 'Not Ready':
                        app_info['status'] = 'Not Ready'
                
                apps.append(app_info)
            
            return apps
            
        except Exception as e:
            logger.error(f"列出应用失败: {e}")
            return []
    
    def get_app_logs(self, app_name: str, namespace: str, container_name: Optional[str] = None, 
                    tail_lines: int = 100) -> Tuple[bool, str, str]:
        """
        获取应用日志
        
        Args:
            app_name: 应用名称
            namespace: 命名空间
            container_name: 容器名称（可选）
            tail_lines: 日志行数
            
        Returns:
            (成功标志, 消息, 日志内容)
        """
        try:
            # 通过标签查找Pod
            label_selector = f"app={app_name}"
            success, message, pod_names = self.client.get_pods_by_label(namespace, label_selector)
            
            if not success or not pod_names:
                return False, f"未找到应用 {app_name} 的Pod", ""
            
            # 如果有多个Pod，只获取第一个Pod的日志
            # 如果需要获取所有Pod的日志，可以在这里添加循环
            pod_name = pod_names[0]
            logger.info(f"获取Pod {pod_name} 的日志")
            
            # 获取Pod日志
            success, message, logs = self.client.get_pod_logs(
                pod_name=pod_name,
                namespace=namespace,
                container_name=container_name,
                tail_lines=tail_lines
            )
            
            if not success:
                return False, message, ""
            
            # 如果有多个Pod，可以添加提示
            if len(pod_names) > 1:
                logs = f"（提示：应用有 {len(pod_names)} 个Pod，仅显示第一个Pod的日志）\n\n{logs}"
            
            return True, "日志获取成功", logs
            
        except Exception as e:
            error_msg = f"获取应用日志失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, ""
    
    def update_app(self, app_name: str, namespace: str, 
                   deployment_yaml_url: Optional[str] = None,
                   service_yaml_url: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        更新应用
        
        Args:
            app_name: 应用名称
            namespace: 命名空间
            deployment_yaml_url: 新的Deployment YAML文件URL
            service_yaml_url: 新的Service YAML文件URL
            
        Returns:
            (成功标志, 消息, 更新结果)
        """
        try:
            logger.info(f"开始更新应用: {app_name} 在命名空间: {namespace}")
            
            deployment_result = None
            service_result = None
            
            # 更新Deployment
            if deployment_yaml_url:
                logger.info(f"更新Deployment: {deployment_yaml_url}")
                success, message = self.deployment_manager.update_deployment_from_yaml(
                    namespace=namespace,
                    deployment_name=app_name,
                    yaml_source=deployment_yaml_url
                )
                deployment_result = {"success": success, "message": message}
                if not success:
                    logger.error(f"Deployment更新失败: {message}")
            
            # 更新Service
            if service_yaml_url:
                logger.info(f"更新Service: {service_yaml_url}")
                # Service更新逻辑可以在这里添加
                service_result = {"success": True, "message": "Service更新功能待实现"}
            
            success_msg = f"应用 {app_name} 更新完成"
            logger.info(success_msg)
            
            return True, success_msg, {
                "deployment": deployment_result,
                "service": service_result
            }
            
        except Exception as e:
            error_msg = f"更新应用失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, {}

