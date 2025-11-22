#!/usr/bin/env bash

# 脚本：在Ubuntu 24.04上自动化安装dockerd、nvidia-container-toolkit、k3s和nvidia-device-plugin
# 作者：AI Assistant
# 日期：$(date +'%Y-%m-%d')

# wsl --install -d Ubuntu-24.04 --name Ubuntu24-AINode
# wsl --list --online
# wsl -d Ubuntu24-AINode
# sudo bash -x ./setup_nvidia_k3s.sh

# 设置颜色变量
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
NC='\033[0m' # 无颜色

# 日志函数
echo_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}
echo_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}
echo_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}
echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 检查是否以root用户运行
check_root() {
    if [ "$(id -u)" != "0" ]; then
        echo_warning "此脚本需要以root用户运行，请使用sudo或切换到root用户"
    fi
}

# 验证NVIDIA驱动是否已安装
check_nvidia_driver() {
    echo_info "验证NVIDIA驱动是否已安装..."
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi --version >/dev/null 2>&1; then
        echo_success "NVIDIA驱动已安装，输出nvidia-smi信息："
        nvidia-smi
        ufw disable
    else
        echo_warning "NVIDIA驱动未安装或不可用，脚本终止"
    fi
}

# 安装Python开发环境和必要的构建工具
install_python_dev() {
    echo_info "安装Python开发环境和必要的构建工具..."
    
    # 检测Python版本
    local python_version="python3"
    if command -v python3.12 >/dev/null 2>&1; then
        python_version="python3.12"
        echo_info "检测到Python 3.12"
    elif command -v python3.11 >/dev/null 2>&1; then
        python_version="python3.11"
        echo_info "检测到Python 3.11"
    else
        # 尝试安装Python 3.12
        sudo apt install -y python3.12 python3.12-venv
        if command -v python3.12 >/dev/null 2>&1; then
            python_version="python3.12"
        fi
    fi
    
    # 根据检测到的Python版本安装对应的包
    local python_major_minor=$(echo $python_version | sed 's/python//')
    local python_dev_pkg="python${python_major_minor}-dev python${python_major_minor}-venv"
    
    # 安装必要的包
    sudo apt install -y python3-pip build-essential $python_dev_pkg
    
    if [ $? -eq 0 ]; then
        echo_success "Python开发环境和构建工具安装成功"
        echo_info "已安装：$python_version, python3-pip, build-essential, $python_dev_pkg"
        
        # 配置pip使用国内镜像源
        echo_info "配置pip使用国内镜像源..."
        if [ -n "$SUDO_USER" ]; then
            # 为使用sudo的用户配置pip镜像
            sudo mkdir -p /home/$SUDO_USER/.pip
            sudo bash -c "cat > /home/$SUDO_USER/.pip/pip.conf << 'EOF'
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
EOF"
            sudo chown $SUDO_USER:$SUDO_USER /home/$SUDO_USER/.pip/pip.conf
        else
            # 为当前用户配置pip镜像
            mkdir -p ~/.pip
            cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
EOF
        fi
        echo_success "pip已配置使用清华大学镜像源"
    else
        echo_warning "Python开发环境安装失败，但继续执行脚本"
    fi
}

# 备份并修改Ubuntu源为阿里云源
change_to_aliyun_source() {
    echo_info "将Ubuntu源更改为阿里云源..."
    
    # 备份原始源文件
    if [ -f /etc/apt/sources.list ]; then
        sudo cp /etc/apt/sources.list /etc/apt/sources.list.bak
        echo_info "已备份原始源文件到/etc/apt/sources.list.bak"
    fi
    
    # 写入阿里云源
    sudo bash -c "cat > /etc/apt/sources.list << EOF
# Ubuntu 24.04 (Noble Numbat) 阿里云源
deb http://mirrors.aliyun.com/ubuntu/ noble main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ noble main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ noble-security main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ noble-security main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ noble-updates main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ noble-updates main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ noble-proposed main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ noble-proposed main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ noble-backports main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ noble-backports main restricted universe multiverse
EOF"
    
    # 更新源
    sudo apt update && sudo apt upgrade -y
    if [ $? -eq 0 ]; then
        echo_success "Ubuntu源已成功更改为阿里云源并更新"
    else
        echo_warning "更新源失败，请检查网络连接或源配置"
    fi
}

# 永久关闭swap分区（支持常规Ubuntu和WSL2环境）
disable_swap_permanently() {
    echo_info "永久关闭swap分区..."
    
    # 检查是否在WSL环境中运行
    if grep -q "microsoft" /proc/version &> /dev/null; then
        echo_info "检测到WSL环境，采用WSL特定方式禁用swap"
        
        # 临时关闭swap
        sudo swapoff -a
        if [ $? -eq 0 ]; then
            echo_info "临时关闭swap分区成功"
        else
            echo_warning "临时关闭swap分区失败，但继续执行脚本"
        fi
        
        # 在WSL内部编辑/etc/wsl.conf文件添加swap=0配置
        echo_info "在WSL内部编辑/etc/wsl.conf文件添加swap=0配置..."
        
        # 备份现有的wsl.conf文件
        if [ -f /etc/wsl.conf ]; then
            sudo cp /etc/wsl.conf /etc/wsl.conf.bak
            echo_info "已备份现有/etc/wsl.conf文件到/etc/wsl.conf.bak"
        fi
        
        # 检查文件中是否已有[wsl2]部分
        if grep -q "^\[wsl2\]" /etc/wsl.conf 2>/dev/null; then
            # 如果已有[wsl2]部分，检查是否已有swap配置
            if grep -q "^swap=" /etc/wsl.conf 2>/dev/null; then
                # 如果已有swap配置，修改它
                sudo sed -i '/^swap=/c\swap=0' /etc/wsl.conf
            else
                # 如果没有swap配置，添加它
                sudo sed -i '/^\[wsl2\]/a\swap=0' /etc/wsl.conf
            fi
        else
            # 如果没有[wsl2]部分，添加整个部分
            echo -e "\n[wsl2]\nswap=0" | sudo tee -a /etc/wsl.conf > /dev/null
        fi
        
        if [ $? -eq 0 ]; then
            echo_success "已在/etc/wsl.conf中添加swap=0配置"
            echo_info "配置完成后需要重启WSL服务才能生效（在Windows命令提示符中运行：wsl --shutdown）"
        else
            echo_warning "修改/etc/wsl.conf文件失败，但继续执行脚本"
        fi
        
    else
        # 常规Ubuntu系统的处理方式
        echo_info "检测到常规Ubuntu环境"
        
        # 临时关闭swap
        sudo swapoff -a
        if [ $? -eq 0 ]; then
            echo_info "临时关闭swap分区成功"
        else
            echo_warning "临时关闭swap分区失败，但继续执行脚本"
        fi
        
        # 永久关闭swap（注释掉/etc/fstab中的swap行）
        sudo sed -i '/swap/s/^/#/' /etc/fstab
        if [ $? -eq 0 ]; then
            echo_success "永久关闭swap分区配置已设置，重启后生效"
        else
            echo_warning "修改/etc/fstab失败，但继续执行脚本"
        fi
    fi
}

# 设置/mnt为共享挂载点，确保重启后有效
set_shared_mount() {
    echo_info "设置/mnt为共享挂载点..."
    
    # 立即设置共享挂载
    sudo mount --make-shared /
    if [ $? -eq 0 ]; then
        echo_info "已临时设置共享挂载点"
    else
        echo_warning "临时设置共享挂载点失败，但继续执行脚本"
    fi
    
    # 使共享挂载永久生效（添加到/etc/fstab）
    # grep -q 'none / mnt shared' /etc/fstab || echo 'none / mnt shared' >> /etc/fstab
    # if [ $? -eq 0 ]; then
    #     echo_success "共享挂载点配置已添加到/etc/fstab，重启后生效"
    # else
    #     echo_warning "添加共享挂载点配置到/etc/fstab失败，但继续执行脚本"
    # fi
}

# 安装Docker和配置加速
install_docker() {
    echo_info "安装Docker并配置加速..."
    
    # # 卸载旧版本Docker
    # sudo apt remove -y docker docker-engine docker.io containerd runc
    
    # # 安装必要的包
    # sudo apt update
    # sudo apt install -y ca-certificates curl gnupg lsb-release
    
    # # 添加Docker GPG密钥
    # sudo mkdir -p /etc/apt/keyrings
    # curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # # 设置Docker源
    # echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # # 安装Docker
    # sudo apt update
    # sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    sudo apt-get install apt-transport-https ca-certificates curl gnupg-agent software-properties-common -y
    curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list

    # 更新包列表，不然docker-ce安装失败，因为docker-ce的源没有更新
    sudo apt update
    
    sudo apt install -y docker-ce docker-ce-cli containerd.io
    if [ $? -eq 0 ]; then
        echo_success "Docker安装成功"
        
        # 将当前用户添加到docker组，以便普通用户可以使用docker命令
        if [ -n "$SUDO_USER" ]; then
            # 如果使用sudo运行，添加使用sudo的用户到docker组
            sudo usermod -aG docker $SUDO_USER
            echo_success "已将用户 $SUDO_USER 添加到 docker 组"
            echo_warning "注意：需要重新登录或运行 'newgrp docker' 才能使组成员生效"
        elif [ "$(id -u)" -ne 0 ]; then
            # 如果不是root且没有SUDO_USER，添加当前用户
            sudo usermod -aG docker $USER
            echo_success "已将用户 $USER 添加到 docker 组"
            echo_warning "注意：需要重新登录或运行 'newgrp docker' 才能使组成员生效"
        fi
        
        # 配置Docker加速和使用systemd驱动
        sudo mkdir -p /etc/docker
        sudo bash -c "cat > /etc/docker/daemon.json << EOF
{
  \"registry-mirrors\": [\"https://docker.m.daocloud.io\"],
  \"exec-opts\": [\"native.cgroupdriver=systemd\"]
}
EOF"
        
        # 重启Docker服务使配置生效
        sudo systemctl restart docker
        sudo systemctl enable docker
        
        echo_success "Docker加速配置已设置为：https://docker.m.daocloud.io"
    else
        echo_error "Docker安装失败"
    fi
}

# 安装NVIDIA Container Toolkit
install_nvidia_container_toolkit() {
    echo_info "安装NVIDIA Container Toolkit..."
    
    # 添加NVIDIA Container Toolkit源
    # curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    # curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    #     sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    #     sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
    
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

    # 更新源并安装指定版本
    sudo apt update
    # sudo apt install -y nvidia-container-toolkit=1.17.8-1
    
    export NVIDIA_CONTAINER_TOOLKIT_VERSION=1.17.8-1
    sudo apt-get install -y \
        nvidia-container-toolkit=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
        nvidia-container-toolkit-base=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
        libnvidia-container-tools=${NVIDIA_CONTAINER_TOOLKIT_VERSION} \
        libnvidia-container1=${NVIDIA_CONTAINER_TOOLKIT_VERSION}

    if [ $? -eq 0 ]; then
        echo_success "NVIDIA Container Toolkit安装成功"
        
        # 配置Docker以使用NVIDIA运行时
        sudo nvidia-ctk runtime configure --runtime=docker
        
        # 设置Docker默认运行时为nvidia
        echo_info "检查并设置Docker默认运行时为nvidia..."
        sudo sed -i 's/^#default-runtime="nvidia"/default-runtime="nvidia"/' /etc/docker/daemon.json
        
        # 如果配置文件中没有default-runtime，则添加
        if ! grep -q '"default-runtime"' /etc/docker/daemon.json; then
            sudo sed -i 's/"runtimes"/"default-runtime": "nvidia",\n    "runtimes"/' /etc/docker/daemon.json
        fi
        
        sudo docker info | grep -i 'Runtimes\|Default Runtime'
        sudo systemctl restart docker.service
        
        echo_success "已配置Docker以使用NVIDIA运行时"
    else
        echo_warning "NVIDIA Container Toolkit安装失败"
    fi
}

# 安装K3s并配置加速
install_k3s() {
    echo_info "安装K3s并配置加速..."
    
    # 设置K3s安装参数，使用Docker作为容器运行时并配置镜像加速
    export INSTALL_K3S_EXEC="--kubelet-arg=image-gc-high-threshold=80 --kubelet-arg=image-gc-low-threshold=70"
    export K3S_IMAGE_REPO="docker.m.daocloud.io"
    
    # 安装K3s - 尝试多个镜像源
    echo_info "尝试从国内镜像源安装K3s..."
    
    local install_success=false
    
    # 尝试1: rancher-mirror (推荐)
    if curl -sfL https://rancher-mirror.rancher.cn/k3s/k3s-install.sh | INSTALL_K3S_MIRROR=cn sh -s - --docker 2>/dev/null; then
        echo_success "从 rancher-mirror 安装成功"
        install_success=true
    else
        echo_warning "rancher-mirror 连接失败，尝试备用源..."
        
        # 尝试2: get.rancher.io
        if curl -sfL https://get.rancher.io/k3s/k3s-install.sh | sh -s - --docker 2>/dev/null; then
            echo_success "从 get.rancher.io 安装成功"
            install_success=true
        else
            echo_warning "get.rancher.io 连接失败，尝试官方源..."
            
            # 尝试3: 官方源
            if curl -sfL https://get.k3s.io | sh -s - --docker 2>/dev/null; then
                echo_success "从官方源安装成功"
                install_success=true
            else
                echo_error "所有镜像源都连接失败，请检查网络连接"
            fi
        fi
    fi
    
    if [ "$install_success" = "true" ]; then
        echo_success "K3s安装成功，使用Docker作为容器运行时"
        
        # 配置kubectl命令行工具
        mkdir -p ~/.kube
        sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
        # 确保配置文件归当前用户所有，以便普通用户可以使用
        sudo chown $(id -u):$(id -g) ~/.kube/config
        chmod 600 ~/.kube/config
        
        echo_info "已配置kubectl命令行工具"
        echo_info "现在可以使用 kubectl 命令（无需 sudo）"
        # export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
        kubectl get pods --all-namespaces 2>/dev/null || true
        # 显示K3s状态
        # systemctl status k3s
    else
        echo_error "K3s安装失败"
    fi
}

# 安装NVIDIA Device Plugin
install_nvidia_device_plugin() {
    echo_info "安装NVIDIA Device Plugin..."
    
    local install_success=false
    
    # 尝试从GitHub安装NVIDIA Device Plugin指定版本(0.17.4)
    if sudo kubectl create -f nvidia-device-plugin.yml 2>/dev/null; then
        echo_success "从 Local 安装成功"
        install_success=true
    else
        echo_warning "本地文件不存在，尝试使用网络文件..."
        
        # 尝试从ghproxy镜像安装
        if sudo kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.17.4/deployments/static/nvidia-device-plugin.yml 2>/dev/null; then
            echo_success "从 github 镜像安装成功"
            install_success=true
        else
            echo_warning "github 镜像连接失败，尝试使用镜像..."
            
            # 尝试从fastgit镜像安装
            if sudo kubectl create -f https://gitee.com/galaxyai/GalaxyAIOS/blob/main/aios_runtime_setup/nvidia-device-plugin.yml 2>/dev/null; then
                echo_success "从 gitee 镜像安装成功"
                install_success=true
            else
                echo_error "所有镜像源都连接失败"
            fi
        fi
    fi

    if [ "$install_success" = "true" ]; then
        echo_success "NVIDIA Device Plugin安装成功"
        
        # 等待插件部署完成
        echo_info "等待NVIDIA Device Plugin部署完成（可能需要几分钟）..."
        sleep 60
        sudo kubectl get pods -n kube-system | grep nvidia-device-plugin || true
        sudo kubectl label nodes $(hostname) nvidia.com/gpu.present=true 2>/dev/null || true
    else
        echo_warning "NVIDIA Device Plugin安装失败"
    fi
}

# 验证GPU是否可在Kubernetes中使用
verify_gpu_in_kubernetes() {
    echo_info "验证GPU是否可在Kubernetes中使用..."
    
    # 创建一个测试Pod来验证GPU
    cat > gpu-test-pod.yaml << EOF
apiVersion: v1
kind: Pod
metadata:
  name: gpu-test-pod
spec:
  restartPolicy: Never
  containers:
  - name: gpu-test-pod
    image: nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda12.5.0
    resources:
      limits:
        nvidia.com/gpu: 1
  tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
EOF
    
    # 应用测试Pod
    sudo kubectl apply -f gpu-test-pod.yaml
    
    # 等待Pod完成并查看日志
    echo_info "等待测试Pod完成（可能需要几分钟）..."
    # sudo kubectl wait --for=condition=complete pod/gpu-test --timeout=3m
    sudo kubectl get pods -A|grep gpu-test-pod|grep Completed
    if [ $? -eq 0 ]; then
        echo_success "GPU测试Pod已成功运行，查看输出："
        sudo kubectl logs gpu-test-pod
        echo_success "GPU在Kubernetes中可用！"
    else
        sleep 120
        sudo kubectl get pods -A|grep gpu-test-pod|grep Completed
        if [ $? -eq 0 ]; then
            echo_success "GPU测试Pod已成功运行，查看输出："
            sudo kubectl logs gpu-test-pod
            echo_success "GPU在Kubernetes中可用！"
        else
            echo_warning "GPU测试Pod运行失败，请检查配置"
        fi
    fi
}

# 清理功能
cleanup() {
    echo_info "执行清理操作..."
    
    # 停止并卸载K3s
    if command -v k3s-uninstall.sh &> /dev/null; then
        sudo k3s-uninstall.sh
        echo_info "已卸载K3s"
    fi
    
    # # 卸载Docker
    # if command -v docker &> /dev/null; then
    #     sudo apt purge -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    #     sudo rm -rf /var/lib/docker /var/lib/containerd /etc/docker
    #     echo_info "已卸载Docker"
    # fi
    
    # # 卸载NVIDIA Container Toolkit
    # if dpkg -l | grep -q nvidia-container-toolkit; then
    #     sudo apt purge -y nvidia-container-toolkit
    #     echo_info "已卸载NVIDIA Container Toolkit"
    # fi
    
    # 恢复原始源
    # if [ -f /etc/apt/sources.list.bak ]; then
    #     mv /etc/apt/sources.list.bak /etc/apt/sources.list
    #     apt update
    #     echo_info "已恢复原始Ubuntu源"
    # fi
    
    
    # 清理测试文件
    sudo rm -f gpu-test-pod.yaml ~/.kube/config
    
    echo_success "清理操作完成"
}

# 帮助信息
display_help() {
    echo -e "\n${BLUE}使用方法:${NC} $0 [选项]"
    echo -e "\n${BLUE}选项:${NC}"
    echo -e "  ${GREEN}--install${NC}   安装所有组件（默认选项）"
    echo -e "  ${GREEN}--cleanup${NC}   清理所有已安装的组件"
    echo -e "  ${GREEN}--help${NC}      显示此帮助信息"
    echo -e "\n${BLUE}示例:${NC}"
    echo -e "  $0 --install   # 安装docker, nvidia-container-toolkit, k3s, nvidia-device-plugin"
    echo -e "  $0 --cleanup   # 清理所有已安装的组件"
    echo -e ""
}

# 主函数
main() {
    # 处理命令行参数
    case "$1" in
        --install)
            # 执行安装流程
            check_nvidia_driver
            change_to_aliyun_source
            install_python_dev
            disable_swap_permanently
            set_shared_mount
            install_docker
            install_nvidia_container_toolkit
            install_k3s
            install_nvidia_device_plugin
            verify_gpu_in_kubernetes
            ;;
        --cleanup)
            # 执行清理流程
            cleanup
            ;;
        --help)
            # 显示帮助信息
            display_help
            ;;
        *)
            # 默认执行安装流程
            # git config --global url."https://gitclone.com/".insteadOf https://
            # git config --global --unset url."https://gitclone.com/".insteadOf
            check_root
            check_nvidia_driver
            change_to_aliyun_source
            install_python_dev
            disable_swap_permanently
            set_shared_mount
            install_docker
            install_nvidia_container_toolkit
            install_k3s
            install_nvidia_device_plugin
            verify_gpu_in_kubernetes
            ;;
    esac
}

# 执行主函数
main "$@"
