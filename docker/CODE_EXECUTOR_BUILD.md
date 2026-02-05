# Code Executor Docker 镜像构建说明

## 镜像信息

- **镜像名称**: `agentsociety2/code-executor:latest`
- **用途**: 代码执行器沙箱环境，用于安全执行生成的 Python 代码

## 构建步骤

### 1. 定位 Dockerfile

Dockerfile 位于项目根目录的 `docker/code_executor.Dockerfile`

### 2. 构建镜像

在项目根目录执行：

```bash
# 基本构建
docker build -t agentsociety2/code-executor:latest -f docker/code_executor.Dockerfile .

# 或者指定其他标签
docker build -t agentsociety2/code-executor:v1.0.0 -f docker/code_executor.Dockerfile .
```

### 3. 验证镜像

```bash
# 查看镜像
docker images | grep code-executor

# 测试运行
docker run --rm agentsociety2/code-executor:latest python --version
```