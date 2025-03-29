from outline_vpn.outline_vpn import OutlineKey


def get_outline_instruction_string(key_access_url: str) -> str:
    instructions = (
        "📖 Инструкция по установке VPN: (подробная инструкция указана в главном меню)\n"
        "Рекомендуем в случае покупке первого ключа и скачивания приложения впервые обратиться к подробной инструкции для корректной установки.\n\n"
        "1. Скачайте приложение OutLine:\n"
        "   - Для Android: [Ссылка на Google Play](https://play.google.com/store/apps/details?id=org.outline.android.client&hl=ru)\n"
        "   - Для iOS: [Ссылка на App Store](https://apps.apple.com/ru/app/outline-app/id1356177741)\n"
        "   - Для Windows: [Ссылка на сайт](https://outline-vpn.com/#download-outline)\n"
        "   - Для Mac: [Ссылка на сайт](https://apps.apple.com/ru/app/outline-secure-internet-access/id1356178125?mt=12)\n\n"
        "2. Откройте приложение и вставьте ключ:\n"
        f"```\n"
        f"{key_access_url}\n"
        f"```"
        "3. Подключитесь и наслаждайтесь безопасным интернетом! 🎉"
    )
    return instructions


def get_vless_instruction_string(key_access_url: str) -> str:
    instructions = (
        "📖 Инструкция по установке VPN: (подробная инструкция указана в главном меню)\n\n"
        "Рекомендуем в случае покупке первого ключа и скачивания приложения впервые обратиться к подробной инструкции для корректной установки.\n\n"
        "1. Скачайте приложение Hiddify (для iOS: v2box):\n"
        "   - Для Android: [Ссылка на Google Play](https://play.google.com/store/apps/details?id=app.hiddify.com)\n"
        "   - Для iOS: [Ссылка на App Store](https://apps.apple.com/ru/app/v2box-v2ray-client/id6446814690)\n"
        "   - Для Windows: [Ссылка на сайт](https://apps.microsoft.com/detail/9PDFNL3QV2S5?hl=neutral&gl=RU&ocid=pdpshare)\n"
        "   - Для Mac: [Ссылка на сайт](https://apps.apple.com/ru/app/hiddify-proxy-vpn/id6596777532)\n\n"
        "2. Откройте приложение и вставьте ключ:\n"
        f"```\n"
        f"{key_access_url}\n"
        f"```"
        "3. Подключитесь и наслаждайтесь безопасным интернетом! 🎉"
    )
    return instructions


def get_your_key_string(key: OutlineKey, text="Ваш ключ от VPN") -> str:
    return f"{text}\n```\n" f"{key.access_url}\n```"
