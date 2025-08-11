# Claude Flow Windows Installation Guide

## Prerequisites

### System Requirements
- **Operating System**: Windows 10 (1903+) or Windows 11
- **Architecture**: x64 (64-bit)
- **RAM**: Minimum 4GB, Recommended 8GB+
- **Disk Space**: 2GB free space

### Required Software

#### 1. Node.js (Required)
- **Version**: Node.js 18.x or later (LTS recommended)
- **Download**: https://nodejs.org/
- **Installation**: Use the Windows Installer (.msi)
- **Verify**: Open Command Prompt/PowerShell and run:
  ```cmd
  node --version
  npm --version
  ```

#### 2. Git (Required)
- **Version**: Git 2.28.0 or later
- **Download**: https://git-scm.com/download/win
- **Installation**: Use Git for Windows installer
- **Configuration**: During installation, select "Git from the command line and also from 3rd-party software"
- **Verify**: 
  ```cmd
  git --version
  ```

#### 3. Terminal/Shell Options
Choose one of the following:

**Option A: PowerShell (Recommended)**
- Pre-installed on Windows 10/11
- Best compatibility with npm scripts

**Option B: Command Prompt**
- Basic functionality, some features may be limited

**Option C: Git Bash**
- Included with Git for Windows
- Unix-like environment on Windows

#### 4. Claude Code CLI (Required)
- **Installation**: 
  ```cmd
  npm install -g @anthropic/claude
  ```
- **Authentication**: You'll need an Anthropic API key
- **Verify**:
  ```cmd
  claude --version
  ```

## Installation Steps

### Step 1: Download from GitHub

#### Method 1: Git Clone (Recommended)
1. Open PowerShell/Command Prompt/Git Bash
2. Navigate to your desired directory:
   ```cmd
   cd C:\Users\%USERNAME%\Documents
   ```
3. Clone the repository:
   ```cmd
   git clone https://github.com/ruvnet/claude-flow.git
   cd claude-flow
   ```

#### Method 2: Download ZIP
1. Visit https://github.com/ruvnet/claude-flow
2. Click "Code" → "Download ZIP"
3. Extract to your desired location
4. Open terminal in the extracted folder

### Step 2: Install Dependencies
```cmd
npm install
```

### Step 3: Initialize Claude Flow
```cmd
npx claude-flow@alpha init --force
```

### Step 4: Setup MCP Servers (Claude Code Integration)
If using Claude Code CLI:
```cmd
claude mcp add claude-flow npx claude-flow@alpha mcp start
claude mcp add ruv-swarm npx ruv-swarm mcp start
```

### Step 5: Verify Installation
```cmd
npx claude-flow@alpha --version
npx claude-flow@alpha help
```

## Quick Start Commands

### Start a Basic Swarm
```cmd
npx claude-flow@alpha swarm "analyze codebase" --claude
```

### Use Hive Mind Coordination
```cmd
npx claude-flow@alpha hive-mind spawn "your task" --claude
```

### SPARC Development Workflow
```cmd
npx claude-flow@alpha sparc tdd "feature description"
```

## Windows-Specific Considerations

### Execution Policy (PowerShell)
If you encounter execution policy errors:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Path Issues
- Ensure Node.js and Git are in your system PATH
- Restart terminal after installing software
- Use full paths if commands aren't recognized

### Long Path Support
Enable long path support in Windows (for deep node_modules):
1. Run as Administrator: `gpedit.msc`
2. Navigate: Computer Configuration → Administrative Templates → System → Filesystem
3. Enable "Enable Win32 long paths"

### Antivirus Considerations
- Add your project folder to antivirus exclusions
- Claude Flow creates many small files that may trigger false positives

## Troubleshooting

### Common Issues

#### "npx command not found"
- Ensure Node.js is properly installed
- Restart terminal after Node.js installation
- Check PATH environment variable

#### "Permission denied" errors
- Run terminal as Administrator
- Check file/folder permissions
- Ensure antivirus isn't blocking file creation

#### MCP Server Connection Issues
- Verify Claude Code CLI is installed and authenticated
- Check network connectivity
- Restart Claude Code CLI: `claude restart`

#### Git Clone Issues
- Check firewall/proxy settings
- Use HTTPS instead of SSH: `git clone https://...`
- Verify Git is properly installed

### Getting Help
- GitHub Issues: https://github.com/ruvnet/claude-flow/issues
- Documentation: Check `.claude/commands/` folder after initialization
- Discord/Community: Links in main repository README

## Next Steps

After successful installation:

1. **Explore Commands**: `ls .claude/commands/` to see available documentation
2. **Try SPARC Workflow**: Use `/sparc` slash command in Claude Code
3. **Setup GitHub Integration**: Run `.claude/helpers/github-setup.sh` (in Git Bash)
4. **Configure Memory**: Explore memory management with MCP tools
5. **Join Community**: Participate in discussions and contribute improvements

## Performance Tips

- Use SSD storage for better performance
- Increase Node.js memory limit for large projects: `NODE_OPTIONS="--max-old-space-size=8192"`
- Enable Windows Developer Mode for better file system performance
- Use Windows Terminal for enhanced experience

---

**Note**: This guide assumes the latest version of Claude Flow v2.0.0. Commands and features may vary with different versions.