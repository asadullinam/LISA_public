from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from urllib.parse import quote
import uvicorn
import socket
from utils.get_processor import get_processor
from initialization.db_processor_init import db_processor


redirect_server = FastAPI()


# def get_server_ip():
#     """Определяет текущий внешний IP-адрес сервера."""
#     try:
#         # Подключаемся к внешнему серверу, но НЕ отправляем данные
#         with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
#             s.connect(("8.8.8.8", 80))  # Google DNS
#             return s.getsockname()[0]
#     except Exception:
#         return "127.0.0.1"  # fallback на localhost


def generate_redirect_html(protocol: str, url: str) -> HTMLResponse:
    templates = {
        "outline": f"""
        <html>
            <head>
                <title>Launch Outline</title>
                <meta http-equiv="refresh" content="0; url='{url}'">
            </head>
            <body>
                <script>
                    window.location.href = '{url}';
                    setTimeout(() => window.close(), 30000);
                </script>
                <p>Если Outline не открылся, <a href="{url}">нажмите здесь</a></p>
            </body>
        </html>
        """,
        "vless": f"""
        <html>
            <head>
                <title>Launch Hiddify</title>
                <meta http-equiv="refresh" content="0; url='{url}'">
            </head>
            <body>
                <h2>Hiddify Connection</h2>
                <div style="margin: 20px; padding: 15px; border: 1px solid #ddd;">
                    <p>Ссылка для подключения:</p>
                    <input type="text" value="{url}" 
                           style="width: 100%; padding: 8px; margin: 10px 0;" 
                           id="hiddifyUrl" readonly>
                    <button onclick="navigator.clipboard.writeText('{url}')">
                        Скопировать
                    </button>
                </div>
                <script>
                    // Попытка открыть десктопное приложение
                    window.location.href = '{url}';

                    // Автоматическое закрытие через 30 сек
                    setTimeout(() => window.close(), 30000);
                </script>
            </body>
        </html>
        """,
    }
    return HTMLResponse(content=templates[protocol])


def generate_hiddify_url(base_url: str, key_name: str) -> str:
    """Генерирует URL для Hiddify с именем ключа"""
    # 1. Удаляем существующее имя из ссылки (если есть)
    base_without_fragment = base_url.split("#")[0]

    # 2. Кодируем имя ключа (пробелы -> %20 и т.д.)
    encoded_name = quote(key_name.strip())

    # 3. Собираем VLESS-ссылку с именем во фрагменте
    vless_url_with_name = f"{base_without_fragment}#{encoded_name}"

    # 4. Кодируем только спецсимволы, кроме :/?#&= для сохранения структуры
    encoded_vless = quote(vless_url_with_name, safe=":/?#&=+")

    # 5. Формируем итоговый URL для Hiddify
    return f"hiddify://import/{encoded_vless}"


@redirect_server.get("/open/{key_id}")
async def open_connection(key_id: str):
    try:
        key = db_processor.get_key_by_id(key_id)

        if not key:
            raise HTTPException(status_code=404, detail="Key not found")

        key_protocol = key.protocol_type.lower()
        processor = await get_processor(key_protocol)
        key_info = await processor.get_key_info(key_id, server_id=key.server_id)

        match key_protocol:
            case "outline":
                url = key_info.access_url
            case "vless":
                # Добавляем имя ключа из базы данных
                url = generate_hiddify_url(
                    key_info.access_url,
                    key.name or f"Server-{key.server_id}",  # Дефолтное имя
                )
            case _:
                raise HTTPException(status_code=400, detail="Unsupported protocol")

        return generate_redirect_html(key_protocol, url)

    except Exception as e:
        return HTMLResponse(content=f"<h1>Error</h1><p>{str(e)}</p>", status_code=500)


if __name__ == "__main__":
    # host_ip = get_server_ip()
    host_ip = "0.0.0.0"
    print(f"Запуск сервера на {host_ip}:8000")
    uvicorn.run(redirect_server, host=host_ip, port=8000)
