#!/bin/bash

# 定义颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# 退出集群的主要函数
leave_cluster() {
    echo -e "${GREEN}[1/3] 停止边缘节点服务...${NC}"
    
    # 停止edgecore服务
    if systemctl is-active --quiet edgecore.service; then
        sudo systemctl stop edgecore.service
        echo "已停止edgecore服务"
    else
        echo "edgecore服务未运行"
    fi
    
    # 禁用edgecore服务自启动
    if systemctl is-enabled --quiet edgecore.service; then
        sudo systemctl disable edgecore.service
        echo "已禁用edgecore服务自启动"
    fi
    
    echo -e "${GREEN}[2/3] 清理KubeEdge配置...${NC}"
    
    # 清理KubeEdge配置
    if [ -d "/etc/kubeedge" ]; then
        sudo rm -rf /etc/kubeedge
        echo "已删除KubeEdge配置目录"
    else
        echo "KubeEdge配置目录不存在"
    fi
    
    # 清理其他可能的KubeEdge数据
    if [ -d "/var/lib/kubeedge" ]; then
        sudo rm -rf /var/lib/kubeedge
        echo "已删除KubeEdge数据目录"
    fi
    
    echo -e "${GREEN}[3/3] 清理网络配置...${NC}"
    
    # 清理CNI配置
    if [ -d "/etc/cni/net.d" ]; then
        sudo rm -rf /etc/cni/net.d
        echo "已删除CNI配置目录"
    fi
    
    # 删除keadm命令
    if [ -f "/usr/bin/keadm" ]; then
        sudo rm -f /usr/bin/keadm
        echo "已删除keadm命令"
    fi
    
    echo -e "${GREEN}集群退出完成！${NC}"
    echo "节点已成功从KubeEdge集群中移除"
}

# 主执行流程
main() {
    echo "开始从KubeEdge集群退出..."
    leave_cluster
}

main "$@" 