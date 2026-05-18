"""Отправка писем через SMTP.

Настраивается переменными окружения. Если SMTP не задан — функции
просто ничего не отправляют (демо-режим), приложение продолжает работать.

Переменные окружения:
  SMTP_HOST      — адрес SMTP-сервера (например smtp.gmail.com, smtp.yandex.ru)
  SMTP_PORT      — порт (обычно 465 для SSL или 587 для STARTTLS), по умолчанию 465
  SMTP_USER      — логин (полный адрес почты, с которой отправляем)
  SMTP_PASSWORD  — пароль приложения (НЕ обычный пароль от почты!)
  SMTP_FROM      — адрес отправителя (по умолчанию = SMTP_USER)
  SMTP_FROM_NAME — имя отправителя (по умолчанию «Европа-Тур»)
  SITE_URL       — базовый адрес сайта для ссылок в письме

Как получить пароль приложения:
  Gmail   — включить 2FA, затем myaccount.google.com → Безопасность →
            Пароли приложений.
  Яндекс  — id.yandex.ru → Безопасность → Пароли приложений → Почта.
"""
import os
import ssl
import smtplib
from email.message import EmailMessage

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Европа-Тур")
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")

# Письма отправляются по-настоящему, только если заданы хост, логин и пароль.
MAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def _send(to_email: str, subject: str, text_body: str, html_body: str) -> bool:
    """Низкоуровневая отправка одного письма. Возвращает True при успехе."""
    if not MAIL_ENABLED:
        print(f"[mail] SMTP не настроен — письмо для {to_email} не отправлено")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM}>"
    msg["To"] = to_email
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    try:
        if SMTP_PORT == 465:
            # SSL-соединение (Gmail, Яндекс — порт 465)
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=20) as s:
                s.login(SMTP_USER, SMTP_PASSWORD)
                s.send_message(msg)
        else:
            # STARTTLS (порт 587 и др.)
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
                s.starttls(context=ssl.create_default_context())
                s.login(SMTP_USER, SMTP_PASSWORD)
                s.send_message(msg)
        print(f"[mail] письмо отправлено: {to_email} — {subject}")
        return True
    except Exception as e:
        print(f"[mail] ошибка отправки на {to_email}: {e}")
        return False


def _html_wrap(title: str, body_html: str) -> str:
    """Оборачивает содержимое письма в общий фирменный шаблон."""
    return f"""\
<!DOCTYPE html>
<html lang="ru">
<body style="margin:0;padding:0;background:#eef2f9;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f9;padding:32px 0;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:14px;overflow:hidden;
                    box-shadow:0 4px 16px rgba(20,30,55,.12);">
        <tr>
          <td style="background:#0a6cff;padding:24px 32px;">
            <span style="color:#ffffff;font-size:20px;font-weight:bold;">
              ✈ Европа-Тур
            </span>
          </td>
        </tr>
        <tr>
          <td style="padding:32px;">
            <h1 style="margin:0 0 16px;font-size:21px;color:#0f1626;">{title}</h1>
            {body_html}
          </td>
        </tr>
        <tr>
          <td style="padding:20px 32px;background:#f5f7fb;color:#5f6982;font-size:12px;">
            ООО «Европа-Тур» · туристическое агентство с 1995 года<br>
            190068, Санкт-Петербург, наб. Крюкова канала, д. 31
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_welcome_email(to_email: str, first_name: str, verify_token: str) -> bool:
    """Письмо после регистрации: приветствие + ссылка подтверждения email."""
    name = first_name or "путешественник"
    verify_link = ""
    if SITE_URL and verify_token:
        verify_link = f"{SITE_URL}/#/verify?token={verify_token}"

    button = ""
    if verify_link:
        button = f"""
      <p style="margin:24px 0;">
        <a href="{verify_link}"
           style="display:inline-block;background:#0a6cff;color:#ffffff;
                  text-decoration:none;font-weight:bold;font-size:15px;
                  padding:13px 28px;border-radius:10px;">
          Подтвердить e-mail
        </a>
      </p>
      <p style="margin:0;font-size:13px;color:#5f6982;">
        Если кнопка не работает, скопируйте ссылку в браузер:<br>
        <a href="{verify_link}" style="color:#0a6cff;">{verify_link}</a>
      </p>"""

    body_html = f"""
      <p style="margin:0 0 12px;font-size:15px;color:#3a4458;line-height:1.6;">
        Здравствуйте, {name}!
      </p>
      <p style="margin:0 0 12px;font-size:15px;color:#3a4458;line-height:1.6;">
        Вы успешно зарегистрировались на сайте туристического агентства
        «Европа-Тур». Теперь вам доступны подбор туров, бронирование и
        личный кабинет.
      </p>
      <p style="margin:0;font-size:15px;color:#3a4458;line-height:1.6;">
        Чтобы завершить регистрацию, подтвердите адрес электронной почты.
      </p>
      {button}
    """

    text_body = (
        f"Здравствуйте, {name}!\n\n"
        "Вы успешно зарегистрировались на сайте «Европа-Тур».\n"
        "Теперь вам доступны подбор туров, бронирование и личный кабинет.\n\n"
    )
    if verify_link:
        text_body += f"Подтвердите e-mail по ссылке:\n{verify_link}\n\n"
    text_body += "ООО «Европа-Тур»"

    return _send(
        to_email,
        "Добро пожаловать в «Европа-Тур»",
        text_body,
        _html_wrap("Вы успешно зарегистрировались", body_html),
    )
