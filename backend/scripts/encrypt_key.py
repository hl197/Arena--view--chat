"""API Key 加密/解密 CLI 工具

用法:
    # 加密一个 Key
    python -m backend.scripts.encrypt_key --key sk-xxx --name DEEPSEEK

    # 迁移现有 .env 中的明文 Key 到加密格式
    python -m backend.scripts.encrypt_key --migrate

    # 生成/替换主密钥
    python -m backend.scripts.encrypt_key --generate-master-key

    # 解密一个值（调试用）
    python -m backend.scripts.encrypt_key --decrypt gAAAAAB...
"""

import os
import sys
import base64
import hashlib
import argparse
from pathlib import Path


# 项目根目录（scripts 的上两级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_KEY_PATH = PROJECT_ROOT / ".env.key"


def load_env():
    """加载 .env 文件"""
    try:
        if ENV_PATH.exists():
            from dotenv import load_dotenv
            load_dotenv(ENV_PATH)
    except ImportError:
        print("⚠️  未安装 python-dotenv，请运行: pip install python-dotenv")
        sys.exit(1)


def get_master_key() -> str:
    """获取或生成主密钥"""
    key = os.getenv("ARENA_MASTER_KEY")
    if not key and ENV_KEY_PATH.exists():
        key = ENV_KEY_PATH.read_text().strip()
    if not key:
        key = _generate_key()
        _persist_master_key(key)
    return key


def _generate_key() -> str:
    """生成 64 字符十六进制主密钥"""
    return os.urandom(32).hex()


def _persist_master_key(key: str):
    """将主密钥持久化到 .env 文件"""
    line = f"\n# === 自动生成 — 加密主密钥，请勿提交到 Git ===\nARENA_MASTER_KEY={key}\n"
    try:
        if ENV_PATH.exists():
            content = ENV_PATH.read_text(encoding="utf-8")
            if "ARENA_MASTER_KEY" in content:
                print("✅ ARENA_MASTER_KEY 已存在于 .env")
                return
            with open(ENV_PATH, "a", encoding="utf-8") as f:
                f.write(line)
        else:
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write(f"# ArenaView 环境配置\n{line}")
        print(f"✅ ARENA_MASTER_KEY 已写入 .env")
    except OSError as e:
        print(f"⚠️  无法写入 .env: {e}")
        print(f"   主密钥（请手动保存）: {key}")


def make_fernet(key_string: str):
    """从字符串创建 Fernet 实例"""
    from cryptography.fernet import Fernet
    fernet_key = base64.urlsafe_b64encode(
        hashlib.sha256(key_string.encode()).digest()
    )
    return Fernet(fernet_key)


def cmd_generate_master_key():
    """生成/替换主密钥"""
    load_env()
    key = _generate_key()
    if ENV_PATH.exists():
        content = ENV_PATH.read_text(encoding="utf-8")
        if "ARENA_MASTER_KEY" in content:
            import re
            old_key = os.getenv("ARENA_MASTER_KEY", "")
            if old_key:
                print(f"⚠️  旧主密钥: {old_key[:8]}...{old_key[-4:]}")
            content = re.sub(
                r'^ARENA_MASTER_KEY=.*$', f'ARENA_MASTER_KEY={key}', content, flags=re.MULTILINE
            )
            ENV_PATH.write_text(content, encoding="utf-8")
            print(f"✅ ARENA_MASTER_KEY 已更新")
        else:
            with open(ENV_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n# === 自动生成 — 加密主密钥 ===\nARENA_MASTER_KEY={key}\n")
            print(f"✅ ARENA_MASTER_KEY 已写入 .env")
    else:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(f"# ArenaView 环境配置\nARENA_MASTER_KEY={key}\n")
        print(f"✅ 已创建 .env 并写入 ARENA_MASTER_KEY")
    print(f"   {key}")


def cmd_encrypt(args):
    """加密一个 API Key"""
    load_env()
    master_key = get_master_key()
    f = make_fernet(master_key)
    plaintext = args.key
    if not plaintext:
        print("❌ 请提供 --key 参数")
        sys.exit(1)
    encrypted = f.encrypt(plaintext.encode()).decode()
    varname = args.name.upper() if args.name else "DEEPSEEK"
    print(f"\n# 复制以下行到 .env 文件：")
    print(f"{varname}_API_KEY_ENC={encrypted}")
    print(f"\n# 如果 .env 中有明文 {varname}_API_KEY，请删除或注释掉")


def cmd_decrypt(args):
    """解密一个值"""
    load_env()
    master_key = get_master_key()
    f = make_fernet(master_key)
    try:
        result = f.decrypt(args.decrypt.encode()).decode()
        print(f"🔓 解密结果: {result}")
    except Exception as e:
        print(f"❌ 解密失败: {e}")
        print("   可能是主密钥不匹配，或密文已损坏")


def cmd_migrate():
    """迁移 .env 中所有明文 API Key 到加密格式"""
    import re

    load_env()
    master_key = get_master_key()
    f = make_fernet(master_key)

    if not ENV_PATH.exists():
        print("❌ .env 文件不存在，无需迁移")
        sys.exit(1)

    content = ENV_PATH.read_text(encoding="utf-8")
    lines = content.split("\n")
    migrated = 0

    for i, line in enumerate(lines):
        match = re.match(r'^(\w*API_KEY)=(sk-\S+)', line)
        if match:
            varname = match.group(1)
            plaintext = match.group(2)
            encrypted = f.encrypt(plaintext.encode()).decode()
            lines[i] = f"# [已迁移] {line}\n{varname}_ENC={encrypted}"
            migrated += 1
            print(f"✅ {varname} → {varname}_ENC")

    if migrated == 0:
        print("ℹ️  .env 中没有找到明文 API Key，无需迁移")
        return

    # 确保 ARENA_MASTER_KEY 存在
    if "ARENA_MASTER_KEY" not in content:
        lines.append(f"\n# === 自动生成 — 加密主密钥 ===\nARENA_MASTER_KEY={master_key}")

    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n🎉 已迁移 {migrated} 个 Key。")
    print(f"   原明文行已注释（前缀 # [已迁移]），确认加密版可用后可手动删除")


def cmd_rekey():
    """更换主密钥并重新加密所有 Key"""
    import re

    load_env()
    old_key = get_master_key()
    new_key = _generate_key()

    if not ENV_PATH.exists():
        print("❌ .env 文件不存在")
        sys.exit(1)

    content = ENV_PATH.read_text(encoding="utf-8")
    lines = content.split("\n")
    rekeyed = 0

    old_fernet = make_fernet(old_key)
    new_fernet = make_fernet(new_key)

    for i, line in enumerate(lines):
        match = re.match(r'^(\w*API_KEY_ENC)=(gAAAAAB.+)', line)
        if match:
            varname = match.group(1)
            ciphertext = match.group(2)
            try:
                plaintext = old_fernet.decrypt(ciphertext.encode()).decode()
                new_ciphertext = new_fernet.encrypt(plaintext.encode()).decode()
                lines[i] = f"{varname}={new_ciphertext}"
                rekeyed += 1
            except Exception:
                print(f"⚠️  无法解密 {varname}，跳过")

    if rekeyed:
        # 更新主密钥
        for i, line in enumerate(lines):
            if line.startswith("ARENA_MASTER_KEY="):
                lines[i] = f"ARENA_MASTER_KEY={new_key}"
                break

        ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
        print(f"✅ 已用新主密钥重新加密 {rekeyed} 个 Key")
    else:
        print("ℹ️  没有找到可重新加密的 Key")


def main():
    parser = argparse.ArgumentParser(
        description="ArenaView API Key 加密/解密工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m backend.scripts.encrypt_key --key sk-abc123          # 加密 DeepSeek Key
  python -m backend.scripts.encrypt_key --key sk-abc --name OPENAI # 加密 OpenAI Key
  python -m backend.scripts.encrypt_key --migrate                  # 一键迁移明文 Key
  python -m backend.scripts.encrypt_key --generate-master-key      # 生成新主密钥
  python -m backend.scripts.encrypt_key --rekey                    # 更换主密钥
  python -m backend.scripts.encrypt_key --decrypt gAAAAAB...       # 解密验证
        """,
    )
    parser.add_argument("--key", help="要加密的明文 API Key")
    parser.add_argument("--name", default="DEEPSEEK", help="Provider 名称前缀（默认 DEEPSEEK）")
    parser.add_argument("--migrate", action="store_true", help="迁移 .env 中所有明文 Key 到加密格式")
    parser.add_argument("--generate-master-key", action="store_true", help="生成/替换主密钥")
    parser.add_argument("--decrypt", help="解密一个加密值（调试用）")
    parser.add_argument("--rekey", action="store_true", help="更换主密钥并重新加密所有 Key")

    args = parser.parse_args()

    if args.migrate:
        cmd_migrate()
    elif args.generate_master_key:
        cmd_generate_master_key()
    elif args.decrypt:
        cmd_decrypt(args)
    elif args.rekey:
        cmd_rekey()
    elif args.key:
        cmd_encrypt(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
