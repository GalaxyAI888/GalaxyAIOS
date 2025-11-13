#!/bin/bash

# 定义颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: Docker Compose未安装。请先安装Docker Compose。${NC}"
    exit 1
fi

# 停止容器
echo -e "${GREEN}停止所有容器...${NC}"
docker-compose down

echo -e "${GREEN}GalaxyAIOS系统已停止！${NC}" 