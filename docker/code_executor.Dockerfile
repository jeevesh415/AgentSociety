# syntax=docker/dockerfile:1.6
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# 创建运行用户
RUN useradd -m sandbox

# 以 root 身份全局预装常用数据处理与可视化库，所有用户可见
# 分批安装以提高构建效率和可维护性
RUN python -m pip install --no-cache-dir \
    # 基础数值计算
    numpy==1.26.4 \
    scipy==1.13.1 \
    # 数据处理
    pandas==2.2.2 \
    openpyxl \
    # 可视化
    matplotlib==3.9.0 \
    seaborn==0.13.2 \
    plotly==5.22.0 \
    # 图像处理
    pillow \
    # 机器学习
    scikit-learn==1.5.1 \
    # 统计分析
    statsmodels==0.14.2 \
    # 网络分析
    networkx==3.3 \
    # 符号计算
    sympy==1.12 \
    # 工具类
    json-repair \
    PyYAML \
    tabulate \
    beautifulsoup4 \
    requests \
    tqdm

# 切换到 sandbox 用户并设置工作目录
USER sandbox
WORKDIR /sandbox
ENV MPLCONFIGDIR=/sandbox/.mplconfig

CMD ["python", "--version"]

