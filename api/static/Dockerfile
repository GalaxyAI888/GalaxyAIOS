FROM m.daocloud.io/docker.io/library/nginx:latest

# 复制默认的nginx配置文件（可选）
# COPY nginx.conf /etc/nginx/nginx.conf

# 复制静态文件到nginx默认目录
# COPY ./static /usr/share/nginx/html

# 暴露80端口
EXPOSE 80

# 启动nginx
CMD ["nginx", "-g", "daemon off;"]
