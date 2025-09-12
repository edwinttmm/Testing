#!/usr/bin/env node

/**
 * Agent Coordination System
 * Prevents conflicts and coordinates TypeScript fixes between multiple agents
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class AgentCoordinationSystem {
  constructor() {
    this.coordinationPath = path.join(__dirname, 'agent-coordination.json');
    this.logPath = path.join(__dirname, 'agent-coordination.log');
    this.lockPath = path.join(__dirname, 'agent-locks');
    this.activeAgents = new Map();
    this.fileReservations = new Map();
    
    // Ensure lock directory exists
    if (!fs.existsSync(this.lockPath)) {
      fs.mkdirSync(this.lockPath, { recursive: true });
    }
  }

  log(message, level = 'INFO') {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] [${level}] ${message}`;
    
    console.log(logMessage);
    fs.appendFileSync(this.logPath, logMessage + '\n');
  }

  registerAgent(agentId, agentType, workingFiles = []) {
    const agent = {
      id: agentId,
      type: agentType,
      registeredAt: new Date().toISOString(),
      workingFiles: workingFiles,
      status: 'active',
      lastActivity: new Date().toISOString()
    };
    
    this.activeAgents.set(agentId, agent);
    
    // Reserve files for this agent
    workingFiles.forEach(file => {
      this.fileReservations.set(file, agentId);
    });
    
    this.saveCoordinationState();
    this.log(`📝 Agent registered: ${agentId} (${agentType}) - Files: ${workingFiles.join(', ')}`, 'INFO');
    
    return agent;
  }

  checkFileConflicts(agentId, requestedFiles) {
    const conflicts = [];
    
    for (const file of requestedFiles) {
      const reservedBy = this.fileReservations.get(file);
      if (reservedBy && reservedBy !== agentId) {
        conflicts.push({
          file: file,
          conflictWith: reservedBy,
          conflictType: 'file-reservation'
        });
      }
    }
    
    return conflicts;
  }

  requestFileAccess(agentId, files) {
    const conflicts = this.checkFileConflicts(agentId, files);
    
    if (conflicts.length > 0) {
      this.log(`🚨 File conflicts detected for agent ${agentId}:`, 'WARN');
      conflicts.forEach(conflict => {
        this.log(`   ${conflict.file} - Reserved by ${conflict.conflictWith}`, 'WARN');
      });
      
      return {
        granted: false,
        conflicts: conflicts,
        suggestion: this.generateConflictResolution(conflicts)
      };
    }
    
    // Grant access
    files.forEach(file => {
      this.fileReservations.set(file, agentId);
    });
    
    this.saveCoordinationState();
    this.log(`✅ File access granted to ${agentId}: ${files.join(', ')}`, 'INFO');
    
    return {
      granted: true,
      files: files
    };
  }

  releaseFileAccess(agentId, files) {
    files.forEach(file => {
      if (this.fileReservations.get(file) === agentId) {
        this.fileReservations.delete(file);
      }
    });
    
    this.saveCoordinationState();
    this.log(`🔓 File access released by ${agentId}: ${files.join(', ')}`, 'INFO');
  }

  generateConflictResolution(conflicts) {
    const suggestions = [];
    
    for (const conflict of conflicts) {
      suggestions.push(`Wait for agent ${conflict.conflictWith} to finish with ${conflict.file}`);
      suggestions.push(`Work on different files first`);
      suggestions.push(`Coordinate directly with ${conflict.conflictWith}`);
    }
    
    return suggestions;
  }

  getAgentWorkload() {
    const workload = {
      totalAgents: this.activeAgents.size,
      agentDetails: [],
      fileReservations: Object.fromEntries(this.fileReservations),
      coordinationHealth: this.assessCoordinationHealth()
    };
    
    this.activeAgents.forEach((agent, id) => {
      workload.agentDetails.push({
        id: id,
        type: agent.type,
        workingFiles: agent.workingFiles,
        status: agent.status,
        activeFor: Date.now() - new Date(agent.registeredAt).getTime()
      });
    });
    
    return workload;
  }

  assessCoordinationHealth() {
    const totalConflicts = this.countPotentialConflicts();
    const activeAgents = this.activeAgents.size;
    
    if (totalConflicts === 0) {
      return 'excellent';
    } else if (totalConflicts < 3) {
      return 'good';
    } else if (totalConflicts < 10) {
      return 'fair';
    } else {
      return 'poor';
    }
  }

  countPotentialConflicts() {
    const fileCounts = new Map();
    
    this.activeAgents.forEach(agent => {
      agent.workingFiles.forEach(file => {
        fileCounts.set(file, (fileCounts.get(file) || 0) + 1);
      });
    });
    
    let conflicts = 0;
    fileCounts.forEach(count => {
      if (count > 1) conflicts += count - 1;
    });
    
    return conflicts;
  }

  provideFeedbackToAgents() {
    const feedback = {
      timestamp: new Date().toISOString(),
      systemStatus: 'operational',
      coordinationHealth: this.assessCoordinationHealth(),
      activeAgents: this.activeAgents.size,
      fileConflicts: this.countPotentialConflicts(),
      recommendations: this.getCoordinationRecommendations(),
      currentWorkload: this.getAgentWorkload()
    };
    
    // Save feedback for agents to read
    const feedbackPath = path.join(__dirname, 'agent-coordination-feedback.json');
    fs.writeFileSync(feedbackPath, JSON.stringify(feedback, null, 2));
    
    this.log(`📢 Coordination feedback updated for ${this.activeAgents.size} agents`, 'INFO');
    
    return feedback;
  }

  getCoordinationRecommendations() {
    const recommendations = [];
    
    const conflictCount = this.countPotentialConflicts();
    
    if (conflictCount === 0) {
      recommendations.push('✅ No conflicts detected - coordination working well');
    } else {
      recommendations.push(`⚠️ ${conflictCount} potential file conflicts - coordinate file access`);
    }
    
    if (this.activeAgents.size > 5) {
      recommendations.push('👥 High agent count - ensure clear task division');
    }
    
    recommendations.push('🔄 Use real-time monitoring for immediate feedback');
    recommendations.push('📋 Check coordination feedback regularly');
    
    return recommendations;
  }

  saveCoordinationState() {
    const state = {
      activeAgents: Object.fromEntries(this.activeAgents),
      fileReservations: Object.fromEntries(this.fileReservations),
      lastUpdated: new Date().toISOString(),
      summary: {
        totalAgents: this.activeAgents.size,
        reservedFiles: this.fileReservations.size,
        coordinationHealth: this.assessCoordinationHealth()
      }
    };
    
    fs.writeFileSync(this.coordinationPath, JSON.stringify(state, null, 2));
  }

  loadCoordinationState() {
    try {
      if (fs.existsSync(this.coordinationPath)) {
        const state = JSON.parse(fs.readFileSync(this.coordinationPath, 'utf8'));
        this.activeAgents = new Map(Object.entries(state.activeAgents || {}));
        this.fileReservations = new Map(Object.entries(state.fileReservations || {}));
      }
    } catch (error) {
      this.log(`Failed to load coordination state: ${error.message}`, 'ERROR');
    }
  }

  cleanupInactiveAgents() {
    const now = Date.now();
    const inactivityThreshold = 5 * 60 * 1000; // 5 minutes
    
    let cleaned = 0;
    
    this.activeAgents.forEach((agent, id) => {
      const lastActivity = new Date(agent.lastActivity).getTime();
      if (now - lastActivity > inactivityThreshold) {
        this.activeAgents.delete(id);
        
        // Release file reservations
        agent.workingFiles.forEach(file => {
          if (this.fileReservations.get(file) === id) {
            this.fileReservations.delete(file);
          }
        });
        
        cleaned++;
      }
    });
    
    if (cleaned > 0) {
      this.saveCoordinationState();
      this.log(`🧹 Cleaned up ${cleaned} inactive agents`, 'INFO');
    }
    
    return cleaned;
  }
}

// CLI interface
if (require.main === module) {
  const coordinator = new AgentCoordinationSystem();
  const command = process.argv[2];
  
  switch (command) {
    case 'register':
      const agentId = process.argv[3];
      const agentType = process.argv[4];
      const files = process.argv.slice(5);
      coordinator.loadCoordinationState();
      coordinator.registerAgent(agentId, agentType, files);
      break;
    case 'request':
      const requesterId = process.argv[3];
      const requestedFiles = process.argv.slice(4);
      coordinator.loadCoordinationState();
      const result = coordinator.requestFileAccess(requesterId, requestedFiles);
      console.log(JSON.stringify(result, null, 2));
      break;
    case 'release':
      const releaserId = process.argv[3];
      const releasedFiles = process.argv.slice(4);
      coordinator.loadCoordinationState();
      coordinator.releaseFileAccess(releaserId, releasedFiles);
      break;
    case 'feedback':
      coordinator.loadCoordinationState();
      console.log(JSON.stringify(coordinator.provideFeedbackToAgents(), null, 2));
      break;
    case 'workload':
      coordinator.loadCoordinationState();
      console.log(JSON.stringify(coordinator.getAgentWorkload(), null, 2));
      break;
    case 'cleanup':
      coordinator.loadCoordinationState();
      const cleanedCount = coordinator.cleanupInactiveAgents();
      console.log(`Cleaned up ${cleanedCount} inactive agents`);
      break;
    default:
      console.log('Agent Coordination System');
      console.log('Usage: node agent-coordination-system.js [command] [args...]');
      console.log('  register <agentId> <agentType> [files...]  - Register new agent');
      console.log('  request <agentId> [files...]              - Request file access');
      console.log('  release <agentId> [files...]              - Release file access');
      console.log('  feedback                                  - Get coordination feedback');
      console.log('  workload                                  - Show current workload');
      console.log('  cleanup                                   - Clean inactive agents');
      break;
  }
}

module.exports = AgentCoordinationSystem;