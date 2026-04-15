/**
 * i18n 国际化工具模块
 * 
 * 为 VSCode 扩展主进程提供国际化支持
 * 默认语言：中文
 */

import * as vscode from 'vscode';

// 翻译资源
const translations: Record<string, Record<string, string>> = {
  'zh-CN': {
    // extension.ts
    'extension.activate': 'AI Social Scientist 扩展已激活！',
    'extension.initProject.prompt': '输入研究话题',
    'extension.initProject.placeholder': '例如：社交媒体对政治观点的影响',
    'extension.initProject.success': '研究项目已初始化：{0}',
    'extension.initProject.button': '初始化工作区',
    'extension.configureEnv.button': '配置环境变量',
    'extension.configureEnv.title': '配置环境变量',
    'extension.fixWorkspace.button': '修复工作区目录',
    'workspaceExport.statusBar.ready': '$(cloud-download) 导出工作区 ZIP',
    'workspaceExport.statusBar.exporting': '$(sync~spin) 导出工作区中...',
    'workspaceExport.statusBar.tooltip': '打开导出内容选择界面并生成 ZIP，.env 会自动排除',
    'workspaceExport.noWorkspace': '未找到工作区文件夹',
    'workspaceExport.noSelection': '请至少勾选一个导出项',
    'workspaceExport.saveLabel': '导出 ZIP',
    'workspaceExport.progress.title': '正在导出工作区 ZIP',
    'workspaceExport.progress.collecting': '正在收集导出文件...',
    'workspaceExport.progress.copying': '正在复制 {0}',
    'workspaceExport.progress.archiving': '正在生成 ZIP 压缩包...',
    'workspaceExport.progress.saving': '正在写入目标位置...',
    'workspaceExport.progress.done': '导出完成',
    'workspaceExport.pick.title': '选择要导出的工作区内容',
    'workspaceExport.pick.placeholder': '默认已勾选插件维护的工作区结构项，.env 已自动排除，其余项可按需勾选',
    'workspaceExport.pick.defaultDescription': '默认导出',
    'workspaceExport.pick.optionalDescription': '可选',
    'workspaceExport.pick.directoryDetail': '目录',
    'workspaceExport.pick.fileDetail': '文件',
    'workspaceExport.pick.claudeConversationDetail': 'Claude Code 对话记录（外部目录）',
    'workspaceExport.empty': '未找到可导出的工作区文件',
    'workspaceExport.failed': '导出工作区失败: {0}',
    'workspaceExport.success': '导出完成：{0}，共包含 {1} 个文件',
    'workspaceExport.reveal': '在系统中显示',
    'workspaceExport.copyPath': '复制路径',
    'workspaceExport.postActionFailed': '导出已完成，但后续操作失败：{0}',
    'workspaceExport.viewOutput': '查看输出',
    'workspaceExport.pythonUnavailable': '无法找到可用的 Python 来创建 ZIP 压缩包',
    'extension.aiChat.label': 'AI 对话',
    'extension.searchPapers.prompt': '输入论文搜索查询',
    'extension.searchPapers.placeholder': '例如：社交媒体影响',
    'extension.searchPapers.searching': '正在搜索论文：{0}',
    'extension.generateHypothesis': '正在生成假设...',
    'extension.initExperiment': '正在初始化实验...',
    'extension.runExperiment': '正在运行实验...',
    'extension.analyzeResults': '正在分析结果...',

    // extension.ts - deleteLiterature
    'extension.deleteLiterature.noFile': '无法删除：未选择有效的文件',
    'extension.deleteLiterature.noWorkspace': '未找到工作区文件夹',
    'extension.deleteLiterature.confirm': '确定要删除 "{0}" 吗？此操作无法撤销。',
    'extension.deleteLiterature.confirmButton': '删除',
    'extension.deleteLiterature.cancelButton': '取消',
    'extension.deleteLiterature.failed': '删除失败: {0}',

    // extension.ts - common errors
    'extension.isDirectory': '"{0}" 是一个目录，请使用专门的删除命令或手动删除。',
    'extension.noFilePath': '无法获取文件路径',
    'extension.noLiteratureIndexPath': '无法获取文献索引文件路径',
    'extension.skill.noName': '无法获取 Skill 名称',
    'extension.skill.noDirPath': '无法获取 Skill 目录路径',
    'extension.skill.deleteFailed': '删除 Skill 失败: {0}',

    // extension.ts - renameLiterature
    'extension.renameLiterature.noFile': '无法重命名：未选择有效的文件',
    'extension.renameLiterature.noWorkspace': '未找到工作区文件夹',
    'extension.renameLiterature.prompt': '输入新文件名',
    'extension.renameLiterature.emptyName': '文件名不能为空',
    'extension.renameLiterature.invalidChars': '文件名不能包含路径分隔符',
    'extension.renameLiterature.failed': '重命名失败: {0}',

    // extension.ts - openMarkdownInEditor
    'extension.openMarkdown.noFile': '无法打开：未选择有效的文件',
    'extension.openMarkdown.warning': '此命令仅适用于 Markdown 文件',
    'extension.openMarkdown.failed': '打开文件失败: {0}',

    // projectStructureProvider.ts
    'projectStructure.noWorkspace': '未找到工作区文件夹',
    'projectStructure.literature': '文献库',
    'projectStructure.userData': '用户数据',
    'projectStructure.resultsDatabase': 'Results Database',
    'projectStructure.init': 'Init: {0}',
    'projectStructure.researchTopic': '研究话题',
    'projectStructure.simSettings': '模拟设置',
    'projectStructure.hypothesis': '假设',
    'projectStructure.experiment': '实验',
    'projectStructure.initWorkspace.warnExists': '检测到 .agentsociety 文件夹已存在。重新初始化将覆盖它，这可能会导致长期记忆丢失。是否继续？',
    'projectStructure.initWorkspace.confirm': '确认',
    'projectStructure.initWorkspace.cancel': '取消',
    'projectStructure.initWorkspace.failed': '初始化失败: {0}',
    'workspaceInit.initializing': '正在初始化工作区，请稍候...',
    'workspaceInit.success': '工作区初始化成功：{0}',
    'workspaceInit.failed': '工作区初始化失败：{0}',

    // dragAndDropController.ts
    'dragDrop.noTarget': '请拖拽到"文献库"或"用户数据"节点',
    'dragDrop.invalidTarget': '不支持拖拽到"{0}"节点，请拖拽到"文献库"或"用户数据"节点',
    'dragDrop.noFiles': '未检测到文件，请从文件管理器拖拽文件',
    'dragDrop.noValidUris': '未找到有效的文件URI',
    'dragDrop.noWorkspace': '未找到工作区文件夹',
    'dragDrop.fileExists': '{0} 已存在，如何处理？',
    'dragDrop.moreFiles': '等 {0} 个文件',
    'dragDrop.overwriteAll': '全部覆盖',
    'dragDrop.skipAll': '全部跳过',
    'dragDrop.askEach': '逐个询问',
    'dragDrop.overwriteConfirm': '文件 "{0}" 已存在，是否覆盖？',
    'dragDrop.overwrite': '覆盖',
    'dragDrop.skip': '跳过',
    'dragDrop.success': '成功上传 {0} 个文件到{1}',
    'dragDrop.partialSuccess': '部分文件处理完成：{0}',
    'dragDrop.successCount': '{0} 个成功',
    'dragDrop.skipCount': '{0} 个跳过',
    'dragDrop.failCount': '{0} 个失败',
    'dragDrop.allSkipped': '已跳过 {0} 个已存在的文件',
    'dragDrop.allFailed': '上传失败：{0} 个文件无法上传',
    'dragDrop.noFilesProcessed': '没有文件需要处理',
    'dragDrop.error': '拖拽上传过程中发生错误: {0}',
    'dragDrop.literature': '文献库',
    'dragDrop.userData': '用户数据',
    'dragDrop.unsupportedDirectory': '不支持拖拽目录: {0}',
    'dragDrop.fileNotAccessible': '文件不存在或无法访问: {0}',
    'dragDrop.uploading': '正在上传文件...',
    'dragDrop.cancel': '取消',
    'dragDrop.largeFileWarning': '文件 "{0}" 大小为 {1} MB，可能需要较长时间上传，是否继续？',
    'dragDrop.largeFilesWarning': '有 {0} 个文件超过 100 MB，上传可能需要较长时间，是否继续？',
    'dragDrop.processing': '正在处理 {0} ({1}/{2})',
    'dragDrop.directoryReadFailed': '无法读取目录内容: {0}',
    'dragDrop.emptyFileName': '跳过无效文件名的文件',
    'dragDrop.cancelled': '上传已取消',
    'dragDrop.mkdirFailed': '无法创建目标目录: {0}',

    // prefillParamsViewProvider.ts
    'prefillParamsViewProvider.noWorkspace': '未找到工作区文件夹',
    'prefillParams.title': '预填充参数',
    'prefillParams.groupTitle': '环境与智能体',
    'prefillParams.envModuleTitle': '环境模块预置参数',
    'prefillParams.agentTitle': '智能体类预置参数',

    // projectStructureProvider.ts - settings
    'projectStructure.settings': '配置设置',
    'projectStructure.agentSkills': 'Agent Skills',
    'projectStructure.extensionSkills': 'AgentSociety Skills',
    'projectStructure.agentSkillsScan': '扫描 Skills',
    'projectStructure.agentSkillsImport': '导入 Skill',
    'projectStructure.agentSkillsBuiltin': '内置 Skills',
    'projectStructure.agentSkillsCustom': '自定义 Skills',
    'projectStructure.agentSkillsEmpty': '暂无 Skills，点击扫描或导入',
    'projectStructure.skillEnabled': '已启用',
    'projectStructure.skillDisabled': '已禁用',
    'projectStructure.skillPriority': '优先级',
    'projectStructure.skillRemove': '删除 Skill',
    'projectStructure.skillRemoveConfirm': '确定要删除自定义 Skill "{0}" 吗？此操作无法撤销。',
    'projectStructure.skillImportLocal': '从本地目录导入 Skill',
    'projectStructure.skillImportPlaceholder': '选择 Skill 导入方式',
    'projectStructure.extensionSkillsUpdate': '更新 Skills',
    'projectStructure.extensionSkillsUpdateSuccess': '已更新 {0} 个 Skills',
    'projectStructure.extensionSkillsUpdateFailed': '更新 Skills 失败: {0}',

    // backendManager.ts
    'backendManager.openSettings': '打开设置',
    'backendManager.configInsufficient': '配置不足以支持启动后端服务',
    'backendManager.statusBar.restart': '重启后端',
    'backendManager.statusBar.stop': '停止后端',
    'backendManager.statusBar.start': '启动后端',
    'backendManager.statusBar.logs': '查看日志',
    'backendManager.statusBar.status': '查看状态',
    'backendManager.statusBar.config': '打开配置',
    'backendManager.statusBar.tooltip': '点击展开操作菜单',
    'backendManager.statusBar.placeholder': '选择操作',

    // configPageViewProvider.ts
    'configPage.title': 'AI Social Scientist 配置',
    'configPage.noWorkspace': '请先打开一个工作区文件夹。配置将保存在当前工作区中。',
    'configPage.openWorkspace': '打开工作区',

    // customModules
    'customModules.noWorkspace': '未找到工作区文件夹',
    'customModules.scanning': '正在扫描自定义模块...',
    'customModules.scanSuccess': '扫描完成',
    'customModules.scanFailed': '扫描失败: {0}',
    'customModules.testing': '正在测试自定义模块...',
    'customModules.testSuccess': '测试完成',
    'customModules.testFailed': '测试失败: {0}',
    'customModules.noModules': '未发现自定义模块',
    'customModules.listFailed': '获取模块列表失败: {0}',
    'customModules.syncAssistant.updating': '正在同步 AI 助手资源...',
    'customModules.syncAssistant.success': 'AI 助手资源已同步: {0} 个技能文件, {1}',
    'customModules.syncAssistant.claudeMdUpdated': 'CLAUDE.md 已更新',
    'customModules.syncAssistant.failed': '同步 AI 助手资源失败: {0}',

    // workspace fix
    'workspaceFix.healthy': '工作区目录结构完整，无需修复',
    'workspaceFix.fixed': '工作区已修复，创建了 {0} 个项目',
    'workspaceFix.failed': '修复失败: {0}',
    'workspaceFix.confirm': '检测到工作区缺少 {0} 个项目:\n{1}\n\n是否立即修复？',

    // projectStructureProvider.ts - custom modules
    'projectStructure.customModules': '自定义模块',
    'projectStructure.customAgents': '自定义 Agents',
    'projectStructure.customEnvs': '自定义环境',
    'projectStructure.customScan': '扫描模块',
    'projectStructure.customTest': '测试模块',

    // projectStructureProvider.ts - analysis reports
    'projectStructure.presentation': '分析报告',
    'projectStructure.synthesis': '综合报告',
    'projectStructure.reportHtml': 'HTML 报告',
    'projectStructure.reportMd': 'Markdown 报告',
    'projectStructure.analysisData': '分析数据',
    'projectStructure.reportCharts': '图表',
    'projectStructure.reportAssets': '资源',
    'projectStructure.reportHtmlZh': '中文 HTML 报告',
    'projectStructure.reportMdZh': '中文 Markdown 报告',
    'projectStructure.reportHtmlEn': 'English HTML Report',
    'projectStructure.reportMdEn': 'English Markdown Report',
    'projectStructure.openReplay': '打开回放',
    'projectStructure.literatureIndex': '文献索引',
    'projectStructure.articles': '篇文献',
    'projectStructure.files': '个文件',
    'projectStructure.pdfFiles': 'PDF文献',
    'projectStructure.mdFiles': 'Markdown笔记',
    'projectStructure.jsonFiles': 'JSON文件',
    'projectStructure.experimentStatus': '实验状态',
    'projectStructure.startTime': '开始时间',
    'projectStructure.endTime': '结束时间',
    'projectStructure.statusCompleted': '实验已完成',
    'projectStructure.statusRunning': '实验运行中',
    'projectStructure.statusFailed': '实验失败',
    'projectStructure.statusPaused': '实验暂停',
    'projectStructure.experiments': '实验数',
    'projectStructure.completed': '已完成',
    'projectStructure.running': '运行中',
    'projectStructure.datasets': '数据集',
    'projectStructure.datasetItem': '数据集',

    // projectStructureProvider.ts - skills update
    'projectStructure.updateSkills.step1': '正在更新 Skills - 步骤 1/2: AgentSociety 技能',
    'projectStructure.updateSkills.step2': '正在更新 Skills - 步骤 2/2: 官方 Office 技能',
    'projectStructure.updateSkills.success': '✅ Skills 更新完成！\n\n',
    'projectStructure.updateSkills.agentsociety': '✓ AgentSociety 技能: {0} 项\n',
    'projectStructure.updateSkills.office': '✓ 官方 Office 技能: {0} 项 (pdf, docx, xlsx, pptx)\n\n',
    'projectStructure.updateSkills.total': '总计: {0} 项',
    'projectStructure.updateSkills.partialIssues': '⚠️ Skills 更新完成但存在问题\n\n',
    'projectStructure.updateSkills.officeFailed': '✗ 官方 Office 技能: 0 项 (复制失败)\n\n',
    'projectStructure.updateSkills.partialSuccess': '⚠️ Skills 部分更新完成\n\n',
    'projectStructure.updateSkills.partialOffice': '✓ 官方 Office 技能: {0} 项\n\n',
    'projectStructure.updateSkills.checkExtension': '📋 请检查扩展安装是否正确。',
    'projectStructure.updateSkills.viewDetails': '查看详情',
    'projectStructure.updateSkills.viewInstructions': '查看说明',
    'projectStructure.updateSkills.close': '关闭',
    'projectStructure.updateSkills.ok': '确定',
    'projectStructure.updateSkills.failed': 'Skills 更新失败: {0}',
    'projectStructure.updateSkills.viewOutput': '查看输出',
  },
  'en-US': {
    // extension.ts
    'extension.activate': 'AI Social Scientist extension is now active!',
    'extension.initProject.prompt': 'Enter research topic',
    'extension.initProject.placeholder': 'e.g., Social media influence on political opinions',
    'extension.initProject.success': 'Research project initialized: {0}',
    'extension.initProject.button': 'Initialize Workspace',
    'extension.configureEnv.button': 'Configure Environment',
    'extension.configureEnv.title': 'Configure Environment Variables',
    'extension.fixWorkspace.button': 'Fix Workspace Directory',
    'workspaceExport.statusBar.ready': '$(cloud-download) Export Workspace ZIP',
    'workspaceExport.statusBar.exporting': '$(sync~spin) Exporting Workspace...',
    'workspaceExport.statusBar.tooltip': 'Open the export picker and generate a ZIP archive. The .env file is always excluded.',
    'workspaceExport.noWorkspace': 'Workspace folder not found',
    'workspaceExport.noSelection': 'Select at least one item to export',
    'workspaceExport.saveLabel': 'Export ZIP',
    'workspaceExport.progress.title': 'Exporting workspace ZIP',
    'workspaceExport.progress.collecting': 'Collecting files to export...',
    'workspaceExport.progress.copying': 'Copying {0}',
    'workspaceExport.progress.archiving': 'Creating ZIP archive...',
    'workspaceExport.progress.saving': 'Writing archive to the selected destination...',
    'workspaceExport.progress.done': 'Export complete',
    'workspaceExport.pick.title': 'Choose workspace content to export',
    'workspaceExport.pick.placeholder': 'Plugin-maintained workspace items are preselected, .env is excluded, and all other top-level items are optional.',
    'workspaceExport.pick.defaultDescription': 'Default export',
    'workspaceExport.pick.optionalDescription': 'Optional',
    'workspaceExport.pick.directoryDetail': 'Directory',
    'workspaceExport.pick.fileDetail': 'File',
    'workspaceExport.pick.claudeConversationDetail': 'Claude Code conversations (external directory)',
    'workspaceExport.empty': 'No workspace files were found for export',
    'workspaceExport.failed': 'Failed to export workspace: {0}',
    'workspaceExport.success': 'Export complete: {0} with {1} file(s)',
    'workspaceExport.reveal': 'Reveal in File Manager',
    'workspaceExport.copyPath': 'Copy Path',
    'workspaceExport.postActionFailed': 'Export succeeded, but the follow-up action failed: {0}',
    'workspaceExport.viewOutput': 'View Output',
    'workspaceExport.pythonUnavailable': 'Could not find an available Python executable to create the ZIP archive',
    'extension.aiChat.label': 'AI Chat',
    'extension.searchPapers.prompt': 'Enter paper search query',
    'extension.searchPapers.placeholder': 'e.g., social media influence',
    'extension.searchPapers.searching': 'Searching papers for: {0}',
    'extension.generateHypothesis': 'Generating hypothesis...',
    'extension.initExperiment': 'Initializing experiment...',
    'extension.runExperiment': 'Running experiment...',
    'extension.analyzeResults': 'Analyzing results...',

    // extension.ts - deleteLiterature
    'extension.deleteLiterature.noFile': 'Cannot delete: No valid file selected',
    'extension.deleteLiterature.noWorkspace': 'Workspace folder not found',
    'extension.deleteLiterature.confirm': 'Are you sure you want to delete "{0}"? This action cannot be undone.',
    'extension.deleteLiterature.confirmButton': 'Delete',
    'extension.deleteLiterature.cancelButton': 'Cancel',
    'extension.deleteLiterature.failed': 'Delete failed: {0}',

    // extension.ts - common errors
    'extension.isDirectory': '"{0}" is a directory. Please use the dedicated delete command or delete manually.',
    'extension.noFilePath': 'Cannot get file path',
    'extension.noLiteratureIndexPath': 'Cannot get literature index file path',
    'extension.skill.noName': 'Cannot get Skill name',
    'extension.skill.noDirPath': 'Cannot get Skill directory path',
    'extension.skill.deleteFailed': 'Failed to delete Skill: {0}',

    // extension.ts - renameLiterature
    'extension.renameLiterature.noFile': 'Cannot rename: No valid file selected',
    'extension.renameLiterature.noWorkspace': 'Workspace folder not found',
    'extension.renameLiterature.prompt': 'Enter new file name',
    'extension.renameLiterature.emptyName': 'File name cannot be empty',
    'extension.renameLiterature.invalidChars': 'File name cannot contain path separators',
    'extension.renameLiterature.failed': 'Rename failed: {0}',

    // extension.ts - openMarkdownInEditor
    'extension.openMarkdown.noFile': 'Cannot open: No valid file selected',
    'extension.openMarkdown.warning': 'This command only works with Markdown files',
    'extension.openMarkdown.failed': 'Failed to open file: {0}',

    // extension.ts - parseWithMinerU
    'extension.parseMinerU.noFile': 'Cannot parse: No valid file selected',
    'extension.parseMinerU.noWorkspace': 'Workspace folder not found',
    'extension.parseMinerU.unsupportedFormat': 'MinerU parsing currently only supports PDF files',
    'extension.parseMinerU.parsing': 'Parsing {0}...',
    'extension.parseMinerU.success': 'Successfully parsed file: {0}',
    'extension.parseMinerU.openFile': 'Open File',
    'extension.parseMinerU.failed': 'Parse failed: {0}',

    // projectStructureProvider.ts
    'projectStructure.noWorkspace': 'Workspace folder not found',
    'projectStructure.literature': 'Literature',
    'projectStructure.userData': 'User Data',
    'projectStructure.resultsDatabase': 'Results Database',
    'projectStructure.init': 'Init: {0}',
    'projectStructure.researchTopic': 'Research Topic',
    'projectStructure.simSettings': 'SIM Settings',
    'projectStructure.hypothesis': 'Hypothesis',
    'projectStructure.experiment': 'Experiment',
    'projectStructure.initWorkspace.warnExists': 'The .agentsociety folder already exists. Re-initializing will overwrite it, which may lead to loss of long-term memory. Do you want to continue?',
    'projectStructure.initWorkspace.confirm': 'Confirm',
    'projectStructure.initWorkspace.cancel': 'Cancel',
    'projectStructure.initWorkspace.failed': 'Initialization failed: {0}',
    'workspaceInit.initializing': 'Initializing workspace, please wait...',
    'workspaceInit.success': 'Workspace initialized successfully: {0}',
    'workspaceInit.failed': 'Workspace initialization failed: {0}',

    // dragAndDropController.ts
    'dragDrop.noTarget': 'Please drag to "Literature" or "User Data" node',
    'dragDrop.invalidTarget': 'Cannot drag to "{0}" node, please drag to "Literature" or "User Data" node',
    'dragDrop.noFiles': 'No files detected, please drag files from file manager',
    'dragDrop.noValidUris': 'No valid file URIs found',
    'dragDrop.noWorkspace': 'Workspace folder not found',
    'dragDrop.fileExists': '{0} already exists, how to proceed?',
    'dragDrop.moreFiles': ' and {0} more files',
    'dragDrop.overwriteAll': 'Overwrite All',
    'dragDrop.skipAll': 'Skip All',
    'dragDrop.askEach': 'Ask for Each',
    'dragDrop.overwriteConfirm': 'File "{0}" already exists, overwrite?',
    'dragDrop.overwrite': 'Overwrite',
    'dragDrop.skip': 'Skip',
    'dragDrop.success': 'Successfully uploaded {0} file(s) to {1}',
    'dragDrop.partialSuccess': 'Partial files processed: {0}',
    'dragDrop.successCount': '{0} succeeded',
    'dragDrop.skipCount': '{0} skipped',
    'dragDrop.failCount': '{0} failed',
    'dragDrop.allSkipped': 'Skipped {0} existing file(s)',
    'dragDrop.allFailed': 'Upload failed: {0} file(s) could not be uploaded',
    'dragDrop.noFilesProcessed': 'No files to process',
    'dragDrop.error': 'Error during drag and drop: {0}',
    'dragDrop.literature': 'Literature',
    'dragDrop.userData': 'User Data',
    'dragDrop.unsupportedDirectory': 'Directories are not supported: {0}',
    'dragDrop.fileNotAccessible': 'File does not exist or is not accessible: {0}',
    'dragDrop.uploading': 'Uploading files...',
    'dragDrop.cancel': 'Cancel',
    'dragDrop.largeFileWarning': 'File "{0}" is {1} MB, upload may take a long time. Continue?',
    'dragDrop.largeFilesWarning': '{0} files are over 100 MB, upload may take a long time. Continue?',
    'dragDrop.processing': 'Processing {0} ({1}/{2})',
    'dragDrop.directoryReadFailed': 'Failed to read directory: {0}',
    'dragDrop.emptyFileName': 'Skipping file with invalid name',
    'dragDrop.cancelled': 'Upload cancelled',
    'dragDrop.mkdirFailed': 'Cannot create target directory: {0}',

    // prefillParamsViewProvider.ts
    'prefillParamsViewProvider.noWorkspace': 'No workspace folder found',
    'prefillParams.title': 'Prefill Parameters',
    'prefillParams.groupTitle': 'Environment & Agents',
    'prefillParams.envModuleTitle': 'Environment Module Prefill Parameters',
    'prefillParams.agentTitle': 'Agent Class Prefill Parameters',

    // projectStructureProvider.ts - settings
    'projectStructure.settings': 'Settings',
    'projectStructure.agentSkills': 'Agent Skills',
    'projectStructure.extensionSkills': 'AgentSociety Skills',
    'projectStructure.agentSkillsScan': 'Scan Skills',
    'projectStructure.agentSkillsImport': 'Import Skill',
    'projectStructure.agentSkillsBuiltin': 'Built-in Skills',
    'projectStructure.agentSkillsCustom': 'Custom Skills',
    'projectStructure.agentSkillsEmpty': 'No Skills found. Click to scan or import.',
    'projectStructure.skillEnabled': 'Enabled',
    'projectStructure.skillDisabled': 'Disabled',
    'projectStructure.skillPriority': 'Priority',
    'projectStructure.skillRemove': 'Remove Skill',
    'projectStructure.skillRemoveConfirm': 'Are you sure you want to remove custom skill "{0}"? This action cannot be undone.',
    'projectStructure.skillImportLocal': 'Import Skill from local directory',
    'projectStructure.skillImportPlaceholder': 'Select Skill import method',
    'projectStructure.extensionSkillsUpdate': 'Update Skills',
    'projectStructure.extensionSkillsUpdateSuccess': 'Updated {0} Skills',
    'projectStructure.extensionSkillsUpdateFailed': 'Failed to update Skills: {0}',

    // backendManager.ts
    'backendManager.openSettings': 'Open Settings',
    'backendManager.configInsufficient': 'Configuration is insufficient to start backend service',
    'backendManager.statusBar.restart': 'Restart Backend',
    'backendManager.statusBar.stop': 'Stop Backend',
    'backendManager.statusBar.start': 'Start Backend',
    'backendManager.statusBar.logs': 'Show Logs',
    'backendManager.statusBar.status': 'Show Status',
    'backendManager.statusBar.config': 'Open Configuration',
    'backendManager.statusBar.tooltip': 'Click to show action menu',
    'backendManager.statusBar.placeholder': 'Select action',

    // configPageViewProvider.ts
    'configPage.title': 'AI Social Scientist Configuration',
    'configPage.noWorkspace': 'Please open a workspace folder first. Configuration will be saved in the current workspace.',
    'configPage.openWorkspace': 'Open Workspace',

    // customModules
    'customModules.noWorkspace': 'Workspace folder not found',
    'customModules.scanning': 'Scanning custom modules...',
    'customModules.scanSuccess': 'Scan completed',
    'customModules.scanFailed': 'Scan failed: {0}',
    'customModules.testing': 'Testing custom modules...',
    'customModules.testSuccess': 'Test completed',
    'customModules.testFailed': 'Test failed: {0}',
    'customModules.noModules': 'No custom modules found',
    'customModules.listFailed': 'Failed to get module list: {0}',
    'customModules.syncAssistant.updating': 'Syncing AI assistant resources...',
    'customModules.syncAssistant.success': 'AI assistant resources synced: {0} skill file(s), {1}',
    'customModules.syncAssistant.claudeMdUpdated': 'CLAUDE.md updated',
    'customModules.syncAssistant.failed': 'Failed to sync AI assistant resources: {0}',

    // workspace fix
    'workspaceFix.healthy': 'Workspace directory structure is complete, no fix needed',
    'workspaceFix.fixed': 'Workspace fixed, created {0} items',
    'workspaceFix.failed': 'Fix failed: {0}',
    'workspaceFix.confirm': 'Detected {0} missing items in workspace:\n{1}\n\nFix now?',

    // projectStructureProvider.ts - custom modules
    'projectStructure.customModules': 'Custom Modules',
    'projectStructure.customAgents': 'Custom Agents',
    'projectStructure.customEnvs': 'Custom Environments',
    'projectStructure.customScan': 'Scan Modules',
    'projectStructure.customTest': 'Test Modules',

    // projectStructureProvider.ts - analysis reports
    'projectStructure.presentation': 'Analysis Reports',
    'projectStructure.synthesis': 'Synthesis Reports',
    'projectStructure.reportHtml': 'HTML Report',
    'projectStructure.reportMd': 'Markdown Report',
    'projectStructure.analysisData': 'Analysis Data',
    'projectStructure.reportCharts': 'Charts',
    'projectStructure.reportAssets': 'Assets',
    'projectStructure.reportHtmlZh': 'Chinese HTML Report',
    'projectStructure.reportMdZh': 'Chinese Markdown Report',
    'projectStructure.reportHtmlEn': 'English HTML Report',
    'projectStructure.reportMdEn': 'English Markdown Report',
    'projectStructure.openReplay': 'Open Replay',
    'projectStructure.literatureIndex': 'Literature Index',
    'projectStructure.articles': 'articles',
    'projectStructure.files': 'files',
    'projectStructure.pdfFiles': 'PDF Papers',
    'projectStructure.mdFiles': 'Markdown Notes',
    'projectStructure.jsonFiles': 'JSON Files',
    'projectStructure.experimentStatus': 'Experiment Status',
    'projectStructure.startTime': 'Start Time',
    'projectStructure.endTime': 'End Time',
    'projectStructure.statusCompleted': 'Experiment completed',
    'projectStructure.statusRunning': 'Experiment running',
    'projectStructure.statusFailed': 'Experiment failed',
    'projectStructure.statusPaused': 'Experiment paused',
    'projectStructure.experiments': 'Experiments',
    'projectStructure.completed': 'Completed',
    'projectStructure.running': 'Running',
    'projectStructure.datasets': 'Datasets',
    'projectStructure.datasetItem': 'Dataset',

    // projectStructureProvider.ts - skills update
    'projectStructure.updateSkills.step1': 'Updating Skills - Step 1/2: AgentSociety Skills',
    'projectStructure.updateSkills.step2': 'Updating Skills - Step 2/2: Official Office Skills',
    'projectStructure.updateSkills.success': '✅ Skills update complete!\n\n',
    'projectStructure.updateSkills.agentsociety': '✓ AgentSociety skills: {0} items\n',
    'projectStructure.updateSkills.office': '✓ Official office skills: {0} items (pdf, docx, xlsx, pptx)\n\n',
    'projectStructure.updateSkills.total': 'Total: {0} items',
    'projectStructure.updateSkills.partialIssues': '⚠️ Skills update completed with issues\n\n',
    'projectStructure.updateSkills.officeFailed': '✗ Official office skills: 0 items (copy failed)\n\n',
    'projectStructure.updateSkills.partialSuccess': '⚠️ Skills update partially completed\n\n',
    'projectStructure.updateSkills.partialOffice': '✓ Official office skills: {0} items\n\n',
    'projectStructure.updateSkills.checkExtension': '📋 Please check your extension installation.',
    'projectStructure.updateSkills.viewDetails': 'View Details',
    'projectStructure.updateSkills.viewInstructions': 'View Instructions',
    'projectStructure.updateSkills.close': 'Close',
    'projectStructure.updateSkills.ok': 'OK',
    'projectStructure.updateSkills.failed': 'Skills update failed: {0}',
    'projectStructure.updateSkills.viewOutput': 'View Output',
  },
};

/**
 * 获取当前语言设置
 * VSCode 的语言设置可以通过 vscode.env.language 获取
 */
function getCurrentLanguage(): string {
  // 尝试从 VSCode 配置获取语言，如果没有则使用系统语言
  const config = vscode.workspace.getConfiguration('aiSocialScientist');
  const language = config.get<string>('language') || vscode.env.language || 'zh-CN';

  // 支持的语言列表
  const supportedLanguages = ['zh-CN', 'en-US'];

  // 如果语言是 zh 或 zh-CN，返回 zh-CN
  if (language.startsWith('zh')) {
    return 'zh-CN';
  }

  // 如果语言是 en 或 en-US，返回 en-US
  if (language.startsWith('en')) {
    return 'en-US';
  }

  // 默认返回中文
  return 'zh-CN';
}

/**
 * 本地化字符串
 * 
 * @param key - 翻译键
 * @param args - 可选的参数，用于替换 {0}, {1} 等占位符
 * @returns 翻译后的字符串
 * 
 * @example
 * localize('extension.initProject.success', 'My Topic')
 * // 返回: "研究项目已初始化：My Topic"
 */
export function localize(key: string, ...args: (string | number)[]): string {
  const language = getCurrentLanguage();
  const translation = translations[language]?.[key] || translations['zh-CN'][key] || key;

  // 替换占位符 {0}, {1}, {2} 等
  return translation.replace(/\{(\d+)\}/g, (match, index) => {
    const argIndex = parseInt(index, 10);
    return args[argIndex] !== undefined ? String(args[argIndex]) : match;
  });
}

/**
 * 获取当前语言代码
 */
export function getCurrentLanguageCode(): string {
  return getCurrentLanguage();
}
