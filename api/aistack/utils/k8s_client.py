import logging
import os
import yaml
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
from pathlib import Path
from aistack import project_path
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class KubernetesClient:
    """Kubernetes客户端管理类"""
    
    def __init__(self):
        """初始化Kubernetes客户端"""
        try:
            # 尝试加载集群内配置
            try:
                config.load_incluster_config()
                logger.info("使用集群内Kubernetes配置")
            except:
                # 尝试加载本地kubeconfig
                try:
                    config.load_kube_config()
                    logger.info("使用本地kubeconfig配置")
                except Exception as e:
                    logger.error(f"无法加载Kubernetes配置: {e}")
                    raise
            
            # 初始化API客户端
            self.apps_v1 = client.AppsV1Api()
            self.core_v1 = client.CoreV1Api()
            self.networking_v1 = client.NetworkingV1Api()
            self.batch_v1 = client.BatchV1Api()
            
            logger.info("Kubernetes客户端初始化成功")
            
        except Exception as e:
            logger.error(f"Kubernetes客户端初始化失败: {e}")
            raise
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        测试Kubernetes连接
        
        Returns:
            (成功标志, 消息)
        """
        try:
            # 获取集群版本信息
            version_api = client.VersionApi()
            version = version_api.get_code()
            logger.info(f"Kubernetes集群连接成功，版本: {version.git_version}")
            return True, f"连接成功，集群版本: {version.git_version}"
        except Exception as e:
            error_msg = f"Kubernetes连接失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_namespaces(self) -> List[Dict[str, Any]]:
        """
        获取所有命名空间
        
        Returns:
            命名空间列表
        """
        try:
            namespaces = self.core_v1.list_namespace()
            namespace_list = []
            
            for ns in namespaces.items:
                namespace_info = {
                    'name': ns.metadata.name,
                    'creation_timestamp': ns.metadata.creation_timestamp,
                    'status': ns.status.phase,
                    'labels': ns.metadata.labels or {}
                }
                namespace_list.append(namespace_info)
            
            return namespace_list
            
        except Exception as e:
            logger.error(f"获取命名空间失败: {e}")
            return []
    
    def create_namespace(self, name: str, labels: Optional[Dict[str, str]] = None) -> Tuple[bool, str]:
        """
        创建命名空间
        
        Args:
            name: 命名空间名称
            labels: 标签
            
        Returns:
            (成功标志, 消息)
        """
        try:
            # 检查命名空间是否已存在
            try:
                existing_ns = self.core_v1.read_namespace(name=name)
                if existing_ns:
                    return True, f"命名空间 {name} 已存在"
            except ApiException as e:
                if e.status != 404:
                    raise
            
            # 创建命名空间
            namespace_manifest = client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels or {}
                )
            )
            
            self.core_v1.create_namespace(body=namespace_manifest)
            logger.info(f"命名空间创建成功: {name}")
            return True, f"命名空间 {name} 创建成功"
            
        except Exception as e:
            error_msg = f"创建命名空间失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def load_yaml_from_url(self, url: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        从URL加载YAML文件
        
        Args:
            url: YAML文件URL
            
        Returns:
            (成功标志, 消息, YAML内容)
        """
        try:
            import urllib.request
            import urllib.error
            
            logger.info(f"开始下载YAML文件: {url}")

            # 如果是本机的 /static 路径，避免在请求处理中再次请求自身导致阻塞，直接读磁盘
            parsed = urlparse(url)
            hostname = parsed.hostname  # 正确解析主机名（忽略端口）
            if parsed.scheme in ("http", "https") and hostname in ("localhost", "127.0.0.1", "::1") and parsed.path.startswith("/static/"):
                # 静态目录在项目 api 目录下：<repo>/api/static
                static_dir = Path(project_path).parent / "static"
                rel_path = parsed.path[len("/static/"):]
                local_path = static_dir / rel_path
                if not local_path.exists():
                    return False, f"本地静态文件不存在: {local_path}", None
                with open(local_path, 'r', encoding='utf-8') as f:
                    yaml_content = f.read()
                yaml_data = yaml.safe_load(yaml_content)
                logger.info(f"本地静态YAML原文:\n{yaml_content}")
                logger.info(f"本地静态YAML解析结果: {yaml_data}")
                logger.info(f"本地静态YAML加载成功: {local_path}")
                return True, "YAML文件加载成功", yaml_data
            
            # 设置请求头
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            # 下载文件内容
            # 设置全局/单次请求超时，避免卡住
            with urllib.request.urlopen(req, timeout=15) as response:
                yaml_content = response.read().decode('utf-8')
            
            # 解析YAML
            yaml_data = yaml.safe_load(yaml_content)
            logger.debug(f"远程YAML原文:\n{yaml_content}")
            logger.debug(f"远程YAML解析结果: {yaml_data}")
            
            logger.info(f"YAML文件下载并解析成功: {url}")
            return True, "YAML文件加载成功", yaml_data
            
        except urllib.error.URLError as e:
            error_msg = f"下载YAML文件失败 - URL错误/超时: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except yaml.YAMLError as e:
            error_msg = f"YAML解析失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"加载YAML文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def load_yaml_from_file(self, file_path: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        从本地文件加载YAML
        
        Args:
            file_path: 本地文件路径
            
        Returns:
            (成功标志, 消息, YAML内容)
        """
        try:
            if not os.path.exists(file_path):
                return False, f"文件不存在: {file_path}", None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
            
            yaml_data = yaml.safe_load(yaml_content)
            
            logger.info(f"本地YAML文件加载成功: {file_path}")
            return True, "YAML文件加载成功", yaml_data
            
        except yaml.YAMLError as e:
            error_msg = f"YAML解析失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
        except Exception as e:
            error_msg = f"加载YAML文件失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None
    
    def load_yaml(self, yaml_source: str) -> Tuple[bool, str, Optional[Dict]]:
        """
        智能加载YAML文件（自动判断URL或本地文件）
        
        Args:
            yaml_source: YAML文件源（URL或本地路径）
            
        Returns:
            (成功标志, 消息, YAML内容)
        """
        if yaml_source.startswith(('http://', 'https://')):
            return self.load_yaml_from_url(yaml_source)
        else:
            return self.load_yaml_from_file(yaml_source)
    
    def get_pods_by_label(self, namespace: str, label_selector: str) -> Tuple[bool, str, List[str]]:
        """
        根据标签选择器获取Pod名称列表
        
        Args:
            namespace: 命名空间
            label_selector: 标签选择器（如 "app=nginx"）
            
        Returns:
            (成功标志, 消息, Pod名称列表)
        """
        try:
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector
            )
            
            pod_names = [pod.metadata.name for pod in pods.items]
            logger.info(f"找到 {len(pod_names)} 个Pod: {pod_names}")
            return True, f"找到 {len(pod_names)} 个Pod", pod_names
            
        except ApiException as e:
            error_msg = f"获取Pod列表失败: {e.reason} - {e.body}"
            logger.error(error_msg)
            return False, error_msg, []
        except Exception as e:
            error_msg = f"获取Pod列表失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, []
    
    def get_pod_logs(self, pod_name: str, namespace: str, container_name: Optional[str] = None,
                     tail_lines: int = 100, since_seconds: Optional[int] = None,
                     timestamps: bool = False) -> Tuple[bool, str, str]:
        """
        获取Pod日志
        
        Args:
            pod_name: Pod名称
            namespace: 命名空间
            container_name: 容器名称（可选，如果Pod中有多个容器）
            tail_lines: 返回的日志行数
            since_seconds: 返回自多少秒前的日志
            timestamps: 是否包含时间戳
            
        Returns:
            (成功标志, 消息, 日志内容)
        """
        try:
            logs = self.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container_name,
                tail_lines=tail_lines,
                since_seconds=since_seconds,
                timestamps=timestamps
            )
            
            log_content = logs if logs else "（无日志输出）"
            logger.info(f"成功获取Pod {pod_name} 的日志，共 {len(log_content)} 字符")
            return True, "日志获取成功", log_content
            
        except ApiException as e:
            if e.status == 404:
                error_msg = f"Pod {pod_name} 不存在"
                logger.error(error_msg)
                return False, error_msg, ""
            else:
                error_msg = f"获取Pod日志失败: {e.reason} - {e.body}"
                logger.error(error_msg)
                return False, error_msg, ""
        except Exception as e:
            error_msg = f"获取Pod日志失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, ""


