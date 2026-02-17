#!/bin/bash
# 飞书 AI 助手 - 一键部署脚本
# 适用于阿里云 ECS + 免费域名

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 配置变量（可修改）
DOMAIN="${DOMAIN:-assistant.yourdomain.top}"
EMAIL="${EMAIL:-your-email@example.com}"
APP_DIR="${APP_DIR:-/opt/feishu-assistant}"

# 飞书配置（从环境变量读取或使用默认值）
FEISHU_APP_ID="${FEISHU_APP_ID:-cli_a90c14b297f85bcb}"
FEISHU_APP_SECRET="${FEISHU_APP_SECRET:-vhK2lyuiBIzd7W9b9cb8KgN8bMHNLAnU}"
FEISHU_VERIFICATION_TOKEN="${FEISHU_VERIFICATION_TOKEN:-}"
FEISHU_ENCRYPT_KEY="${FEISHU_ENCRYPT_KEY:-}"
FEISHU_USER_OPEN_ID="${FEISHU_USER_OPEN_ID:-ou_58af23946f2fffb4260cbf51f49c9620}"
KIMI_API_KEY="${KIMI_API_KEY:-sk-RnMXCmQBuUgAbSPvYVrHRVeiUzsLhcLG7yNVc5vFr5rIVucK}"
GITHUB_TOKEN="${GITHUB_TOKEN:-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}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "请使用 root 权限运行此脚本"
        exit 1
    fi
}

install_dependencies() {
    log_info "安装系统依赖..."
    apt-get update -qq
    apt-get install -y -qq \
        docker.io \
        docker-compose \
        curl \
        sqlite3 \
        certbot \
        cron \
        git \
        jq
    
    # 启动 Docker
    systemctl enable docker
    systemctl start docker
    
    log_info "依赖安装完成"
}

create_directories() {
    log_info "创建项目目录..."
    mkdir -p ${APP_DIR}/{nginx/{ssl,www/.well-known/acme-challenge,logs},data,logs}
    cd ${APP_DIR}
}

create_env_file() {
    log_info "创建环境变量文件..."
    cat > .env << EOF
# 域名配置
DOMAIN=${DOMAIN}

# 飞书配置
FEISHU_APP_ID=${FEISHU_APP_ID}
FEISHU_APP_SECRET=${FEISHU_APP_SECRET}
FEISHU_VERIFICATION_TOKEN=${FEISHU_VERIFICATION_TOKEN}
FEISHU_ENCRYPT_KEY=${FEISHU_ENCRYPT_KEY}
FEISHU_USER_OPEN_ID=${FEISHU_USER_OPEN_ID}

# API Keys
KIMI_API_KEY=${KIMI_API_KEY}
GITHUB_TOKEN=${GITHUB_TOKEN}

# 数据库
DATABASE_PATH=/app/data/assistant.db
LOG_LEVEL=INFO
EOF
    chmod 600 .env
}

create_docker_compose() {
    log_info "创建 Docker Compose 配置..."
    cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  nginx:
    image: nginx:alpine
    container_name: feishu-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - ./nginx/www:/var/www/certbot:ro
      - ./nginx/logs:/var/log/nginx
    depends_on:
      - assistant
    networks:
      - assistant-net
    restart: always
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  certbot:
    image: certbot/certbot
    container_name: feishu-certbot
    volumes:
      - ./nginx/ssl:/etc/letsencrypt
      - ./nginx/www:/var/www/certbot
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew --quiet --deploy-hook \"docker restart feishu-nginx\"; sleep 12h; done'"
    networks:
      - assistant-net
    restart: always

  assistant:
    build: 
      context: ./assistant
      dockerfile: Dockerfile
    image: feishu-assistant:latest
    container_name: feishu-assistant
    expose:
      - "8000"
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    networks:
      - assistant-net
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

networks:
  assistant-net:
    driver: bridge
EOF
}

create_nginx_config() {
    log_info "创建 Nginx 配置..."
    cat > nginx/nginx.conf << 'EOF'
server {
    listen 80;
    server_name _;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$host$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate /etc/nginx/ssl/live/assistant/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/live/assistant/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;

    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log warn;

    location /webhook/feishu {
        proxy_pass http://assistant:8000/webhook/feishu;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 10s;
        proxy_send_timeout 10s;
        proxy_read_timeout 15s;
    }

    location /health {
        proxy_pass http://assistant:8000/health;
        access_log off;
    }

    location / {
        return 404;
    }
}
EOF
}

create_application_code() {
    log_info "创建应用代码..."
    
    # 创建目录结构
    mkdir -p assistant/app/{db,core,handlers,services,tools}
    
    # requirements.txt
    cat > assistant/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
httpx==0.25.2
python-multipart==0.0.6
openai==1.3.0
pydantic-settings==2.1.0
aiofiles==23.2.1
cryptography==41.0.7
EOF

    # Dockerfile
    cat > assistant/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY app/ ./app/

# 创建数据目录
RUN mkdir -p /app/data /app/logs

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
EOF

    # 应用主文件
    create_main_py
    create_config_py
    create_database_py
    create_security_py
    create_events_py
    create_command_handler_py
    create_message_handler_py
    create_feishu_service_py
    create_tools
}

create_main_py() {
    cat > assistant/app/main.py << 'EOF'
"""
Feishu AI Assistant - FastAPI Main Application
"""
from fastapi import FastAPI, Request, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import json

from app.config import get_settings
from app.db.database import Database
from app.core.events import EventDispatcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    print("🚀 Feishu AI Assistant 启动中...")
    await Database.init()
    print("✅ 数据库初始化完成")
    yield
    # 关闭
    print("🛑 应用关闭")


app = FastAPI(
    title="Feishu AI Assistant",
    description="飞书 AI 个人助手",
    version="1.0.0",
    lifespan=lifespan
)

# 事件分发器
dispatcher = EventDispatcher()


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "ok",
        "service": "feishu-assistant",
        "version": "1.0.0"
    }


@app.post("/webhook/feishu")
async def feishu_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    接收飞书事件推送
    文档: https://open.feishu.cn/document/server-docs/im-v1/message/events/receive
    """
    try:
        body = await request.body()
        data = await request.json()
        
        # 1. URL 验证（首次配置事件订阅时使用）
        if data.get("type") == "url_verification":
            challenge = data.get("challenge")
            log_info(f"收到 URL 验证请求: challenge={challenge}")
            return {"challenge": challenge}
        
        # 2. 解析事件
        header = data.get("header", {})
        event_type = header.get("event_type")
        
        # 只处理消息事件
        if event_type != "im.message.receive_v1":
            return JSONResponse(content={"code": 0})
        
        event = data.get("event", {})
        message = event.get("message", {})
        
        # 提取关键信息
        user_id = event.get("sender", {}).get("sender_id", {}).get("union_id", "")
        message_id = message.get("message_id", "")
        msg_type = message.get("message_type", "")
        chat_type = message.get("chat_type", "")  # "p2p" 私聊, "group" 群聊
        
        # 解析消息内容
        content = {}
        try:
            content = json.loads(message.get("content", "{}"))
        except:
            pass
        
        text = content.get("text", "").strip()
        
        log_info(f"收到消息: user={user_id}, type={msg_type}, chat={chat_type}, text={text[:50]}")
        
        # 3. 消息去重检查
        if await Database.is_message_processed(message_id):
            log_info(f"消息已处理，跳过: {message_id}")
            return JSONResponse(content={"code": 0})
        
        await Database.mark_message_processed(message_id)
        
        # 4. 异步处理消息（不阻塞响应）
        background_tasks.add_task(
            dispatcher.process_message,
            user_id=user_id,
            message_id=message_id,
            text=text,
            chat_type=chat_type,
            msg_type=msg_type
        )
        
        # 立即返回（飞书要求 10 秒内响应）
        return JSONResponse(content={"code": 0})
        
    except Exception as e:
        log_error(f"处理 webhook 失败: {e}")
        return JSONResponse(content={"code": 0})  # 即使出错也返回成功，避免飞书重试


def log_info(msg: str):
    print(f"[INFO] {msg}")


def log_error(msg: str):
    print(f"[ERROR] {msg}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
}

create_config_py() {
    cat > assistant/app/config.py << 'EOF'
"""
配置管理
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置"""
    
    # 飞书配置
    FEISHU_APP_ID: str
    FEISHU_APP_SECRET: str
    FEISHU_VERIFICATION_TOKEN: str = ""
    FEISHU_ENCRYPT_KEY: str = ""  # 可选，用于加密
    FEISHU_USER_OPEN_ID: str = ""  # 默认接收者
    
    # API Keys
    KIMI_API_KEY: str
    GITHUB_TOKEN: str = ""
    
    # 数据库
    DATABASE_PATH: str = "/app/data/assistant.db"
    
    # 日志
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
EOF
}

create_database_py() {
    cat > assistant/app/db/database.py << 'EOF'
"""
SQLite 数据库管理
会话、消息、任务存储
"""
import sqlite3
import json
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


class Database:
    """异步 SQLite 数据库管理"""
    
    _db_path: str = "/app/data/assistant.db"
    
    @classmethod
    def set_db_path(cls, path: str):
        cls._db_path = path
    
    @classmethod
    async def init(cls):
        """初始化数据库表"""
        async with aiosqlite.connect(cls._db_path) as db:
            await db.executescript("""
                -- 会话上下文表
                CREATE TABLE IF NOT EXISTS sessions (
                    user_id TEXT PRIMARY KEY,
                    context TEXT DEFAULT '{}',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 消息去重表
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- 任务记录表
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    params TEXT DEFAULT '{}',
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                );
                
                -- 创建索引
                CREATE INDEX IF NOT EXISTS idx_messages_time ON processed_messages(created_at);
                CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            """)
            await db.commit()
    
    @classmethod
    async def is_message_processed(cls, message_id: str) -> bool:
        """检查消息是否已处理"""
        async with aiosqlite.connect(cls._db_path) as db:
            async with db.execute(
                "SELECT 1 FROM processed_messages WHERE message_id = ?",
                (message_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return True
                
                # 记录消息
                await db.execute(
                    "INSERT INTO processed_messages (message_id) VALUES (?)",
                    (message_id,)
                )
                await db.commit()
                
                # 清理过期消息（7天前）
                await db.execute(
                    "DELETE FROM processed_messages WHERE created_at < ?",
                    (datetime.now() - timedelta(days=7),)
                )
                await db.commit()
                return False
    
    @classmethod
    async def mark_message_processed(cls, message_id: str):
        """标记消息已处理"""
        async with aiosqlite.connect(cls._db_path) as db:
            await db.execute(
                """INSERT OR IGNORE INTO processed_messages (message_id) VALUES (?)""",
                (message_id,)
            )
            await db.commit()
    
    @classmethod
    async def get_session(cls, user_id: str) -> Dict[str, Any]:
        """获取用户会话"""
        async with aiosqlite.connect(cls._db_path) as db:
            async with db.execute(
                "SELECT context FROM sessions WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return {"history": [], "state": {}}
    
    @classmethod
    async def update_session(cls, user_id: str, context: Dict[str, Any]):
        """更新用户会话"""
        # 限制历史记录长度
        history = context.get("history", [])
        if len(history) > 20:
            context["history"] = history[-20:]
        
        async with aiosqlite.connect(cls._db_path) as db:
            await db.execute(
                """INSERT INTO sessions (user_id, context, updated_at) 
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(user_id) DO UPDATE SET
                   context = excluded.context,
                   updated_at = excluded.updated_at""",
                (user_id, json.dumps(context))
            )
            await db.commit()
    
    @classmethod
    async def clear_session(cls, user_id: str):
        """清除用户会话"""
        async with aiosqlite.connect(cls._db_path) as db:
            await db.execute(
                "DELETE FROM sessions WHERE user_id = ?",
                (user_id,)
            )
            await db.commit()
    
    @classmethod
    async def create_task(cls, task_id: str, user_id: str, task_type: str, params: Dict) -> str:
        """创建任务"""
        async with aiosqlite.connect(cls._db_path) as db:
            await db.execute(
                """INSERT INTO tasks (task_id, user_id, task_type, status, params)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (task_id, user_id, task_type, json.dumps(params))
            )
            await db.commit()
        return task_id
    
    @classmethod
    async def update_task(cls, task_id: str, status: str, result: Any = None, error: str = None):
        """更新任务状态"""
        async with aiosqlite.connect(cls._db_path) as db:
            if status in ["completed", "failed"]:
                await db.execute(
                    """UPDATE tasks 
                       SET status = ?, result = ?, error = ?, completed_at = CURRENT_TIMESTAMP
                       WHERE task_id = ?""",
                    (status, json.dumps(result) if result else None, error, task_id)
                )
            else:
                await db.execute(
                    "UPDATE tasks SET status = ? WHERE task_id = ?",
                    (status, task_id)
                )
            await db.commit()
    
    @classmethod
    async def get_task(cls, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        async with aiosqlite.connect(cls._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {
                        "task_id": row["task_id"],
                        "user_id": row["user_id"],
                        "task_type": row["task_type"],
                        "status": row["status"],
                        "params": json.loads(row["params"]) if row["params"] else {},
                        "result": json.loads(row["result"]) if row["result"] else None,
                        "error": row["error"],
                        "created_at": row["created_at"],
                        "completed_at": row["completed_at"]
                    }
                return None
EOF
}

create_security_py() {
    cat > assistant/app/core/security.py << 'EOF'
"""
飞书签名验证
文档: https://open.feishu.cn/document/ukTMukTMukTM/uYDNxYjL2UTM24iN1EjN/event-security-verification
"""
import base64
import hmac
import hashlib
from typing import Optional


class FeishuVerifier:
    """飞书请求验证器"""
    
    def __init__(self, encrypt_key: str = "", verification_token: str = ""):
        self.encrypt_key = encrypt_key
        self.verification_token = verification_token
    
    def verify_signature(self, body: bytes, signature: str, timestamp: str, nonce: str) -> bool:
        """
        验证请求签名
        
        Args:
            body: 请求体字节
            signature: 请求头中的 X-Lark-Signature
            timestamp: 请求头中的 X-Lark-Request-Timestamp
            nonce: 请求头中的 X-Lark-Request-Nonce
        
        Returns:
            签名是否有效
        """
        if not self.encrypt_key:
            # 未配置密钥，跳过验证
            return True
        
        try:
            # 拼接字符串
            raw_string = timestamp + nonce + self.encrypt_key + body.decode('utf-8')
            
            # SHA256 哈希
            computed = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()
            
            return computed == signature
        except Exception as e:
            print(f"签名验证失败: {e}")
            return False
    
    def decrypt(self, encrypt_data: str) -> Optional[str]:
        """
        解密飞书加密消息（如启用加密）
        
        Args:
            encrypt_data: 加密数据
        
        Returns:
            解密后的字符串
        """
        if not self.encrypt_key:
            return None
        
        try:
            # Base64 解码
            decode = base64.b64decode(encrypt_data)
            
            # 前 16 字节是 IV
            iv = decode[:16]
            ciphertext = decode[16:]
            
            # AES-256-CBC 解密（需要 cryptography 库）
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            # 从密钥派生 32 字节 AES 密钥
            key = hashlib.sha256(self.encrypt_key.encode()).digest()
            
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            # 移除 PKCS7 填充
            pad_len = plaintext[-1]
            return plaintext[:-pad_len].decode('utf-8')
            
        except Exception as e:
            print(f"解密失败: {e}")
            return None
EOF
}

create_events_py() {
    cat > assistant/app/core/events.py << 'EOF'
"""
事件处理分发器
"""
import asyncio
from typing import Dict, Any

from app.db.database import Database
from app.handlers.command import CommandHandler
from app.handlers.message import MessageHandler
from app.services.feishu import FeishuService


class EventDispatcher:
    """事件分发器"""
    
    def __init__(self):
        self.command_handler = CommandHandler()
        self.message_handler = MessageHandler()
        self.feishu = FeishuService()
    
    async def process_message(self, user_id: str, message_id: str, text: str, 
                             chat_type: str, msg_type: str):
        """
        处理用户消息
        
        Args:
            user_id: 用户唯一标识
            message_id: 消息唯一标识
            text: 消息文本内容
            chat_type: "p2p" 私聊 或 "group" 群聊
            msg_type: 消息类型
        """
        try:
            print(f"处理消息: user={user_id}, text={text}")
            
            # 获取用户会话
            session = await Database.get_session(user_id)
            
            # 更新历史记录
            session["history"].append({
                "role": "user",
                "content": text,
                "time": Database._now()
            })
            
            # 判断处理模式
            if text.startswith("/"):
                # 命令模式
                response = await self.command_handler.handle(text, user_id, session)
            else:
                # 自然语言模式（Phase 2 实现 AI 规划）
                response = await self.message_handler.handle(text, user_id, session)
            
            # 更新会话（包含助手回复）
            session["history"].append({
                "role": "assistant",
                "content": response.get("content", "")[:200],
                "time": Database._now()
            })
            await Database.update_session(user_id, session)
            
            # 发送回复
            await self.feishu.send_message(user_id, response)
            
        except Exception as e:
            print(f"处理消息失败: {e}")
            # 发送错误提示
            await self.feishu.send_text(user_id, "❌ 处理失败，请稍后重试")
    
    @staticmethod
    def _now():
        from datetime import datetime
        return datetime.now().isoformat()
EOF
}

create_command_handler_py() {
    cat > assistant/app/handlers/command.py << 'EOF'
"""
命令处理器
支持 /market /github /paper /help /cancel 等命令
"""
import re
from typing import Dict, Any, Callable
from datetime import datetime

from app.services.feishu import FeishuService
from app.tools.market import MarketTool
from app.tools.github import GitHubTool
from app.tools.paper import PaperTool
from app.db.database import Database


class CommandHandler:
    """命令处理器"""
    
    def __init__(self):
        self.feishu = FeishuService()
        self.market_tool = MarketTool()
        self.github_tool = GitHubTool()
        self.paper_tool = PaperTool()
        
        # 命令映射表
        self.commands: Dict[str, Callable] = {
            "/market": self.handle_market,
            "/m": self.handle_market,
            "/github": self.handle_github,
            "/gh": self.handle_github,
            "/paper": self.handle_paper,
            "/arxiv": self.handle_paper,
            "/help": self.handle_help,
            "/h": self.handle_help,
            "/start": self.handle_start,
            "/cancel": self.handle_cancel,
            "/clear": self.handle_clear,
            "/status": self.handle_status,
        }
    
    async def handle(self, text: str, user_id: str, session: Dict) -> Dict[str, Any]:
        """
        处理命令
        
        Returns:
            {"type": "text|card", "content": "..."}
        """
        # 解析命令和参数
        parts = text.strip().split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # 查找处理器
        handler = self.commands.get(command, self.handle_unknown)
        
        return await handler(args, user_id, session)
    
    async def handle_market(self, args: str, user_id: str, session: Dict) -> Dict:
        """查询市场行情"""
        # 解析参数
        markets = []
        if not args or "us" in args.lower() or "美" in args:
            markets.append("US")
        if not args or "hk" in args.lower() or "港" in args:
            markets.append("HK")
        if not args or "cn" in args.lower() or "a" in args.lower() or "中" in args:
            markets.append("CN")
        
        if not markets:
            markets = ["US"]  # 默认
        
        # 发送正在处理提示
        await self.feishu.send_text(user_id, f"🔄 正在查询 {', '.join(markets)} 市场行情...")
        
        try:
            # 查询数据
            data = await self.market_tool.query(markets)
            
            # 格式化回复
            return {
                "type": "card",
                "content": self._format_market_card(data)
            }
        except Exception as e:
            print(f"查询市场失败: {e}")
            return {
                "type": "text",
                "content": f"❌ 查询失败: {str(e)}"
            }
    
    def _format_market_card(self, data: Dict) -> Dict:
        """格式化市场行情卡片"""
        elements = []
        
        # 标题
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📊 市场行情** {datetime.now().strftime('%m-%d %H:%M')}"
            }
        })
        elements.append({"tag": "hr"})
        
        # 美股
        if "US" in data:
            us = data["US"]
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**🇺🇸 美股**\n{self._format_index(us.get('indices', {}))}"
                }
            })
        
        # 港股
        if "HK" in data:
            hk = data["HK"]
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**🇭🇰 港股**\n{self._format_index(hk.get('indices', {}))}"
                }
            })
        
        # A股
        if "CN" in data:
            cn = data["CN"]
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**🇨🇳 A股**\n{self._format_index(cn.get('indices', {}))}"
                }
            })
        
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": "💡 发送 `/market US` 仅查看美股"
            }
        })
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📊 市场行情"},
                "template": "blue"
            },
            "elements": elements
        }
    
    def _format_index(self, indices: Dict) -> str:
        """格式化指数数据"""
        lines = []
        for name, info in indices.items():
            change = info.get("change", 0)
            emoji = "🟢" if change >= 0 else "🔴"
            lines.append(f"{emoji} {name}: {info.get('price', '-')} ({change:+.2f}%)")
        return "\n".join(lines) if lines else "暂无数据"
    
    async def handle_github(self, args: str, user_id: str, session: Dict) -> Dict:
        """查询 GitHub 趋势"""
        keywords = args.split() if args else ["ai-agent"]
        
        await self.feishu.send_text(user_id, f"🔄 正在搜索 GitHub 趋势: {', '.join(keywords)}")
        
        try:
            repos = await self.github_tool.search_trending(keywords)
            
            if not repos:
                return {
                    "type": "text",
                    "content": "未找到相关项目"
                }
            
            return {
                "type": "card",
                "content": self._format_github_card(repos, keywords)
            }
        except Exception as e:
            return {
                "type": "text",
                "content": f"❌ 搜索失败: {str(e)}"
            }
    
    def _format_github_card(self, repos: list, keywords: list) -> Dict:
        """格式化 GitHub 卡片"""
        elements = [{
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**🚀 GitHub 趋势** - 关键词: {', '.join(keywords)}"
            }
        }, {"tag": "hr"}]
        
        for repo in repos[:5]:  # 最多显示 5 个
            name = repo.get("full_name", "")
            desc = repo.get("description", "无描述")[:100]
            stars = repo.get("stargazers_count", 0)
            url = repo.get("html_url", "")
            
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**[{name}]({url})** ⭐ {stars}\n{desc}"
                }
            })
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🚀 GitHub 趋势"},
                "template": "indigo"
            },
            "elements": elements
        }
    
    async def handle_paper(self, args: str, user_id: str, session: Dict) -> Dict:
        """搜索论文"""
        topic = args if args else "AI Agent"
        
        await self.feishu.send_text(user_id, f"🔄 正在搜索论文: {topic}")
        
        try:
            papers = await self.paper_tool.search(topic, max_results=5)
            
            if not papers:
                return {
                    "type": "text",
                    "content": "未找到相关论文"
                }
            
            return {
                "type": "card",
                "content": self._format_paper_card(papers, topic)
            }
        except Exception as e:
            return {
                "type": "text",
                "content": f"❌ 搜索失败: {str(e)}"
            }
    
    def _format_paper_card(self, papers: list, topic: str) -> Dict:
        """格式化论文卡片"""
        elements = [{
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**📄 arXiv 论文** - 主题: {topic}"
            }
        }, {"tag": "hr"}]
        
        for paper in papers:
            title = paper.get("title", "")
            authors = ", ".join(paper.get("authors", [])[:3])
            url = paper.get("url", "")
            
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**[{title}]({url})**\n👤 {authors}"
                }
            })
        
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "📄 arXiv 论文"},
                "template": "green"
            },
            "elements": elements
        }
    
    async def handle_help(self, args: str, user_id: str, session: Dict) -> Dict:
        """帮助信息"""
        help_text = """🤖 **飞书 AI 助手使用指南**

**快速命令：**
• `/market` 或 `/m` - 查询市场行情（美/港/A股）
  例: `/market US` 仅查看美股

• `/github` 或 `/gh` - 搜索 GitHub 趋势项目
  例: `/github ai-agent`

• `/paper` 或 `/arxiv` - 搜索 arXiv 论文
  例: `/paper transformer`

• `/clear` - 清除会话历史
• `/status` - 查看系统状态
• `/help` 或 `/h` - 显示帮助

**自然语言（即将支持）：**
直接输入问题，AI 将自动理解并执行

💡 **提示：** 所有命令支持简写，如 `/m` = `/market`
"""
        return {
            "type": "text",
            "content": help_text
        }
    
    async def handle_start(self, args: str, user_id: str, session: Dict) -> Dict:
        """开始/欢迎"""
        return {
            "type": "text",
            "content": "👋 欢迎使用飞书 AI 助手！\n\n发送 `/help` 查看使用指南"
        }
    
    async def handle_cancel(self, args: str, user_id: str, session: Dict) -> Dict:
        """取消当前操作"""
        return {
            "type": "text",
            "content": "✅ 已取消"
        }
    
    async def handle_clear(self, args: str, user_id: str, session: Dict) -> Dict:
        """清除会话"""
        await Database.clear_session(user_id)
        return {
            "type": "text",
            "content": "🗑️ 会话历史已清除"
        }
    
    async def handle_status(self, args: str, user_id: str, session: Dict) -> Dict:
        """系统状态"""
        from app.config import get_settings
        
        settings = get_settings()
        
        status_text = f"""📊 **系统状态**

✅ 服务运行正常
🤖 机器人: {settings.FEISHU_APP_ID[:15]}...
🧠 AI: Kimi (Moonshot)
💾 数据库: SQLite

发送 `/help` 查看可用命令
"""
        return {
            "type": "text",
            "content": status_text
        }
    
    async def handle_unknown(self, args: str, user_id: str, session: Dict) -> Dict:
        """未知命令"""
        return {
            "type": "text",
            "content": f"❓ 未知命令，发送 `/help` 查看可用命令"
        }
EOF
}

create_message_handler_py() {
    cat > assistant/app/handlers/message.py << 'EOF'
"""
自然语言消息处理器
Phase 1: 简单回复，提示使用命令
Phase 2: 集成 AI 规划
"""
from typing import Dict, Any


class MessageHandler:
    """自然语言消息处理器"""
    
    def __init__(self):
        pass
    
    async def handle(self, text: str, user_id: str, session: Dict) -> Dict[str, Any]:
        """
        处理自然语言消息
        
        Phase 1: 识别简单意图并提示使用命令
        Phase 2: 使用 LLM 进行意图识别和任务规划
        """
        text_lower = text.lower()
        
        # 简单意图识别
        if any(kw in text_lower for kw in ["市场", "股票", "行情", "涨", "跌", "美股", "港股"]):
            return {
                "type": "text",
                "content": "📊 查询市场行情请使用命令：`/market` 或 `/m`\n\n例：`/market US` 查看美股"
            }
        
        if any(kw in text_lower for kw in ["github", "项目", "开源", "代码", "仓库"]):
            return {
                "type": "text",
                "content": "🚀 搜索 GitHub 请使用命令：`/github` 或 `/gh`\n\n例：`/github ai-agent`"
            }
        
        if any(kw in text_lower for kw in ["论文", "arxiv", "研究", "学术", "文献"]):
            return {
                "type": "text",
                "content": "📄 搜索论文请使用命令：`/paper` 或 `/arxiv`\n\n例：`/paper transformer`"
            }
        
        if any(kw in text_lower for kw in ["帮助", "怎么用", "help", "?"]):
            return {
                "type": "text",
                "content": "发送 `/help` 查看完整使用指南"
            }
        
        # 默认回复
        return {
            "type": "text",
            "content": f"🤖 收到: \"{text[:50]}...\"\n\n我是飞书 AI 助手，目前支持以下命令：\n\n• `/market` - 查询市场行情\n• `/github` - 搜索 GitHub 趋势\n• `/paper` - 搜索学术论文\n• `/help` - 查看帮助\n\n💡 Phase 2 将支持自然语言直接对话"
        }
EOF
}

create_feishu_service_py() {
    cat > assistant/app/services/feishu.py << 'EOF'
"""
飞书 API 封装
文档: https://open.feishu.cn/document/server-docs/im-v1/message/create
"""
import httpx
import json
from typing import Dict, Any, Optional

from app.config import get_settings


class FeishuService:
    """飞书服务"""
    
    BASE_URL = "https://open.feishu.cn/open-apis"
    
    def __init__(self):
        self.settings = get_settings()
        self._tenant_token: Optional[str] = None
    
    async def _get_tenant_token(self) -> str:
        """获取 tenant access token"""
        if self._tenant_token:
            return self._tenant_token
        
        url = f"{self.BASE_URL}/auth/v3/tenant_access_token/internal"
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={
                "app_id": self.settings.FEISHU_APP_ID,
                "app_secret": self.settings.FEISHU_APP_SECRET
            })
            data = resp.json()
        
        if data.get("code") != 0:
            raise Exception(f"获取 token 失败: {data.get('msg')}")
        
        self._tenant_token = data["tenant_access_token"]
        return self._tenant_token
    
    async def send_message(self, user_id: str, message: Dict[str, Any]):
        """
        发送消息
        
        Args:
            user_id: 用户 open_id
            message: {"type": "text|card", "content": "..."}
        """
        token = await self._get_tenant_token()
        url = f"{self.BASE_URL}/im/v1/messages"
        
        # 构建消息内容
        msg_type = message.get("type", "text")
        content = message.get("content", {})
        
        if msg_type == "text":
            post_data = {
                "receive_id": user_id,
                "msg_type": "text",
                "content": json.dumps({"text": content})
            }
        elif msg_type == "card":
            post_data = {
                "receive_id": user_id,
                "msg_type": "interactive",
                "content": json.dumps(content)
            }
        else:
            raise ValueError(f"不支持的消息类型: {msg_type}")
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={"receive_id_type": "open_id"},
                json=post_data,
                timeout=30.0
            )
            data = resp.json()
        
        if data.get("code") != 0:
            print(f"发送消息失败: {data.get('msg')}")
            raise Exception(f"发送消息失败: {data.get('msg')}")
        
        print(f"消息发送成功: {data.get('data', {}).get('message_id', 'unknown')}")
    
    async def send_text(self, user_id: str, text: str):
        """发送文本消息（快捷方法）"""
        await self.send_message(user_id, {"type": "text", "content": text})
    
    async def send_card(self, user_id: str, card_content: Dict):
        """发送卡片消息（快捷方法）"""
        await self.send_message(user_id, {"type": "card", "content": card_content})
EOF
}

create_tools() {
    # Market Tool
    cat > assistant/app/tools/market.py << 'EOF'
"""
市场行情查询工具
使用 Yahoo Finance API
"""
import httpx
from typing import List, Dict, Any


class MarketTool:
    """市场数据工具"""
    
    # 指数代码映射
    INDICES = {
        "US": {
            "标普500": "^GSPC",
            "纳斯达克": "^IXIC",
            "道琼斯": "^DJI"
        },
        "HK": {
            "恒生指数": "^HSI",
            "恒生科技": "^HSTECH"
        },
        "CN": {
            "上证指数": "000001.SS",
            "深证成指": "399001.SZ",
            "创业板指": "399006.SZ"
        }
    }
    
    async def query(self, markets: List[str]) -> Dict[str, Any]:
        """查询市场行情"""
        result = {}
        
        for market in markets:
            if market.upper() not in self.INDICES:
                continue
            
            indices = {}
            for name, symbol in self.INDICES[market.upper()].items():
                try:
                    data = await self._fetch_yahoo(symbol)
                    indices[name] = data
                except Exception as e:
                    print(f"获取 {name} 失败: {e}")
                    indices[name] = {"price": "-", "change": 0}
            
            result[market.upper()] = {"indices": indices}
        
        return result
    
    async def _fetch_yahoo(self, symbol: str) -> Dict:
        """从 Yahoo Finance 获取数据"""
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }, timeout=10.0)
            data = resp.json()
        
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        
        # 计算涨跌幅
        prev_close = meta.get("previousClose", 0)
        current = meta.get("regularMarketPrice", 0)
        
        change = 0
        if prev_close > 0:
            change = ((current - prev_close) / prev_close) * 100
        
        return {
            "price": round(current, 2),
            "change": round(change, 2),
            "symbol": symbol
        }
EOF

    # GitHub Tool
    cat > assistant/app/tools/github.py << 'EOF'
"""
GitHub 趋势查询工具
"""
import httpx
from typing import List, Dict, Any
from datetime import datetime, timedelta

from app.config import get_settings


class GitHubTool:
    """GitHub 工具"""
    
    async def search_trending(self, keywords: List[str], days: int = 7) -> List[Dict]:
        """搜索热门项目"""
        settings = get_settings()
        
        # 构建查询
        date_since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query = " OR ".join(keywords)
        
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"({query}) stars:>10 pushed:>{date_since}",
            "sort": "stars",
            "order": "desc",
            "per_page": 10
        }
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Feishu-Assistant"
        }
        
        # 使用 GitHub Token（如果有）
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=30.0)
            
            if resp.status_code == 403:
                raise Exception("GitHub API 速率限制，请配置 GITHUB_TOKEN")
            
            resp.raise_for_status()
            data = resp.json()
        
        return data.get("items", [])
EOF

    # Paper Tool
    cat > assistant/app/tools/paper.py << 'EOF'
"""
arXiv 论文搜索工具
"""
import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any


class PaperTool:
    """论文搜索工具"""
    
    BASE_URL = "http://export.arxiv.org/api/query"
    
    async def search(self, topic: str, max_results: int = 5) -> List[Dict]:
        """搜索论文"""
        params = {
            "search_query": f"all:{topic}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending"
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.BASE_URL, params=params, timeout=30.0)
            resp.raise_for_status()
            xml_data = resp.text
        
        return self._parse_arxiv_xml(xml_data)
    
    def _parse_arxiv_xml(self, xml_data: str) -> List[Dict]:
        """解析 arXiv XML"""
        papers = []
        
        # 注册命名空间
        namespaces = {
            'atom': 'http://www.w3.org/2005/Atom',
            'arxiv': 'http://arxiv.org/schemas/atom'
        }
        
        root = ET.fromstring(xml_data)
        
        for entry in root.findall('atom:entry', namespaces):
            paper = {}
            
            # 标题
            title = entry.find('atom:title', namespaces)
            paper['title'] = title.text.strip() if title is not None else "No title"
            
            # 作者
            authors = []
            for author in entry.findall('atom:author', namespaces):
                name = author.find('atom:name', namespaces)
                if name is not None:
                    authors.append(name.text)
            paper['authors'] = authors
            
            # 链接
            paper['url'] = ""
            for link in entry.findall('atom:link', namespaces):
                if link.get('type') == 'text/html':
                    paper['url'] = link.get('href', '')
                    break
            
            # 摘要
            summary = entry.find('atom:summary', namespaces)
            paper['summary'] = summary.text.strip()[:200] + "..." if summary is not None else ""
            
            papers.append(paper)
        
        return papers
EOF

    # Init files
    touch assistant/app/{db,core,handlers,services,tools}/__init__.py
}

# 主部署流程
main() {
    check_root
    
    log_info "开始部署飞书 AI 助手..."
    log_info "域名: ${DOMAIN}"
    log_info "部署目录: ${APP_DIR}"
    
    install_dependencies
    create_directories
    create_env_file
    create_docker_compose
    create_nginx_config
    create_application_code
    
    log_info "代码创建完成，启动服务..."
    
    # 启动服务（HTTP 模式，用于 SSL 验证）
    docker-compose up -d nginx
    
    # 等待 Nginx 启动
    sleep 3
    
    # 申请 SSL 证书
    log_info "申请 SSL 证书..."
    if certbot certonly --webroot \
        -w ${APP_DIR}/nginx/www \
        -d ${DOMAIN} \
        --agree-tos \
        -m ${EMAIL} \
        --non-interactive 2>/dev/null; then
        
        # 复制证书
        mkdir -p ${APP_DIR}/nginx/ssl/live/assistant
        cp /etc/letsencrypt/live/${DOMAIN}/fullchain.pem ${APP_DIR}/nginx/ssl/live/assistant/ 2>/dev/null || true
        cp /etc/letsencrypt/live/${DOMAIN}/privkey.pem ${APP_DIR}/nginx/ssl/live/assistant/ 2>/dev/null || true
        
        # 如果没有 live 目录，尝试 archive
        if [ ! -f "${APP_DIR}/nginx/ssl/live/assistant/fullchain.pem" ]; then
            cp /etc/letsencrypt/archive/${DOMAIN}/*1.pem ${APP_DIR}/nginx/ssl/live/assistant/ 2>/dev/null || true
        fi
        
        log_info "SSL 证书申请成功"
    else
        log_warn "SSL 证书申请失败，将使用 HTTP 模式（飞书要求 HTTPS）"
        log_warn "请检查域名解析是否正确指向本服务器 IP"
    fi
    
    # 重新启动所有服务
    docker-compose down
    docker-compose up -d --build
    
    # 设置证书自动续期
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'docker restart feishu-nginx'") | crontab -
    
    # 等待服务启动
    log_info "等待服务启动..."
    sleep 5
    
    # 健康检查
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        log_info "✅ 服务启动成功！"
    else
        log_warn "⚠️  服务可能未完全启动，查看日志: docker-compose logs"
    fi
    
    echo ""
    echo "========================================"
    log_info "部署完成！"
    echo "========================================"
    echo ""
    echo "🌐 访问地址:"
    echo "  HTTP:  http://${DOMAIN}"
    echo "  HTTPS: https://${DOMAIN}"
    echo ""
    echo "🔗 Webhook URL:"
    echo "  https://${DOMAIN}/webhook/feishu"
    echo ""
    echo "📋 常用命令:"
    echo "  查看日志: cd ${APP_DIR} && docker-compose logs -f"
    echo "  重启服务: cd ${APP_DIR} && docker-compose restart"
    echo "  更新代码: cd ${APP_DIR} && docker-compose up -d --build"
    echo ""
    echo "⚠️  请确保在飞书平台配置以下信息:"
    echo "  1. 事件订阅 URL: https://${DOMAIN}/webhook/feishu"
    echo "  2. 事件类型: im.message.receive_v1"
    echo "  3. 权限: 给应用发送单聊/群聊消息"
    echo ""
}

# 运行
main "$@"
