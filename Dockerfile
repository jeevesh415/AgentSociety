# Stage 1: Build VSCode extension as vsix
FROM node:20 AS extension-builder

WORKDIR /app

RUN npm config set registry https://registry.npmmirror.com

# Install vsce globally for packaging
RUN npm install -g @vscode/vsce

# Copy extension dependency files first for better caching
WORKDIR /app/extension
COPY ./extension/package.json ./extension/package-lock.json ./
RUN npm ci

# Copy extension source code and config files
COPY ./extension/tsconfig.json ./
COPY ./extension/webpack.config.js ./
COPY ./extension/src/ ./src/
COPY ./extension/media/ ./media/
COPY ./extension/resources/ ./resources/
COPY ./extension/.vscodeignore ./
# Copy LICENSE file for vsce packaging (from project root)
COPY LICENSE ./

# Build and package the extension
RUN npm run vscode:prepublish
RUN vsce package --out /app/extension.vsix

# Stage 2: Python runtime with extension
FROM python:3.12

RUN apt-get update && apt-get install -y curl locales && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files
COPY README.md LICENSE ./
COPY pyproject.toml uv.lock ./
COPY packages/ ./packages/

# 使用清华源安装依赖
RUN mkdir -p /etc/uv
RUN echo "[[index]]\nurl = \"https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/\"\ndefault = true" > /etc/uv/uv.toml

# 安装 agentsociety2 及其所有依赖到默认 Python 环境（不使用 venv）
# 使用 --system 标志安装到系统 Python 环境，而不是创建虚拟环境
RUN uv pip install --system -e ./packages/agentsociety2

# Copy the vsix file from builder stage
COPY --from=extension-builder /app/extension.vsix /app/extension.vsix

# Remove the `ubuntu` user and add a user `coder` so that you're not developing as the `root` user
RUN mkdir -p /etc/sudoers.d && \
    useradd coder \
    --create-home \
    --shell=/bin/bash \
    --uid=1000 \
    --user-group && \
    echo "coder ALL=(ALL) NOPASSWD:ALL" >>/etc/sudoers.d/nopasswd

# Make typing unicode characters in the terminal work.
# Generate the desired locale (en_US.UTF-8)
RUN locale-gen en_US.UTF-8
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# Install pipx and ensure path is set up
RUN uv pip install --system pipx && pipx ensurepath

USER coder
