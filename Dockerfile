FROM python:3.13-slim-bookworm

# Оптимизация работы Python в Docker контейнерах
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Копируем сгенерированный requirements.txt
COPY requirements.txt .

# Устанавливаем пакеты стандартным pip напрямую в систему
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальной исходный код приложения
COPY . .

EXPOSE 8003

# Дефолтная команда (совпадает с тем, что требует ваш Kubernetes)
CMD ["python", "-m", "bin.api"]
