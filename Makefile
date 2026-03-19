# =============================================================================
# 平时调试常用命令:
#   make dev        - 首次使用：同步依赖、安装、构建
#   make rebuild    - 代码修改后：快速重新构建
#   make watch-webview - 开发时：监听 webview 变化自动构建
#   make clean-extension & make build - 清除缓存后重新构建
# =============================================================================

.PHONY: all sync build build-extension build-webview watch watch-extension watch-webview clean clean-extension clean-all help dev rebuild
.PHONY: html html-zh html-en html-all gettext update-po build-po

# =============================================================================
# Extension Development Targets
# =============================================================================

# 默认目标：同步依赖并构建 extension
all: sync build

# 同步 Python 依赖
sync:
	@echo "==> Syncing Python dependencies with uv..."
	uv sync

# 安装 Node 依赖
install-node:
	@echo "==> Installing Node dependencies..."
	cd extension && npm install

# 构建 extension (TypeScript + Webview)
build: build-extension build-webview
	@echo "==> Build complete!"

# 仅编译 TypeScript
build-extension:
	@echo "==> Compiling TypeScript..."
	cd extension && npm run compile

# 仅构建 Webview
build-webview:
	@echo "==> Building webview..."
	cd extension && npm run build-webview

# 监听模式编译
watch: watch-extension watch-webview

# 监听 TypeScript 编译
watch-extension:
	@echo "==> Watching TypeScript..."
	cd extension && npm run watch

# 监听 Webview 构建
watch-webview:
	@echo "==> Watching webview..."
	cd extension && npm run watch-webview

# 清理 extension 构建产物
clean-extension:
	@echo "==> Cleaning extension build artifacts..."
	rm -rf extension/out/webview
	rm -rf extension/out/**/*.js
	rm -rf extension/out/**/*.map
	rm -rf extension/node_modules/.cache
	@echo "==> Extension clean complete!"

# 完整清理（包括 node_modules）
clean-all: clean-extension
	@echo "==> Removing node_modules..."
	rm -rf extension/node_modules

# 快速重新构建（用于开发时快速迭代）
rebuild: build-extension build-webview
	@echo "==> Rebuild complete!"

# 开发模式：同步、安装依赖、构建
dev: sync install-node build
	@echo ""
	@echo "==> Development environment ready!"
	@echo "==> To start debugging:"
	@echo "    1. Open extension/ folder in VSCode"
	@echo "    2. Press F5 or select 'Run > Start Debugging'"
	@echo "    3. Or use 'make watch' in another terminal for live rebuild"

# =============================================================================
# Sphinx Documentation Targets
# =============================================================================

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
SPHINXINTL    ?= sphinx-intl
SOURCEDIR     = docs
BUILDDIR      = docs/_build

# 国际化相关命令

# 提取需要翻译的文本
gettext:
	@echo "提取可翻译的文本..."
	$(SPHINXBUILD) -b gettext $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/gettext

# 更新翻译文件
update-po: gettext
	@echo "更新翻译文件..."
	$(SPHINXINTL) update -p $(BUILDDIR)/gettext -d $(SOURCEDIR)/locale -l en

# 编译翻译文件
build-po:
	@echo "编译翻译文件..."
	$(SPHINXINTL) build -d $(SOURCEDIR)/locale

# 构建中文文档（默认）
html-zh:
	@echo "构建中文文档..."
	$(SPHINXBUILD) -b html -D language=zh $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html/zh

# 构建英文文档
html-en: build-po
	@echo "构建英文文档..."
	$(SPHINXBUILD) -b html -D language=en $(SPHINXOPTS) $(SOURCEDIR) $(BUILDDIR)/html/en

# 构建所有语言版本
html-all: html-zh html-en
	@echo "所有语言版本构建完成！"

# 默认构建中文版本
html: html-zh

# 清理文档构建文件
clean-docs:
	@echo "清理文档构建文件..."
	rm -rf $(BUILDDIR)/*

# 清理所有构建产物
clean: clean-extension clean-docs
	@echo "==> All clean complete!"

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

# =============================================================================
# Help
# =============================================================================

help:
	@echo "AgentSociety Development Makefile"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Extension Development:"
	@echo "  all              同步依赖并构建 extension (默认)"
	@echo "  sync             仅同步 Python 依赖 (uv sync)"
	@echo "  install-node     仅安装 Node 依赖"
	@echo "  build            构建 extension (TypeScript + Webview)"
	@echo "  build-extension  仅编译 TypeScript"
	@echo "  build-webview    仅构建 Webview"
	@echo "  watch            监听模式构建 (TypeScript + Webview)"
	@echo "  watch-extension  监听 TypeScript 编译"
	@echo "  watch-webview    监听 Webview 构建"
	@echo "  rebuild          快速重新构建"
	@echo "  dev              完整开发环境准备 (sync + install + build)"
	@echo ""
	@echo "Documentation:"
	@echo "  html             构建中文文档"
	@echo "  html-zh          构建中文文档"
	@echo "  html-en          构建英文文档"
	@echo "  html-all         构建所有语言版本"
	@echo "  gettext          提取可翻译文本"
	@echo "  update-po        更新翻译文件"
	@echo ""
	@echo "Cleaning:"
	@echo "  clean            清理所有构建产物"
	@echo "  clean-extension  清理 extension 构建产物"
	@echo "  clean-docs       清理文档构建产物"
	@echo "  clean-all        完整清理（包括 node_modules）"
	@echo ""
	@echo "VSCode 调试:"
	@echo "  在 VSCode 中打开 extension/ 目录，按 F5 启动调试"
