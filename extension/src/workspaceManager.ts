/**
 * Workspace Manager - Local file operations
 *
 * Handles workspace file operations locally instead of using backend APIs.
 *
 * 关联文件：
 * - @extension/src/projectStructureProvider.ts - 树视图调用WorkspaceManager初始化工作区
 * - @extension/src/extension.ts - 主入口，创建WorkspaceManager实例
 * - @extension/skills/ - Skills目录，复制到工作区
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export interface WorkspaceInitOptions {
  topic: string;
  createStructure?: boolean;
  progress?: vscode.Progress<{ message?: string; increment?: number }>;
}

export interface WorkspaceInitResult {
  success: boolean;
  message: string;
  filesCreated?: string[];
}

export class WorkspaceManager {
  private outputChannel: vscode.OutputChannel;
  private skillsSourcePath: string;

  constructor(context: vscode.ExtensionContext) {
    this.outputChannel = vscode.window.createOutputChannel('Workspace Manager');
    // Skills are stored in the extension's skills directory
    this.skillsSourcePath = path.join(context.extensionPath, 'skills');
  }

  private log(message: string): void {
    const timestamp = new Date().toISOString();
    this.outputChannel.appendLine(`[${timestamp}] ${message}`);
  }

  /**
   * Get workspace folder path
   */
  getWorkspacePath(): string | null {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    return workspaceFolder ? workspaceFolder.uri.fsPath : null;
  }

  /**
   * Initialize workspace
   */
  async init(options: WorkspaceInitOptions): Promise<WorkspaceInitResult> {
    const workspacePath = this.getWorkspacePath();
    if (!workspacePath) {
      return {
        success: false,
        message: 'No workspace folder open',
      };
    }

    const filesCreated: string[] = [];

    const reportProgress = (message: string) => {
      if (options.progress) {
        options.progress.report({ message });
      }
      this.log(message);
    };

    try {
      reportProgress('正在创建基础文件...');

      // Create/update .gitignore to exclude .env
      const gitignorePath = path.join(workspacePath, '.gitignore');
      this.updateGitignore(gitignorePath);

      // Create .env file from EnvManager example if it doesn't exist
      const envPath = path.join(workspacePath, '.env');
      if (!fs.existsSync(envPath)) {
        const { EnvManager } = await import('./envManager');
        const envManager = new EnvManager();
        envManager.createEnvFromExample();
        filesCreated.push('.env (from example)');
      }

      // Verify .env has required API key before proceeding with CLI calls
      const { EnvManager } = await import('./envManager');
      const envManager = new EnvManager();
      const envConfig = envManager.readEnv();
      const hasApiKey = !!(envConfig.llmApiKey?.trim());

      if (!hasApiKey) {
        this.log('Warning: .env file exists but LLM API key is not configured');
        // Still create basic structure, but skip CLI-dependent operations
        return {
          success: false,
          message: '工作区初始化失败：请在 .env 文件中配置 LLM API 密钥后重试',
          filesCreated,
        };
      }

      // Create TOPIC.md
      const topicPath = path.join(workspacePath, 'TOPIC.md');
      if (!fs.existsSync(topicPath)) {
        fs.writeFileSync(topicPath, `# ${options.topic}\n\n`, 'utf-8');
        filesCreated.push('TOPIC.md');
        this.log(`Created: ${topicPath}`);
      }

      // Create papers directory
      const papersDir = path.join(workspacePath, 'papers');
      if (!fs.existsSync(papersDir)) {
        fs.mkdirSync(papersDir, { recursive: true });
        filesCreated.push('papers/');
        this.log(`Created: ${papersDir}`);
      }

      // Create user_data directory for user data storage
      const userDataDir = path.join(workspacePath, 'user_data');
      if (!fs.existsSync(userDataDir)) {
        fs.mkdirSync(userDataDir, { recursive: true });
        filesCreated.push('user_data/');
        this.log(`Created: ${userDataDir}`);
      }

      // Initialize custom modules using agentsociety2 CLI
      reportProgress('正在初始化自定义模块...');

      const customDir = path.join(workspacePath, 'custom');
      if (!fs.existsSync(customDir)) {
        const initCustomResult = await this.initCustomModules(workspacePath, options.progress);
        if (initCustomResult.success) {
          filesCreated.push(...initCustomResult.created);
          this.log(`Custom modules initialized: ${initCustomResult.created.join(', ')}`);
        } else {
          this.log(`Failed to initialize custom modules: ${initCustomResult.message}`);
          // 即使自定义模块初始化失败，也继续创建其他文件
        }
      } else {
        filesCreated.push('custom/ (already exists)');
        this.log(`Custom directory already exists: ${customDir}`);
      }

      reportProgress('正在创建文献索引...');

      // Create literature index
      const indexPath = path.join(papersDir, 'literature_index.json');
      if (!fs.existsSync(indexPath)) {
        const index = {
          version: '1.0',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          entries: [],
        };
        fs.writeFileSync(indexPath, JSON.stringify(index, null, 2), 'utf-8');
        filesCreated.push('papers/literature_index.json');
        this.log(`Created: ${indexPath}`);
      }

      reportProgress('正在创建工作区配置...');

      // Create .agentsociety directory for internal state (prefill_params.json)
      const agentsocietyDir = path.join(workspacePath, '.agentsociety');
      if (!fs.existsSync(agentsocietyDir)) {
        fs.mkdirSync(agentsocietyDir, { recursive: true });
        filesCreated.push('.agentsociety/');
        this.log(`Created: ${agentsocietyDir}`);
      }

      // Create prefill_params.json file
      const prefillParamsPath = path.join(agentsocietyDir, 'prefill_params.json');
      if (!fs.existsSync(prefillParamsPath)) {
        const prefillParams = {
          version: '1.0',
          env_modules: {},
          agents: {}
        };
        fs.writeFileSync(prefillParamsPath, JSON.stringify(prefillParams, null, 2), 'utf-8');
        filesCreated.push('.agentsociety/prefill_params.json');
        this.log(`Created: ${prefillParamsPath}`);
      }

      // Create CLAUDE.md with technical project guidance
      const claudeMdPath = path.join(workspacePath, 'CLAUDE.md');
      if (!fs.existsSync(claudeMdPath)) {
        const claudeMdContent = this.getClaudeMdContent();
        fs.writeFileSync(claudeMdPath, claudeMdContent, 'utf-8');
        filesCreated.push('CLAUDE.md');
        this.log(`Created: ${claudeMdPath}`);
      }

      // Create AGENTS.md as symlink to CLAUDE.md
      const agentsMdPath = path.join(workspacePath, 'AGENTS.md');
      if (!fs.existsSync(agentsMdPath)) {
        try {
          fs.symlinkSync('CLAUDE.md', agentsMdPath);
          filesCreated.push('AGENTS.md (symlink to CLAUDE.md)');
          this.log(`Created symlink: ${agentsMdPath} -> CLAUDE.md`);
        } catch (error) {
          // Symlink creation may fail on Windows or without permissions
          // Fall back to copying the content
          fs.writeFileSync(agentsMdPath, fs.readFileSync(claudeMdPath), 'utf-8');
          filesCreated.push('AGENTS.md (copy of CLAUDE.md)');
          this.log(`Created copy: ${agentsMdPath} (symlink not supported)`);
        }
      }

      reportProgress('正在同步技能文件...');

      // Copy skills to .claude/skills/ (always overwrite for upgrade support)
      const skillsResult = await this.copySkills();
      if (skillsResult.success) {
        this.log(`Skills installed: ${skillsResult.copied.join(', ')}`);
      }

      reportProgress('正在完成初始化...');

      return {
        success: true,
        message: `Workspace initialized for topic: ${options.topic}`,
        filesCreated,
      };
    } catch (error) {
      this.log(`Failed to initialize workspace: ${error}`);
      return {
        success: false,
        message: `初始化工作区失败: ${error}`,
      };
    }
  }

  /**
   * Check if custom modules exist
   */
  getCustomModulesStatus(): {
    customDirExists: boolean;
    agentsDirExists: boolean;
    envsDirExists: boolean;
    agentFilesCount: number;
    envFilesCount: number;
  } {
    const workspacePath = this.getWorkspacePath();
    if (!workspacePath) {
      return {
        customDirExists: false,
        agentsDirExists: false,
        envsDirExists: false,
        agentFilesCount: 0,
        envFilesCount: 0,
      };
    }

    const customDir = path.join(workspacePath, 'custom');
    const agentsDir = path.join(customDir, 'agents');
    const envsDir = path.join(customDir, 'envs');

    let agentFilesCount = 0;
    let envFilesCount = 0;

    if (fs.existsSync(agentsDir)) {
      const files = fs.readdirSync(agentsDir);
      // Count .py files but exclude examples directory
      agentFilesCount = files.filter(f => f.endsWith('.py') && !f.startsWith('__')).length;
    }

    if (fs.existsSync(envsDir)) {
      const files = fs.readdirSync(envsDir);
      // Count .py files but exclude examples directory
      envFilesCount = files.filter(f => f.endsWith('.py') && !f.startsWith('__')).length;
    }

    return {
      customDirExists: fs.existsSync(customDir),
      agentsDirExists: fs.existsSync(agentsDir),
      envsDirExists: fs.existsSync(envsDir),
      agentFilesCount,
      envFilesCount,
    };
  }

  /**
   * List custom modules
   */
  listCustomModules(): { agents: string[]; envs: string[] } {
    const workspacePath = this.getWorkspacePath();
    if (!workspacePath) {
      return { agents: [], envs: [] };
    }

    const agentsDir = path.join(workspacePath, 'custom', 'agents');
    const envsDir = path.join(workspacePath, 'custom', 'envs');

    const agents: string[] = [];
    const envs: string[] = [];

    if (fs.existsSync(agentsDir)) {
      const files = fs.readdirSync(agentsDir);
      for (const file of files) {
        if (file.endsWith('.py') && !file.startsWith('__')) {
          agents.push(file);
        }
      }
    }

    if (fs.existsSync(envsDir)) {
      const files = fs.readdirSync(envsDir);
      for (const file of files) {
        if (file.endsWith('.py') && !file.startsWith('__')) {
          envs.push(file);
        }
      }
    }

    return { agents, envs };
  }

  /**
   * Copy skills to workspace .claude/skills directory and update CLAUDE.md
   */
  async copySkills(): Promise<{ success: boolean; message: string; copied: string[]; claudeMdUpdated: boolean }> {
    const workspacePath = this.getWorkspacePath();
    if (!workspacePath) {
      return {
        success: false,
        message: 'No workspace folder open',
        copied: [],
        claudeMdUpdated: false,
      };
    }

    // Check if skills source directory exists
    if (!fs.existsSync(this.skillsSourcePath)) {
      return {
        success: false,
        message: `Skills source directory not found: ${this.skillsSourcePath}`,
        copied: [],
        claudeMdUpdated: false,
      };
    }

    // Target directory: .claude/skills/
    const targetDir = path.join(workspacePath, '.claude', 'skills');

    // Clear and recreate target directory for overwrite support
    if (fs.existsSync(targetDir)) {
      // Remove all items in the target directory
      const existingItems = fs.readdirSync(targetDir);
      for (const item of existingItems) {
        const itemPath = path.join(targetDir, item);
        try {
          const stat = fs.statSync(itemPath);
          if (stat.isDirectory()) {
            fs.rmSync(itemPath, { recursive: true, force: true });
          } else {
            fs.unlinkSync(itemPath);
          }
          this.log(`Removed existing: ${item}`);
        } catch (error) {
          this.log(`Failed to remove ${item}: ${error}`);
        }
      }
    } else {
      // Create target directory if it doesn't exist
      fs.mkdirSync(targetDir, { recursive: true });
      this.log(`Created directory: ${targetDir}`);
    }

    const copied: string[] = [];
    const skills = fs.readdirSync(this.skillsSourcePath);

    for (const skill of skills) {
      const sourcePath = path.join(this.skillsSourcePath, skill);
      const targetPath = path.join(targetDir, skill);

      const stat = fs.statSync(sourcePath);

      try {
        if (stat.isDirectory()) {
          // Recursively copy directory
          this.copyDirectoryRecursive(sourcePath, targetPath);
          copied.push(skill);
          this.log(`Copied skill directory: ${skill}`);
        } else if (stat.isFile()) {
          // Copy single file
          fs.copyFileSync(sourcePath, targetPath);
          copied.push(skill);
          this.log(`Copied skill file: ${skill}`);
        }
      } catch (error) {
        this.log(`Failed to copy skill ${skill}: ${error}`);
      }
    }

    // Update CLAUDE.md
    let claudeMdUpdated = false;
    const claudeMdPath = path.join(workspacePath, 'CLAUDE.md');
    try {
      const claudeMdContent = this.getClaudeMdContent();
      fs.writeFileSync(claudeMdPath, claudeMdContent, 'utf-8');
      claudeMdUpdated = true;
      this.log(`Updated CLAUDE.md`);
    } catch (error) {
      this.log(`Failed to update CLAUDE.md: ${error}`);
    }

    if (copied.length === 0) {
      return {
        success: false,
        message: 'No skills copied',
        copied: [],
        claudeMdUpdated,
      };
    }

    return {
      success: true,
      message: `Copied ${copied.length} skill(s) to .claude/skills/`,
      copied,
      claudeMdUpdated,
    };
  }

  /**
   * Recursively copy directory
   */
  private copyDirectoryRecursive(source: string, target: string): void {
    // Create target directory
    if (!fs.existsSync(target)) {
      fs.mkdirSync(target, { recursive: true });
    }

    // Read source directory
    const items = fs.readdirSync(source);

    for (const item of items) {
      const sourcePath = path.join(source, item);
      const targetPath = path.join(target, item);
      const stat = fs.statSync(sourcePath);

      if (stat.isDirectory()) {
        // Recursively copy subdirectory
        this.copyDirectoryRecursive(sourcePath, targetPath);
      } else if (stat.isFile()) {
        // Copy file
        fs.copyFileSync(sourcePath, targetPath);
      }
    }
  }

  /**
   * Initialize custom modules using agentsociety2 CLI
   *
   * Note: This requires agentsociety2 to be installed in the Python environment
   * specified by PYTHON_PATH in .env file. The package should be importable as
   * 'agentsociety2.society.workspace'.
   */
  async initCustomModules(
    workspacePath: string,
    progress?: vscode.Progress<{ message?: string; increment?: number }>
  ): Promise<{ success: boolean; message: string; created: string[] }> {
    const { exec } = require('child_process');
    const util = require('util');
    const execPromise = util.promisify(exec);

    const reportProgress = (message: string) => {
      if (progress) {
        progress.report({ message });
      }
      this.log(message);
    };

    try {
      // Read .env to get PYTHON_PATH
      const { EnvManager } = await import('./envManager');
      const envManager = new EnvManager();
      const envConfig = envManager.readEnv();
      const configuredPythonPath = envConfig.pythonPath?.trim();

      // Determine Python command to use
      let pythonCmd = 'python'; // default fallback
      if (configuredPythonPath) {
        pythonCmd = configuredPythonPath;
        this.log(`Using configured PYTHON_PATH: ${pythonCmd}`);
      } else {
        this.log(`PYTHON_PATH not configured, using default: ${pythonCmd}`);
      }

      // Build command using determined Python path
      // Assumes agentsociety2 is installed in the Python environment
      const command = `"${pythonCmd}" -m agentsociety2.society.workspace init-custom --target-dir "${workspacePath}" --json`;

      this.log(`Executing: ${command}`);

      reportProgress('正在执行自定义模块初始化命令...');

      const { stdout, stderr } = await execPromise(
        command,
        { cwd: workspacePath, env: process.env }
      );

      this.log(`Custom modules CLI output: ${stdout}`);
      if (stderr) {
        this.log(`Custom modules CLI stderr: ${stderr}`);
      }

      // Parse JSON output
      const result = JSON.parse(stdout);
      return {
        success: result.success || false,
        message: result.message || '',
        created: result.created || []
      };
    } catch (error: any) {
      this.log(`Failed to initialize custom modules via CLI: ${error.message}`);
      // Fallback: try to create basic directory structure
      try {
        reportProgress('使用备用方案创建目录结构...');

        const customDir = path.join(workspacePath, 'custom');
        const agentsDir = path.join(customDir, 'agents');
        const envsDir = path.join(customDir, 'envs');

        if (!fs.existsSync(agentsDir)) {
          fs.mkdirSync(agentsDir, { recursive: true });
        }
        if (!fs.existsSync(envsDir)) {
          fs.mkdirSync(envsDir, { recursive: true });
        }

        return {
          success: true,
          message: 'Custom modules directory created (CLI unavailable, used fallback)',
          created: ['custom/agents/', 'custom/envs/']
        };
      } catch (fallbackError: any) {
        return {
          success: false,
          message: `初始化自定义模块失败: ${error.message}`,
          created: []
        };
      }
    }
  }

  /**
   * Get skills status in workspace
   */
  getSkillsStatus(): {
    skillsDirExists: boolean;
    installedSkills: string[];
  } {
    const workspacePath = this.getWorkspacePath();
    if (!workspacePath) {
      return {
        skillsDirExists: false,
        installedSkills: [],
      };
    }

    const skillsDir = path.join(workspacePath, '.claude', 'skills');

    if (!fs.existsSync(skillsDir)) {
      return {
        skillsDirExists: false,
        installedSkills: [],
      };
    }

    const installedSkills = fs.readdirSync(skillsDir).filter(f =>
      fs.statSync(path.join(skillsDir, f)).isFile()
    );

    return {
      skillsDirExists: true,
      installedSkills,
    };
  }

  /**
   * Update .gitignore to exclude .env file
   */
  private updateGitignore(gitignorePath: string): void {
    const entriesToAdd = [
      '.env',
      '.claude/',
      '# Python cache files in custom/',
      'custom/**/__pycache__/',
      'custom/**/*.pyc',
      'custom/**/.pytest_cache/',
    ];

    try {
      let content = '';
      if (fs.existsSync(gitignorePath)) {
        content = fs.readFileSync(gitignorePath, 'utf-8');
      }

      const lines = content.split('\n');
      const existingEntries = new Set(
        lines
          .map(l => l.trim())
          .filter(l => l && !l.startsWith('#'))
      );

      let modified = false;
      for (const entry of entriesToAdd) {
        if (!existingEntries.has(entry)) {
          if (!content.endsWith('\n') && content.length > 0) {
            content += '\n';
          }
          content += `${entry}\n`;
          modified = true;
          this.log(`Added to .gitignore: ${entry}`);
        }
      }

      if (modified || !fs.existsSync(gitignorePath)) {
        fs.writeFileSync(gitignorePath, content, 'utf-8');
        this.log(`Updated .gitignore: ${gitignorePath}`);
      }
    } catch (error) {
      this.log(`Failed to update .gitignore: ${error}`);
    }
  }

  /**
   * Get CLAUDE.md content - AI Social Scientist workspace guide
   */
  private getClaudeMdContent(): string {
    return `# CLAUDE.md

This file provides guidance to Claude Code when working in this AI Social Scientist workspace.

**Research Context**: See \`TOPIC.md\` for research topics, goals, and current work.

---

## Python Environment

**CRITICAL**: All skills require \`agentsociety2\` to be installed in the Python environment.

### Finding the Correct Python

The workspace \`.env\` file contains \`PYTHON_PATH\` pointing to the Python environment with agentsociety2 installed:

\`\`\`bash
# Read PYTHON_PATH from .env (with fallback to python3)
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=\${PYTHON_PATH:-python3}

# Use this Python for ALL skill invocations
$PYTHON_PATH .claude/skills/agentsociety-hypothesis/scripts/hypothesis.py list
\`\`\`

### Why PYTHON_PATH Matters

- Dependencies are managed via \`uv\`, not system Python
- Skills auto-load \`.env\` but use the calling Python interpreter
- Always use \`$PYTHON_PATH\` to ensure agentsociety2 is available

---

## Research Workflow (Execution Order)

Follow this sequence for social science research:

\`\`\`
1. Define Research Topic (TOPIC.md)
   └─> Define research question and objectives

2. Literature Review
   └─> agentsociety-literature-search
   └─> agentsociety-web-research

3. Generate Hypothesis
   └─> agentsociety-hypothesis add

4. Initialize Experiment
   └─> agentsociety-experiment-config (validate → prepare → info → run → check)

5. Run Experiment
   └─> agentsociety-run-experiment start

6. Analyze Results
   └─> agentsociety-analysis

7. Generate Report
   └─> agentsociety-synthesize

8. Refine Hypothesis/Experiment
   └─> Repeat from step 3 with new insights
\`\`\`

---

## Workspace Structure

\`\`\`
.
├── TOPIC.md              # Research topic and goals
├── CLAUDE.md             # This file - technical guidance
├── AGENTS.md             # Symlink to CLAUDE.md
├── .env                  # Environment configuration (API keys, PYTHON_PATH, etc)
├── papers/               # Literature storage
│   ├── literature_index.json  # Literature catalog
│   └── literature/            # Individual article summaries
├── user_data/            # User data storage for custom datasets
├── custom/               # Custom Agent and Environment modules
│   ├── agents/               # Custom agent definitions
│   │   └── examples/         # Example agents (reference only)
│   ├── envs/                 # Custom environment modules
│   │   └── examples/         # Example environments (reference only)
│   └── README.md             # Custom module development guide
├── .agentsociety/        # Internal workspace state
│   └── prefill_params.json  # Pre-filled parameters for modules
├── hypothesis_{id}/      # Hypothesis directories
│   ├── HYPOTHESIS.md         # Hypothesis description and groups
│   ├── SIM_SETTINGS.json     # Agent and env module selection
│   └── experiment_{id}/
│       ├── EXPERIMENT.md     # Experiment description
│       ├── init/             # Configuration files (simplified)
│       │   ├── config_params.py  # Parameter generation script
│       │   ├── init_config.json  # Experiment configuration
│       │   └── steps.yaml        # Execution steps
│       ├── run/              # Simulation outputs
│       │   ├── sqlite.db         # Simulation database
│       │   ├── stdout.log        # Standard output
│       │   ├── stderr.log        # Error messages
│       │   └── pid.json          # Process ID file (when running)
│       └── data/             # Analysis results
│           ├── analysis_summary.json
│           ├── report.md
│           └── figures/
└── presentation/         # Synthesized reports
    └── hypothesis_{id}/
        └── experiment_{id}/
            ├── synthesis_report_zh.md
            └── synthesis_report_en.md
\`\`\`

### Directory Notes

- **custom/** - Create your custom Agent and Environment modules here. See \`custom/README.md\` for development guide.
- **user_data/** - Store your custom datasets and data files here for experiment configuration.
- **.agentsociety/** - Internal workspace state, managed by the system.

---

## User Dialogue Style

When interacting with users:

### 1. Academic Tone
- Use academic terminology and maintain professionalism
- Be precise with terminology
- Acknowledge uncertainty and limitations

### 2. Language Matching
- Match the user's language (Chinese or English)
- Maintain consistency throughout the conversation

### 3. Guidance Flow
- Proactively guide users to the next step
- After completing a step, suggest the next action
- Explain the current step's position in the overall research workflow
- Provide optional research paths

### 4. Ask Questions
- Frequently ask questions to clarify user requirements:
- "Which specific research direction are you interested in?"
- "What is the theoretical basis for this hypothesis?"
- "What results do you expect to observe?"
- "How many agents should participate in the experiment?"

---

## Quick Skill Reference

| Skill | Purpose | Example |
|-------|---------|---------|
| \`agentsociety-scan-modules\` | List available agents/envs | \`list --short\` |
| \`agentsociety-hypothesis\` | Manage hypotheses | \`add\`, \`list\`, \`get\` |
| \`agentsociety-experiment-config\` | Generate experiment config | \`validate\`, \`prepare\`, \`run\` |
| \`agentsociety-run-experiment\` | Execute simulations | \`start\`, \`status\`, \`stop\` |
| \`agentsociety-analysis\` | Analyze results | \`--hypothesis-id 1 --experiment-id 1\` |
| \`agentsociety-synthesize\` | Create reports | Bilingual synthesis |

---

## Essential Commands

\`\`\`bash
# Always use PYTHON_PATH from .env
PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
PYTHON_PATH=\${PYTHON_PATH:-python3}

# List available modules
$PYTHON_PATH .claude/skills/agentsociety-scan-modules/scripts/scan_modules.py list

# List hypotheses
$PYTHON_PATH .claude/skills/agentsociety-hypothesis/scripts/hypothesis.py list

# Run experiment
$PYTHON_PATH .claude/skills/agentsociety-run-experiment/scripts/run.py start --hypothesis-id 1 --experiment-id 1
\`\`\`
`;
  }

  /**
   * Dispose
   */
  dispose(): void {
    this.outputChannel.dispose();
  }
}
