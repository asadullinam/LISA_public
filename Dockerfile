# Используем официальный образ Python
FROM python:3.10

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта
COPY requirements.txt .
COPY src /app/src

# Устанавливаем зависимости
RUN pip install -r requirements.txt

# Добавляем /app в PYTHONPATH
ENV PYTHONPATH=/app/src
