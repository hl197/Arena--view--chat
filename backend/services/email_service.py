"""邮件服务——QQ SMTP 发送验证码（纯标准库，零新依赖）"""

import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr


class EmailService:
    """邮件发送服务

    使用 QQ 邮箱 SMTP (smtp.qq.com:587, STARTTLS)。
    授权码获取: QQ邮箱 → 设置 → 账户 → POP3/SMTP服务 → 生成授权码
    """

    def __init__(self, config):
        self.host = config.smtp_host
        self.port = config.smtp_port
        self.username = config.smtp_username
        self.password = config.smtp_password
        self.from_name = config.smtp_from_name
        self.code_ttl = config.verification_code_ttl_minutes
        self.resend_cooldown = config.verification_resend_cooldown_seconds

    @property
    def configured(self) -> bool:
        """SMTP 是否已配置"""
        return bool(self.username and self.password)

    @staticmethod
    def generate_code() -> str:
        """生成 6 位数字验证码（cryptographically secure）"""
        return str(random.SystemRandom().randint(100000, 999999))

    def send_verification_email(self, to_email: str, code: str) -> bool:
        """发送验证码邮件

        Returns:
            True 发送成功
        Raises:
            ValueError: SMTP 未配置
            smtplib.SMTPException: 发送失败
        """
        if not self.configured:
            raise ValueError("SMTP 未配置，请在 .env 中设置 SMTP_USERNAME 和 SMTP_PASSWORD")

        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{code} — ArenaView 邮箱验证码"
        msg["From"] = formataddr((self.from_name, self.username))
        msg["To"] = to_email

        # 纯文本 + HTML
        text_part = (
            f"您好！\n\n"
            f"您的 ArenaView 验证码是: {code}\n"
            f"验证码 {self.code_ttl} 分钟内有效，请勿告知他人。\n\n"
            f"如果这不是您本人的操作，请忽略此邮件。\n\n"
            f"— ArenaView 团队"
        )
        html_part = f"""<div style="max-width:480px;margin:0 auto;padding:24px;font-family:sans-serif;
            background:#f5f0e8;border:2px solid #d4c5b0;border-radius:12px;">
            <h2 style="color:#4a3728;margin:0 0 16px;">ArenaView 邮箱验证</h2>
            <p style="color:#6b5a4e;">你的验证码是：</p>
            <div style="text-align:center;margin:24px 0;">
              <span style="font-size:32px;font-weight:bold;letter-spacing:6px;color:#3b82f6;
                background:#fff;padding:12px 28px;border-radius:8px;border:2px dashed #3b82f6;">
                {code}
              </span>
            </div>
            <p style="color:#8b7a6e;font-size:13px;">
              ⏰ {self.code_ttl} 分钟内有效 &nbsp;|&nbsp; 🔒 请勿告知他人
            </p>
            <hr style="border:1px dashed #d4c5b0;margin:20px 0;">
            <p style="color:#a09080;font-size:12px;">
              如果这不是你本人的操作，请忽略此邮件。
            </p>
          </div>"""

        msg.attach(MIMEText(text_part, "plain", "utf-8"))
        msg.attach(MIMEText(html_part, "html", "utf-8"))

        # 连接 QQ SMTP
        server = smtplib.SMTP(self.host, self.port, timeout=15)
        try:
            server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.username, to_email, msg.as_string())
            return True
        finally:
            server.quit()
