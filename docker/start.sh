#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查docker是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker未安装。请先安装Docker。${NC}"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: Docker Compose未安装。请先安装Docker Compose。${NC}"
    exit 1
fi

# 创建必要的目录
echo -e "${GREEN}创建必要的目录...${NC}"
mkdir -p ../api/logs/processed

# 设置脚本权限
echo -e "${GREEN}设置脚本权限...${NC}"
chmod +x ../api/aistack/scripts/*.sh

# 构建并启动容器
echo -e "${GREEN}构建并启动容器...${NC}"
docker-compose up -d --build

# 检查容器状态
echo -e "${GREEN}检查容器状态...${NC}"
docker-compose ps

echo -e "${GREEN}GalaxyAIOS系统已启动！${NC}"
echo -e "${GREEN}Web界面: http://localhost:12888${NC}"
echo -e "${GREEN}API接口: http://localhost:9999${NC}"
echo -e "${GREEN}默认用户名: admin${NC}"
echo -e "${GREEN}默认密码: admin${NC}" 