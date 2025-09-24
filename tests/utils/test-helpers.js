const fs = require('fs').promises;
const path = require('path');

class TestHelpers {
  constructor(page) {
    this.page = page;
    this.baseURL = 'http://localhost:3000';
    this.backendURL = 'http://localhost:8000';
    this.backendURL2 = 'http://localhost:8001';
  }

  // Authentication helpers
  async login(email = 'test@example.com', password = 'password') {
    await this.page.goto('/login');
    await this.page.fill('[data-testid="email-input"]', email);
    await this.page.fill('[data-testid="password-input"]', password);
    await this.page.click('[data-testid="login-button"]');
    await this.page.waitForURL('/dashboard');
  }

  async logout() {
    await this.page.click('[data-testid="logout-button"]');
    await this.page.waitForURL('/login');
  }

  // Project management helpers
  async createProject(name = 'Test Project', description = 'Test project description') {
    await this.page.click('[data-testid="create-project-button"]');
    await this.page.fill('[data-testid="project-name-input"]', name);
    await this.page.fill('[data-testid="project-description-input"]', description);
    await this.page.click('[data-testid="save-project-button"]');
    await this.page.waitForSelector('[data-testid="project-created-success"]');
  }

  // File upload helpers
  async uploadVideo(filePath) {
    const fileInput = await this.page.locator('[data-testid="video-upload-input"]');
    await fileInput.setInputFiles(filePath);
    await this.page.waitForSelector('[data-testid="upload-success"]', { timeout: 30000 });
  }

  // ML model helpers
  async selectMLModel(modelType = 'yolov8') {
    await this.page.selectOption('[data-testid="model-select"]', modelType);
    await this.page.waitForSelector('[data-testid="model-loaded"]', { timeout: 30000 });
  }

  async startDetection() {
    await this.page.click('[data-testid="start-detection-button"]');
    await this.page.waitForSelector('[data-testid="detection-started"]');
  }

  // WebSocket helpers
  async waitForWebSocketConnection() {
    await this.page.waitForFunction(() => {
      return window.websocketConnected === true;
    }, { timeout: 10000 });
  }

  async waitForDetectionResults() {
    await this.page.waitForSelector('[data-testid="detection-results"]', { timeout: 60000 });
  }

  // Performance monitoring
  async measurePerformance(operation) {
    const startTime = Date.now();
    await operation();
    const endTime = Date.now();
    return endTime - startTime;
  }

  async captureNetworkRequests() {
    const requests = [];
    this.page.on('request', request => {
      requests.push({
        url: request.url(),
        method: request.method(),
        headers: request.headers(),
        timestamp: Date.now()
      });
    });
    return requests;
  }

  // Screenshot and reporting helpers
  async takeScreenshot(name, fullPage = true) {
    const screenshotPath = path.join(__dirname, '../screenshots', `${name}-${Date.now()}.png`);
    await this.page.screenshot({ 
      path: screenshotPath, 
      fullPage,
      type: 'png' 
    });
    return screenshotPath;
  }

  async saveTestResults(testName, results) {
    const resultsPath = path.join(__dirname, '../test-results', `${testName}.json`);
    await fs.writeFile(resultsPath, JSON.stringify(results, null, 2));
    return resultsPath;
  }

  // Backend API helpers
  async callBackendAPI(endpoint, options = {}) {
    const response = await this.page.request.get(`${this.backendURL}${endpoint}`, options);
    return response;
  }

  async testBackendHealth() {
    const response = await this.callBackendAPI('/health');
    return response.status() === 200;
  }

  // Hardware integration helpers
  async testLabJackConnection() {
    const response = await this.callBackendAPI('/hardware/labjack/status');
    return response.json();
  }

  // Error handling helpers
  async captureConsoleErrors() {
    const errors = [];
    this.page.on('console', message => {
      if (message.type() === 'error') {
        errors.push({
          text: message.text(),
          timestamp: Date.now()
        });
      }
    });
    return errors;
  }

  async captureNetworkErrors() {
    const errors = [];
    this.page.on('requestfailed', request => {
      errors.push({
        url: request.url(),
        error: request.failure().errorText,
        timestamp: Date.now()
      });
    });
    return errors;
  }

  // Utility methods
  async waitForElement(selector, timeout = 10000) {
    await this.page.waitForSelector(selector, { timeout });
  }

  async getElementText(selector) {
    return await this.page.textContent(selector);
  }

  async clickAndWait(selector, waitSelector) {
    await this.page.click(selector);
    if (waitSelector) {
      await this.page.waitForSelector(waitSelector);
    }
  }

  // ML pipeline testing helpers
  async testYOLOInference(inputData) {
    const response = await this.page.request.post(`${this.backendURL}/ml/yolo/inference`, {
      data: inputData
    });
    return response.json();
  }

  async monitorInferencePerformance() {
    const startTime = performance.now();
    const response = await this.testYOLOInference({ test: true });
    const endTime = performance.now();
    
    return {
      response,
      duration: endTime - startTime,
      timestamp: Date.now()
    };
  }
}

module.exports = TestHelpers;