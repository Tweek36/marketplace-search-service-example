#!/bin/sh
set -e

# Устанавливаем зависимости
uv sync --frozen

# Запускаем приложение
exec python -m bin.api