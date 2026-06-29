#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
#  ArenaView 一键启动脚本
#  启动后端 (FastAPI :8000) + 前端 (Vite :5173)
# ──────────────────────────────────────────────────────────
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# ── 颜色 ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

banner() {
  echo -e "${CYAN}"
  echo "   ╔══════════════════════════════════════╗"
  echo "   ║        ArenaView  多视角决策       ║"
  echo "   ╚══════════════════════════════════════╝"
  echo -e "${NC}"
}

# ── 清理函数 ─────────────────────────────────────────
cleanup() {
  echo ""
  echo -e "${YELLOW}🛑 正在关闭服务...${NC}"

  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null
    wait "$BACKEND_PID" 2>/dev/null
    echo -e "${GREEN}   ✓ 后端已关闭${NC}"
  fi

  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null
    wait "$FRONTEND_PID" 2>/dev/null
    echo -e "${GREEN}   ✓ 前端已关闭${NC}"
  fi

  # 清理可能残留的子进程
  if [ -n "$FRONTEND_PID" ]; then
    # Vite 有时会产生子进程，一起杀掉
    pkill -P "$FRONTEND_PID" 2>/dev/null || true
  fi

  echo -e "${GREEN}👋 ArenaView 已停止${NC}"
  exit 0
}

trap cleanup SIGINT SIGTERM

# ── 环境检查 ─────────────────────────────────────────
# 确定 Python 命令（兼容 Windows Store Python / conda / 系统安装）
if command -v python &>/dev/null; then
  PYTHON="python"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
else
  echo -e "${RED}❌ 未找到 Python${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Python:${NC} $($PYTHON --version 2>&1)"

check_deps() {
  local missing=()

  if ! command -v npm &>/dev/null; then
    missing+=("Node.js / npm")
  fi

  if [ ${#missing[@]} -gt 0 ]; then
    echo -e "${RED}❌ 缺少依赖: ${missing[*]}${NC}"
    exit 1
  fi

  echo -e "${GREEN}✓ Python:${NC} $($PYTHON --version 2>&1)"
  echo -e "${GREEN}✓ Node:${NC}   $(node --version)"
  echo -e "${GREEN}✓ npm:${NC}    $(npm --version)"
}

# ── 环境变量 ─────────────────────────────────────────
load_env() {
  # 加载全局 API Key（~/.bashrc）
  if [ -f ~/.bashrc ]; then
    source ~/.bashrc 2>/dev/null || true
  fi

  # 加载项目 .env
  if [ -f "$ROOT_DIR/.env" ]; then
    set -a
    source "$ROOT_DIR/.env"
    set +a
    echo -e "${GREEN}✓ 已加载 .env${NC}"
  else
    echo -e "${YELLOW}⚠ 未找到 .env 文件，请确保 API Key 已配置${NC}"
  fi

  # 检查关键密钥
  if [ -z "$DEEPSEEK_API_KEY" ] && [ -z "$DEEPSEEK_API_KEY_ENC" ]; then
    echo -e "${RED}❌ 未配置 DEEPSEEK_API_KEY 或 DEEPSEEK_API_KEY_ENC${NC}"
    echo -e "   获取: https://platform.deepseek.com/api_keys"
    echo -e "   设置: 在 .env 中写入 DEEPSEEK_API_KEY=sk-xxx"
    exit 1
  fi
}

# ── 安装依赖（如需要） ────────────────────────────────
install_deps() {
  # 后端 Python 依赖（检查关键包是否可导入）
  echo -e "${YELLOW}📦 检查 Python 依赖...${NC}"
  local py_ok=0
  $PYTHON -c "import fastapi, uvicorn, httpx, openai, pydantic, dotenv, cryptography" 2>/dev/null && py_ok=1
  if [ "$py_ok" -eq 1 ]; then
    echo -e "${GREEN}   ✓ Python 依赖已就绪${NC}"
  else
    echo -e "${YELLOW}   ⚠ 部分 Python 包缺失，尝试安装...${NC}"
    $PYTHON -m pip install fastapi uvicorn httpx openai pydantic python-dotenv cryptography python-multipart 2>/dev/null || true
  fi

  # 前端 npm 依赖
  if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${YELLOW}📦 安装前端依赖...${NC}"
    cd "$FRONTEND_DIR" && npm install && {
      echo -e "${GREEN}   ✓ 前端依赖已安装${NC}"
    } || {
      echo -e "${RED}   ❌ npm install 失败${NC}"
      exit 1
    }
    cd "$ROOT_DIR"
  fi
}

# ── 启动服务 ─────────────────────────────────────────
start_backend() {
  echo -e "${CYAN}🔧 启动后端 (FastAPI :8000)...${NC}"

  cd "$ROOT_DIR"
  $PYTHON -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
  BACKEND_PID=$!

  # 等待后端就绪
  echo -ne "   等待后端就绪"
  for i in $(seq 1 20); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
      echo -e "\n${GREEN}   ✓ 后端就绪 (http://localhost:8000)${NC}"
      return 0
    fi
    echo -ne "."
    sleep 0.5
  done

  echo -e "\n${YELLOW}   ⚠ 后端可能未完全启动，继续启动前端...${NC}"
  return 0
}

start_frontend() {
  echo -e "${CYAN}🎨 启动前端 (Vite :5173)...${NC}"

  cd "$FRONTEND_DIR"
  npm run dev &
  FRONTEND_PID=$!
  cd "$ROOT_DIR"

  # 等待前端就绪
  echo -ne "   等待前端就绪"
  for i in $(seq 1 15); do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
      echo -e "\n${GREEN}   ✓ 前端就绪 (http://localhost:5173)${NC}"
      return 0
    fi
    echo -ne "."
    sleep 1
  done

  echo -e "\n${YELLOW}   ⚠ 前端可能未完全启动${NC}"
  return 0
}

# ── 主流程 ───────────────────────────────────────────
main() {
  banner
  echo -e "${CYAN}📋 检查环境...${NC}"
  check_deps
  load_env
  install_deps

  echo ""
  echo -e "${GREEN}🚀 启动 ArenaView...${NC}"
  echo ""

  start_backend
  start_frontend

  echo ""
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${GREEN}  ArenaView 运行中！${NC}"
  echo -e ""
  echo -e "  🌐 前端:  ${CYAN}http://localhost:5173${NC}"
  echo -e "  🔧 后端:  ${CYAN}http://localhost:8000${NC}"
  echo -e "  📚 API:   ${CYAN}http://localhost:8000/docs${NC}"
  echo -e ""
  echo -e "  按 ${YELLOW}Ctrl+C${NC} 停止所有服务"
  echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""

  # 等待任意子进程退出
  wait
}

main
