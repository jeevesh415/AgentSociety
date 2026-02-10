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

    // extension.ts - parseWithMinerU
    'extension.parseMinerU.noFile': '无法解析：未选择有效的文件',
    'extension.parseMinerU.noWorkspace': '未找到工作区文件夹',
    'extension.parseMinerU.unsupportedFormat': 'MinerU解析目前仅支持PDF文件',
    'extension.parseMinerU.parsing': '正在解析 {0}...',
    'extension.parseMinerU.success': '成功解析文件: {0}',
    'extension.parseMinerU.openFile': '打开文件',
    'extension.parseMinerU.failed': '解析失败: {0}',

    // projectStructureProvider.ts
    'projectStructure.noWorkspace': '未找到工作区文件夹',
    'projectStructure.literature': '文献库',
    'projectStructure.userData': '用户数据',
    'projectStructure.resultsDatabase': 'Results Database',
    'projectStructure.init': 'Init: {0}',
    'projectStructure.aiChat': 'AI 对话',
    'projectStructure.researchTopic': '研究话题',
    'projectStructure.openAiChat': '打开AI对话',
    'projectStructure.simSettings': '模拟设置',
    'projectStructure.hypothesis': '假设',
    'projectStructure.experiment': '实验',
    'projectStructure.initWorkspace.warnExists': '检测到 .agentsociety 文件夹已存在。重新初始化将覆盖它，这可能会导致长期记忆丢失。是否继续？',
    'projectStructure.initWorkspace.confirm': '确认',
    'projectStructure.initWorkspace.cancel': '取消',
    'projectStructure.initWorkspace.failed': '初始化失败: {0}',

    // paperWatcher.ts
    'paperWatcher.newFile': '发现新文件: {0}',
    'paperWatcher.parsePrompt': '是否使用MinerU解析该文档？',
    'paperWatcher.parse': '解析',
    'paperWatcher.later': '稍后',
    'paperWatcher.dontAsk': '不再提示',
    'paperWatcher.skipped': '已跳过文件 {0}，将不再提示解析该文件',
    'paperWatcher.parsing': '正在解析 {0}...',
    'paperWatcher.success': '成功解析文件: {0}',
    'paperWatcher.parsedFile': '解析文件: {0}',
    'paperWatcher.failed': '解析文件失败: {0}',
    'paperWatcher.error': '解析文件时出错: {0}',

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

    // chatWebviewProvider.ts
    'chatWebview.noBackend': '无法连接到后端服务 ({0})。请确保后端服务正在运行。',
    'chatWebview.noWorkspace': '请先打开一个工作区文件夹。AI Social Scientist 需要在工作区中运行。',
    'chatWebview.chatFailed': '对话失败: {0}',
    'chatWebview.toolFailed': '工具执行失败: {1} - {0}',
    'chatWebview.filesSaved': '已保存 {0} 个文献文件到工作区的 papers 目录',

    // prefillParamsViewProvider.ts
    'prefillParamsViewProvider.noWorkspace': '未找到工作区文件夹',
    'prefillParams.title': '预填充参数',
    'prefillParams.groupTitle': '环境与智能体',
    'prefillParams.envModuleTitle': '环境模块预置参数',
    'prefillParams.agentTitle': '智能体类预置参数',

    // projectStructureProvider.ts - settings
    'projectStructure.settings': '配置设置',

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
  },
  'en-US': {
    // extension.ts
    'extension.activate': 'AI Social Scientist extension is now active!',
    'extension.initProject.prompt': 'Enter research topic',
    'extension.initProject.placeholder': 'e.g., Social media influence on political opinions',
    'extension.initProject.success': 'Research project initialized: {0}',
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
    'projectStructure.aiChat': 'AI Chat',
    'projectStructure.researchTopic': 'Research Topic',
    'projectStructure.openAiChat': 'Open AI Chat',
    'projectStructure.simSettings': 'SIM Settings',
    'projectStructure.hypothesis': 'Hypothesis',
    'projectStructure.experiment': 'Experiment',
    'projectStructure.initWorkspace.warnExists': 'The .agentsociety folder already exists. Re-initializing will overwrite it, which may lead to loss of long-term memory. Do you want to continue?',
    'projectStructure.initWorkspace.confirm': 'Confirm',
    'projectStructure.initWorkspace.cancel': 'Cancel',
    'projectStructure.initWorkspace.failed': 'Initialization failed: {0}',

    // paperWatcher.ts
    'paperWatcher.newFile': 'New file detected: {0}',
    'paperWatcher.parsePrompt': 'Would you like to parse this document with MinerU?',
    'paperWatcher.parse': 'Parse',
    'paperWatcher.later': 'Later',
    'paperWatcher.dontAsk': "Don't ask again",
    'paperWatcher.skipped': 'Skipped file {0}, will not prompt to parse this file again',
    'paperWatcher.parsing': 'Parsing {0}...',
    'paperWatcher.success': 'Successfully parsed file: {0}',
    'paperWatcher.parsedFile': 'Parsed file: {0}',
    'paperWatcher.failed': 'Failed to parse file: {0}',
    'paperWatcher.error': 'Error parsing file: {0}',

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

    // chatWebviewProvider.ts
    'chatWebview.noBackend': 'Cannot connect to backend service ({0}). Please ensure the backend service is running.',
    'chatWebview.noWorkspace': 'Please open a workspace folder first. AI Social Scientist requires a workspace to run.',
    'chatWebview.chatFailed': 'Chat failed: {0}',
    'chatWebview.toolFailed': 'Tool execution failed: {1} - {0}',
    'chatWebview.filesSaved': 'Saved {0} literature file(s) to papers directory in workspace',

    // prefillParamsViewProvider.ts
    'prefillParamsViewProvider.noWorkspace': 'No workspace folder found',
    'prefillParams.title': 'Prefill Parameters',
    'prefillParams.groupTitle': 'Environment & Agents',
    'prefillParams.envModuleTitle': 'Environment Module Prefill Parameters',
    'prefillParams.agentTitle': 'Agent Class Prefill Parameters',

    // projectStructureProvider.ts - settings
    'projectStructure.settings': 'Settings',

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

