FROM python:3.11-slim

# 安装系统依赖（spaCy 中文模型 + 编译工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 下载 spaCy 模型（使用较小的中文模型避免体积过大）
RUN python -m spacy download en_core_web_sm || true
RUN python -m spacy download zh_core_web_sm || true

# 复制项目代码
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
