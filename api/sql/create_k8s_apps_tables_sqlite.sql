-- =====================================================
-- K8s应用表结构创建SQL脚本 (SQLite版本)
-- 创建时间: 2025-10-26
-- 说明: 创建k8s_apps和k8s_app_instances表
-- =====================================================

-- 创建k8s_apps表
CREATE TABLE IF NOT EXISTS k8s_apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    version TEXT NOT NULL DEFAULT '1.0.0',
    icon TEXT,
    user_id INTEGER,
    dockerfile TEXT,
    docker_img_url TEXT,
    img_name TEXT,
    img_tag TEXT NOT NULL DEFAULT 'latest',
    imgsize TEXT,
    deployment TEXT,
    service TEXT,
    configmap TEXT,
    ingress TEXT,
    app_type TEXT NOT NULL DEFAULT 'WEB_APP' CHECK (app_type IN ('WEB_APP', 'API_SERVICE', 'MICROSERVICE', 'WORKLOAD')),
    category TEXT,
    tags TEXT, -- JSON字符串
    status TEXT NOT NULL DEFAULT 'STOPPED' CHECK (status IN ('STOPPED', 'DEPLOYING', 'RUNNING', 'ERROR', 'UPDATING', 'SCALING', 'DELETING')),
    is_active INTEGER NOT NULL DEFAULT 1, -- SQLite使用INTEGER表示BOOLEAN
    is_preset INTEGER NOT NULL DEFAULT 0,
    namespace TEXT NOT NULL DEFAULT 'default',
    replicas INTEGER NOT NULL DEFAULT 1,
    status_message TEXT,
    deployed_at TEXT, -- SQLite使用TEXT存储日期时间
    last_updated_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 创建k8s_app_instances表
CREATE TABLE IF NOT EXISTS k8s_app_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    k8s_app_id INTEGER NOT NULL,
    pod_name TEXT,
    status TEXT NOT NULL DEFAULT 'STOPPED' CHECK (status IN ('STOPPED', 'DEPLOYING', 'RUNNING', 'ERROR', 'UPDATING', 'SCALING', 'DELETING')),
    status_message TEXT,
    started_at TEXT,
    stopped_at TEXT,
    memory_usage TEXT,
    cpu_usage REAL,
    pod_ip TEXT,
    node_name TEXT,
    deployment_name TEXT,
    service_name TEXT,
    namespace TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT,
    FOREIGN KEY (k8s_app_id) REFERENCES k8s_apps(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS ix_k8s_apps_name ON k8s_apps(name);
CREATE INDEX IF NOT EXISTS ix_k8s_apps_user_id ON k8s_apps(user_id);
CREATE INDEX IF NOT EXISTS ix_k8s_app_instances_k8s_app_id ON k8s_app_instances(k8s_app_id);

-- 创建触发器来自动更新updated_at字段
CREATE TRIGGER IF NOT EXISTS update_k8s_apps_updated_at 
    AFTER UPDATE ON k8s_apps
    FOR EACH ROW
    BEGIN
        UPDATE k8s_apps SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

CREATE TRIGGER IF NOT EXISTS update_k8s_app_instances_updated_at 
    AFTER UPDATE ON k8s_app_instances
    FOR EACH ROW
    BEGIN
        UPDATE k8s_app_instances SET updated_at = datetime('now') WHERE id = NEW.id;
    END;

-- 插入测试数据（可选）
INSERT OR IGNORE INTO k8s_apps (
    name, display_name, description, version, icon, user_id,
    dockerfile, docker_img_url, img_name, img_tag, imgsize,
    deployment, service, app_type, category, tags, namespace, replicas
) VALUES (
    'nginx-test',
    'Nginx测试应用',
    '这是一个用于测试的Nginx应用',
    '1.0.0',
    'http://example.com/nginx-icon.png',
    1,
    'http://www.byteverse.vip/aigc1.dockerfile',
    'm.daocloud.io/docker.io/library/nginx',
    'm.daocloud.io/docker.io/library/nginx',
    'latest',
    '20G',
    '{"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "nginx-test", "labels": {"app": "nginx-test"}}, "spec": {"replicas": 1, "selector": {"matchLabels": {"app": "nginx-test"}}, "template": {"metadata": {"labels": {"app": "nginx-test"}}, "spec": {"containers": [{"name": "nginx-test", "image": "m.daocloud.io/docker.io/library/nginx:latest", "ports": [{"containerPort": 80}]}]}}}}',
    '{"apiVersion": "v1", "kind": "Service", "metadata": {"name": "nginx-test-service"}, "spec": {"type": "NodePort", "ports": [{"port": 80, "targetPort": 80, "nodePort": 30080}], "selector": {"app": "nginx-test"}}}',
    'WEB_APP',
    '测试应用',
    '["nginx", "测试", "web"]',
    'default',
    1
);

-- 查看创建的表结构
.schema k8s_apps
.schema k8s_app_instances

-- 查看表数据
SELECT COUNT(*) as k8s_apps_count FROM k8s_apps;
SELECT COUNT(*) as k8s_app_instances_count FROM k8s_app_instances;

-- 查看测试数据
SELECT id, name, display_name, status, created_at FROM k8s_apps;
