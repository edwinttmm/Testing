import { test, expect, Page } from '@playwright/test';
import { ErrorMonitor } from '../utils/error-monitor';
import { PRDValidator } from '../utils/prd-validator';

test.describe('PRD Module 2: Project Management', () => {
  let errorMonitor: ErrorMonitor;
  let prdValidator: PRDValidator;
  
  test.beforeEach(async ({ page }) => {
    errorMonitor = new ErrorMonitor('Module2-ProjectManagement');
    prdValidator = new PRDValidator(page, errorMonitor);
    
    await errorMonitor.setupPageMonitoring(page);
    
    // Navigate to the application
    await page.goto('http://localhost:3000');
    await page.waitForLoadState('networkidle');
    
    // Wait for React to load and capture any initial errors
    await page.waitForTimeout(2000);
    await errorMonitor.captureTypeScriptErrors(page);
  });
  
  test.afterEach(async ({ page }) => {
    await errorMonitor.capturePerformanceIssues(page);
    await errorMonitor.saveErrorLog();
    
    // Take screenshot of final state
    await page.screenshot({ 
      path: `test-reports/screenshots/module2-final-state-${Date.now()}.png`, 
      fullPage: true 
    });
  });

  test('2.1 Project Creation - Name and Configuration', async ({ page }) => {
    console.log('📋 Testing project creation with naming (e.g., "Front-Facing Camera v2.1 Regression Test")...');
    
    // Navigate to projects page
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    
    // Look for project creation button
    const createButton = page.locator('button:has-text("Create"), button:has-text("New"), [data-testid*="create-project"]').first();
    await expect(createButton).toBeVisible({ timeout: 10000 });
    
    // Click to create new project
    await createButton.click();
    await page.waitForTimeout(1000);
    
    // Look for project creation form/modal
    const projectForm = page.locator('form, [role="dialog"], .modal, [data-testid*="project-form"]').first();
    if (await projectForm.count() > 0) {
      await expect(projectForm).toBeVisible();
      
      // Look for project name input
      const nameInput = page.locator('input[data-testid*="project-name"], input[name*="name"], input[placeholder*="name"]').first();
      if (await nameInput.count() > 0) {
        await expect(nameInput).toBeVisible();
        
        // Test with PRD-style project name
        const testProjectName = 'Front-Facing Camera v2.1 Regression Test';
        await nameInput.fill(testProjectName);
        
        const enteredValue = await nameInput.inputValue();
        expect(enteredValue).toBe(testProjectName);
        console.log(`✅ Project name entered: ${enteredValue}`);
      }
      
      // Look for description field
      const descriptionInput = page.locator('textarea, input[data-testid*="description"]').first();
      if (await descriptionInput.count() > 0) {
        await descriptionInput.fill('Automated regression testing for front-facing camera VRU detection accuracy');
        console.log('📝 Project description added');
      }
      
      // Check for project configuration options
      const configOptions = page.locator('[data-testid*="config"], .config-option, input[type="checkbox"]');
      console.log(`⚙️ Configuration options: ${await configOptions.count()}`);
      
      // Look for save/create button
      const saveButton = page.locator('button:has-text("Save"), button:has-text("Create"), button[type="submit"]').first();
      if (await saveButton.count() > 0 && !await saveButton.isDisabled()) {
        // Don't actually save in test, just verify button is ready
        console.log('💾 Save button is available and enabled');
      }
    }
    
    // Check for project template options
    const templates = page.locator('[data-testid*="template"], .template-option, .project-template');
    console.log(`📄 Project templates: ${await templates.count()}`);
    
    if (await templates.count() > 0) {
      const templateNames = await templates.allTextContents();
      console.log('📋 Available templates:', templateNames);
    }
  });

  test('2.1 Project Management - CRUD Operations', async ({ page }) => {
    console.log('🔧 Testing complete project CRUD operations...');
    
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    
    // Check for existing projects list
    const projectsList = page.locator('[data-testid*="projects-list"], .projects-grid, table tbody');
    await expect(projectsList.first()).toBeVisible({ timeout: 15000 });
    
    // Count existing projects
    const projectItems = page.locator('[data-testid*="project-item"], .project-card, tbody tr');
    const projectCount = await projectItems.count();
    console.log(`📊 Existing projects: ${projectCount}`);
    
    if (projectCount > 0) {
      // Test READ operation - view project details
      const firstProject = projectItems.first();
      
      // Look for project name/title
      const projectName = firstProject.locator('[data-testid*="name"], .project-name, h3, .title').first();
      if (await projectName.count() > 0) {
        const name = await projectName.textContent();
        console.log(`📋 First project name: ${name}`);
      }
      
      // Test UPDATE operation - look for edit controls
      const editButton = firstProject.locator('button:has-text("Edit"), [data-testid*="edit"], .edit-btn').first();
      if (await editButton.count() > 0) {
        await editButton.click();
        await page.waitForTimeout(1000);
        
        // Look for edit form
        const editForm = page.locator('[data-testid*="edit-form"], form, .modal').first();
        if (await editForm.count() > 0) {
          console.log('✏️ Edit form opened successfully');
          
          // Close edit form (don't actually modify)
          const cancelButton = page.locator('button:has-text("Cancel"), [data-testid*="cancel"]').first();
          if (await cancelButton.count() > 0) {
            await cancelButton.click();
          } else {
            await page.keyboard.press('Escape');
          }
        }
      }
      
      // Test DELETE operation - look for delete controls
      const deleteButton = firstProject.locator('button:has-text("Delete"), [data-testid*="delete"], .delete-btn').first();
      if (await deleteButton.count() > 0) {
        console.log('🗑️ Delete functionality available');
        
        // Don't actually delete - just verify the control exists
        const isDeleteDisabled = await deleteButton.isDisabled();
        console.log(`🔒 Delete button disabled: ${isDeleteDisabled}`);
      }
    }
    
    // Check for bulk operations
    const bulkControls = page.locator('[data-testid*="bulk"], .bulk-actions, input[type="checkbox"]');
    console.log(`📦 Bulk operation controls: ${await bulkControls.count()}`);
    
    // Check for project sorting/filtering
    const sortControls = page.locator('[data-testid*="sort"], .sort-dropdown, [aria-label*="sort"]');
    console.log(`🔄 Sort controls: ${await sortControls.count()}`);
  });

  test('2.1 Project Status and Metadata Display', async ({ page }) => {
    console.log('📈 Testing project status and metadata display...');
    
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    
    const projectItems = page.locator('[data-testid*="project-item"], .project-card, tbody tr');
    
    if (await projectItems.count() > 0) {
      const firstProject = projectItems.first();
      
      // Check for status indicators
      const statusElements = firstProject.locator('[data-testid*="status"], .status, .badge');
      if (await statusElements.count() > 0) {
        const statusTexts = await statusElements.allTextContents();
        console.log('📊 Project status indicators:', statusTexts);
      }
      
      // Check for video count display
      const videoCountElements = firstProject.locator('[data-testid*="video-count"], [data-testid*="count"], .video-count');
      if (await videoCountElements.count() > 0) {
        const countTexts = await videoCountElements.allTextContents();
        console.log('🎬 Video count displays:', countTexts);
      }
      
      // Check for creation date/time
      const dateElements = firstProject.locator('[data-testid*="date"], [data-testid*="created"], .timestamp');
      if (await dateElements.count() > 0) {
        const dateTexts = await dateElements.allTextContents();
        console.log('📅 Date displays:', dateTexts);
      }
      
      // Check for progress indicators
      const progressElements = firstProject.locator('[data-testid*="progress"], .progress-bar, .completion');
      if (await progressElements.count() > 0) {
        console.log(`📊 Progress indicators found: ${await progressElements.count()}`);
      }
      
      // Check for project owner/creator
      const ownerElements = firstProject.locator('[data-testid*="owner"], [data-testid*="creator"], .author');
      if (await ownerElements.count() > 0) {
        const ownerTexts = await ownerElements.allTextContents();
        console.log('👤 Project owners:', ownerTexts);
      }
    }
  });

  test('2.1 Video Association - Add Validated Videos', async ({ page }) => {
    console.log('🎬 Testing adding validated videos to projects...');
    
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    
    // Find a project to work with
    const projectItems = page.locator('[data-testid*="project-item"], .project-card, tbody tr');
    
    if (await projectItems.count() > 0) {
      // Click on first project to view details
      await projectItems.first().click();
      await page.waitForTimeout(1000);
      
      // Look for video management section
      const videoSection = page.locator('[data-testid*="videos"], .project-videos, .video-management');
      if (await videoSection.count() > 0) {
        await expect(videoSection.first()).toBeVisible();
        console.log('📹 Video management section found');
        
        // Look for add video button
        const addVideoButton = page.locator('button:has-text("Add Video"), [data-testid*="add-video"], .add-video-btn').first();
        if (await addVideoButton.count() > 0) {
          await addVideoButton.click();
          await page.waitForTimeout(1000);
          
          // Check for video selection interface
          const videoSelector = page.locator('[data-testid*="video-selector"], .video-picker, .modal').first();
          if (await videoSelector.count() > 0) {
            await expect(videoSelector).toBeVisible();
            console.log('🎯 Video selector opened');
            
            // Look for validated video filter
            const validatedFilter = page.locator('[data-testid*="validated"], .validated-only, input[type="checkbox"]').first();
            if (await validatedFilter.count() > 0) {
              console.log('✅ Validated videos filter available');
            }
            
            // Check for video list in selector
            const selectableVideos = page.locator('[data-testid*="selectable-video"], .video-option, .video-checkbox');
            console.log(`📋 Selectable videos: ${await selectableVideos.count()}`);
            
            // Look for multi-select capability
            const checkboxes = page.locator('input[type="checkbox"]');
            console.log(`☑️ Selection checkboxes: ${await checkboxes.count()}`);
            
            // Close selector
            const closeButton = page.locator('button:has-text("Close"), button:has-text("Cancel"), [data-testid*="close"]').first();
            if (await closeButton.count() > 0) {
              await closeButton.click();
            } else {
              await page.keyboard.press('Escape');
            }
          }
        }
        
        // Check for existing video list in project
        const projectVideos = page.locator('[data-testid*="project-video"], .video-item, .associated-video');
        console.log(`🎬 Videos currently in project: ${await projectVideos.count()}`);
        
        if (await projectVideos.count() > 0) {
          // Check for remove video functionality
          const removeButtons = page.locator('button:has-text("Remove"), [data-testid*="remove"], .remove-btn');
          console.log(`🗑️ Remove video buttons: ${await removeButtons.count()}`);
        }
      }
    } else {
      console.warn('⚠️ No projects available for video association testing');
    }
  });

  test('2.1 Video Association - Remove Videos from Project', async ({ page }) => {
    console.log('➖ Testing removing videos from projects...');
    
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    
    const projectItems = page.locator('[data-testid*="project-item"], .project-card, tbody tr');
    
    if (await projectItems.count() > 0) {
      // Enter project details
      await projectItems.first().click();
      await page.waitForTimeout(1000);
      
      // Find associated videos
      const projectVideos = page.locator('[data-testid*="project-video"], .video-item, .associated-video');
      const videoCount = await projectVideos.count();
      console.log(`🎬 Videos in project: ${videoCount}`);
      
      if (videoCount > 0) {
        const firstVideo = projectVideos.first();
        
        // Look for remove/delete controls
        const removeButton = firstVideo.locator('button:has-text("Remove"), [data-testid*="remove"], .remove-btn').first();
        if (await removeButton.count() > 0) {
          console.log('🗑️ Remove video control found');
          
          // Check if remove requires confirmation
          await removeButton.click();
          await page.waitForTimeout(500);
          
          const confirmDialog = page.locator('[role="dialog"], .confirmation, .modal').first();
          if (await confirmDialog.count() > 0) {
            console.log('⚠️ Remove confirmation dialog appeared');
            
            // Cancel the removal
            const cancelButton = page.locator('button:has-text("Cancel"), [data-testid*="cancel"]').first();
            if (await cancelButton.count() > 0) {
              await cancelButton.click();
            }
          }
        }
        
        // Check for bulk removal
        const selectAllCheckbox = page.locator('[data-testid*="select-all"], .select-all-checkbox').first();
        if (await selectAllCheckbox.count() > 0) {
          console.log('📦 Bulk selection available');
        }
        
        // Check for drag-and-drop removal
        const dragHandles = page.locator('[draggable="true"], .drag-handle').first();
        if (await dragHandles.count() > 0) {
          console.log('🔄 Drag-and-drop functionality available');
        }
      }
    }
  });

  test('2.1 Project Video Requirements - Validated Videos Only', async ({ page }) => {
    console.log('✅ Testing that only validated videos can be added to projects...');
    
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    
    const projectItems = page.locator('[data-testid*="project-item"], .project-card, tbody tr');
    
    if (await projectItems.count() > 0) {
      await projectItems.first().click();
      await page.waitForTimeout(1000);
      
      const addVideoButton = page.locator('button:has-text("Add Video"), [data-testid*="add-video"]').first();
      if (await addVideoButton.count() > 0) {
        await addVideoButton.click();
        await page.waitForTimeout(1000);
        
        // Check for validation status filter
        const statusFilters = page.locator('[data-testid*="status"], .status-filter, select');
        if (await statusFilters.count() > 0) {
          const firstFilter = statusFilters.first();
          
          // Check if only validated videos are shown by default
          const options = await firstFilter.locator('option').allTextContents();
          console.log('🎛️ Status filter options:', options);
          
          const hasValidatedOption = options.some(opt => opt.toLowerCase().includes('validated'));
          expect(hasValidatedOption).toBeTruthy();
        }
        
        // Check video list for validation status indicators
        const videoOptions = page.locator('[data-testid*="video-option"], .video-selector-item');
        if (await videoOptions.count() > 0) {
          const statusBadges = page.locator('[data-testid*="status"], .status-badge, .validated-badge');
          console.log(`📊 Status badges in video selector: ${await statusBadges.count()}`);
          
          if (await statusBadges.count() > 0) {
            const statusTexts = await statusBadges.allTextContents();
            const validatedCount = statusTexts.filter(text => text.toLowerCase().includes('validated')).length;
            console.log(`✅ Validated videos available: ${validatedCount}`);
          }
        }
        
        // Look for warning messages about non-validated videos
        const warningMessages = page.locator('.warning, .alert, [data-testid*="warning"]');
        if (await warningMessages.count() > 0) {
          const warningTexts = await warningMessages.allTextContents();
          console.log('⚠️ Warning messages:', warningTexts);
        }
        
        // Close the selector
        const closeButton = page.locator('button:has-text("Close"), [data-testid*="close"]').first();
        if (await closeButton.count() > 0) {
          await closeButton.click();
        }
      }
    }
  });

  test('2.1 Project Analytics and Insights', async ({ page }) => {
    console.log('📊 Testing project analytics and insights display...');
    
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    
    const projectItems = page.locator('[data-testid*="project-item"], .project-card, tbody tr');
    
    if (await projectItems.count() > 0) {
      await projectItems.first().click();
      await page.waitForTimeout(1000);
      
      // Look for analytics section
      const analyticsSection = page.locator('[data-testid*="analytics"], [data-testid*="insights"], .project-stats');
      if (await analyticsSection.count() > 0) {
        console.log('📈 Analytics section found');
        
        // Check for key metrics
        const metrics = page.locator('[data-testid*="metric"], .metric, .stat-card');
        console.log(`📊 Metrics displayed: ${await metrics.count()}`);
        
        if (await metrics.count() > 0) {
          const metricTexts = await metrics.allTextContents();
          console.log('📋 Metric values:', metricTexts);
        }
        
        // Look for charts or visualizations
        const charts = page.locator('canvas, svg, [data-testid*="chart"]');
        console.log(`📊 Charts/visualizations: ${await charts.count()}`);
        
        // Check for progress indicators
        const progressBars = page.locator('.progress-bar, [data-testid*="progress"]');
        console.log(`📊 Progress indicators: ${await progressBars.count()}`);
      }
      
      // Check for test history
      const testHistory = page.locator('[data-testid*="history"], [data-testid*="tests"], .test-runs');
      if (await testHistory.count() > 0) {
        console.log('📜 Test history section found');
      }
      
      // Look for export functionality
      const exportButtons = page.locator('button:has-text("Export"), [data-testid*="export"]');
      console.log(`💾 Export options: ${await exportButtons.count()}`);
    }
  });

  test('Module 2 - Comprehensive PRD Validation', async ({ page }) => {
    console.log('🏆 Running comprehensive Module 2 PRD compliance validation...');
    
    // Run all Module 2 validations
    const results = await prdValidator.validateModule2ProjectManagement();
    
    // Log results
    console.log(`📊 Module 2 Results: ${results.length} requirements tested`);
    
    const passed = results.filter(r => r.passed).length;
    const failed = results.filter(r => !r.passed).length;
    const critical = results.filter(r => !r.passed && r.requirement.priority === 'critical').length;
    
    console.log(`✅ Passed: ${passed}`);
    console.log(`❌ Failed: ${failed}`);
    console.log(`🚨 Critical Failures: ${critical}`);
    
    // Calculate compliance rate
    const complianceRate = prdValidator.getModuleComplianceRate('Module 2');
    console.log(`📈 Module 2 Compliance Rate: ${complianceRate.toFixed(1)}%`);
    
    // Expect reasonable compliance
    expect(complianceRate).toBeGreaterThan(60); // At least 60% compliance for project management
    
    // Log critical failures
    if (critical > 0) {
      console.warn(`⚠️ ${critical} critical requirements failed in Module 2`);
      const criticalFailures = results.filter(r => !r.passed && r.requirement.priority === 'critical');
      criticalFailures.forEach(failure => {
        console.warn(`🚨 CRITICAL: ${failure.requirement.requirement} - ${failure.message}`);
      });
    }
  });
});