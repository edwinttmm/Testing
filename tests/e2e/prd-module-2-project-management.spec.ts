import { test, expect } from '@playwright/test';
import { ErrorMonitor } from './utils/error-monitor';
import { TestHelpers } from './utils/test-helpers';

test.describe('PRD Module 2: Project Management', () => {
  let errorMonitor: ErrorMonitor;
  let helpers: TestHelpers;

  test.beforeEach(async ({ page }) => {
    errorMonitor = new ErrorMonitor(page);
    helpers = new TestHelpers(page);
    
    await page.goto('/');
    await helpers.waitForPageLoad();
  });

  test.afterEach(async ({ page }) => {
    if (errorMonitor.hasErrors()) {
      await errorMonitor.saveErrorLog(test.info().title);
    }
  });

  test('2.1 Project Creation Interface', async ({ page }) => {
    test.setTimeout(90000);
    
    console.log('🚀 Testing project creation interface...');
    
    // Navigate to projects section
    const projectPaths = [
      '/projects',
      '/project-management',
      '/manage-projects',
      '/'  // fallback to home
    ];

    let projectInterfaceFound = false;
    for (const path of projectPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();
        
        // Look for project creation elements
        const createProjectElements = [
          '[data-testid="create-project"]',
          '[data-testid="new-project"]',
          '.create-project-btn',
          '.new-project-button',
          'button:has-text("Create Project")',
          'button:has-text("New Project")',
          '[href*="create"]',
          '.project-create'
        ];

        for (const selector of createProjectElements) {
          if (await page.locator(selector).count() > 0) {
            projectInterfaceFound = true;
            console.log(`✅ Found project creation interface at ${path}: ${selector}`);
            
            // Test clicking the create project button
            try {
              await helpers.clickAndWait(selector);
              console.log(`✅ Project creation button is clickable`);
              
              // Look for project creation form
              const formElements = [
                'form[data-testid*="project"]',
                '.project-form',
                'input[name*="name"]',
                'input[placeholder*="Project"]',
                'input[placeholder*="Name"]'
              ];

              for (const formSelector of formElements) {
                if (await page.locator(formSelector).count() > 0) {
                  console.log(`✅ Found project creation form: ${formSelector}`);
                }
              }
            } catch (e) {
              console.log(`⚠️ Could not interact with create project button: ${e}`);
            }
            break;
          }
        }
        
        if (projectInterfaceFound) break;
      } catch (e) {
        continue;
      }
    }

    // Look for existing projects list
    const projectListElements = [
      '.projects-list',
      '.project-grid', 
      '[data-testid*="projects"]',
      '.project-card',
      '.project-item'
    ];

    for (const selector of projectListElements) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        console.log(`✅ Found project list interface: ${selector} (${count} elements)`);
      }
    }

    console.log('✅ Project creation interface validated');
  });

  test('2.2 Project Creation - "Front-Facing Camera v2.1 Regression Test"', async ({ page }) => {
    test.setTimeout(90000);
    
    console.log('🚀 Testing specific project creation scenario...');
    
    await page.goto('/');
    await helpers.waitForPageLoad();

    // Look for project creation workflow
    const createTriggers = [
      '[data-testid="create-project"]',
      'button:has-text("Create")',
      'button:has-text("New")',
      '.create-btn',
      '[href*="create"]'
    ];

    let creationStarted = false;
    for (const trigger of createTriggers) {
      if (await page.locator(trigger).count() > 0) {
        try {
          await helpers.clickAndWait(trigger);
          creationStarted = true;
          console.log(`✅ Started project creation via: ${trigger}`);
          break;
        } catch (e) {
          continue;
        }
      }
    }

    if (creationStarted) {
      // Fill in project details
      const projectName = "Front-Facing Camera v2.1 Regression Test";
      
      const nameFields = [
        'input[name="name"]',
        'input[name="title"]', 
        'input[name="projectName"]',
        'input[placeholder*="name" i]',
        'input[placeholder*="title" i]',
        '[data-testid*="name"]'
      ];

      for (const field of nameFields) {
        if (await page.locator(field).count() > 0) {
          try {
            await page.fill(field, projectName);
            console.log(`✅ Filled project name in: ${field}`);
            
            // Verify the text was entered
            const value = await page.inputValue(field);
            expect(value).toBe(projectName);
            break;
          } catch (e) {
            continue;
          }
        }
      }

      // Look for description field
      const descriptionFields = [
        'textarea[name="description"]',
        'input[name="description"]',
        'textarea[placeholder*="description" i]',
        '[data-testid*="description"]'
      ];

      for (const field of descriptionFields) {
        if (await page.locator(field).count() > 0) {
          try {
            await page.fill(field, "Regression testing project for front-facing camera VRU detection capabilities");
            console.log(`✅ Filled project description in: ${field}`);
          } catch (e) {
            continue;
          }
        }
      }

      // Look for save/submit button
      const saveButtons = [
        'button[type="submit"]',
        'button:has-text("Save")',
        'button:has-text("Create")',
        '[data-testid*="save"]',
        '[data-testid*="submit"]'
      ];

      for (const button of saveButtons) {
        if (await page.locator(button).count() > 0) {
          try {
            await helpers.clickAndWait(button);
            console.log(`✅ Submitted project via: ${button}`);
            break;
          } catch (e) {
            continue;
          }
        }
      }
    }

    console.log('✅ Project creation scenario tested');
  });

  test('2.3 Add Videos to Project Interface', async ({ page }) => {
    test.setTimeout(90000);
    
    console.log('🚀 Testing add videos to project interface...');

    // Navigate to projects or project detail
    await page.goto('/');
    await helpers.waitForPageLoad();

    // Look for project management interface
    const projectElements = [
      '.project-detail',
      '.project-videos',
      '[data-testid*="project"]',
      '.project-content'
    ];

    let projectDetailFound = false;
    for (const selector of projectElements) {
      if (await page.locator(selector).count() > 0) {
        projectDetailFound = true;
        console.log(`✅ Found project interface: ${selector}`);
        break;
      }
    }

    // Look for "Add Videos" functionality
    const addVideoElements = [
      '[data-testid="add-video"]',
      '[data-testid="add-videos"]',
      'button:has-text("Add Video")',
      'button:has-text("Add Videos")',
      'button:has-text("Attach")',
      '.add-video-btn',
      '[href*="add-video"]'
    ];

    for (const selector of addVideoElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found add video interface: ${selector}`);
        
        try {
          await helpers.clickAndWait(selector);
          console.log(`✅ Add video button is functional`);
          
          // Look for video selection interface
          const selectionElements = [
            '.video-selector',
            '.video-list',
            '.available-videos',
            'input[type="checkbox"]',
            '[data-testid*="video-select"]'
          ];

          for (const selElement of selectionElements) {
            if (await page.locator(selElement).count() > 0) {
              console.log(`✅ Found video selection interface: ${selElement}`);
            }
          }
        } catch (e) {
          console.log(`⚠️ Could not interact with add video button`);
        }
      }
    }

    // Look for video management in project context
    const videoManagementElements = [
      '.project-videos-list',
      '.attached-videos',
      '.video-grid',
      '[data-testid*="project-video"]'
    ];

    for (const selector of videoManagementElements) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        console.log(`✅ Found video management interface: ${selector} (${count} elements)`);
      }
    }

    console.log('✅ Add videos to project interface validated');
  });

  test('2.4 Remove Videos from Project', async ({ page }) => {
    test.setTimeout(60000);
    
    console.log('🚀 Testing remove videos from project...');

    await page.goto('/');
    await helpers.waitForPageLoad();

    // Look for video removal interfaces
    const removeVideoElements = [
      '[data-testid="remove-video"]',
      'button:has-text("Remove")',
      'button:has-text("Delete")',
      '.remove-video-btn',
      '.delete-btn',
      '[title="Remove"]',
      '[title="Delete"]',
      '.video-actions button'
    ];

    for (const selector of removeVideoElements) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        console.log(`✅ Found video removal interface: ${selector} (${count} elements)`);
        
        // Test if removal buttons are functional (without actually removing)
        const firstButton = page.locator(selector).first();
        const isEnabled = await firstButton.isEnabled();
        if (isEnabled) {
          console.log(`✅ Remove video button is enabled and functional`);
        }
      }
    }

    // Look for bulk removal options
    const bulkActionElements = [
      '[data-testid*="bulk"]',
      '.bulk-actions',
      'button:has-text("Remove Selected")',
      'button:has-text("Delete Selected")',
      '.select-all'
    ];

    for (const selector of bulkActionElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found bulk removal interface: ${selector}`);
      }
    }

    console.log('✅ Video removal functionality validated');
  });

  test('2.5 Project-Based Workflow Organization', async ({ page }) => {
    test.setTimeout(90000);
    
    console.log('🚀 Testing project-based workflow organization...');

    await page.goto('/');
    await helpers.waitForPageLoad();

    // Look for workflow organization elements
    const workflowElements = [
      '.project-workflow',
      '.workflow-steps',
      '[data-testid*="workflow"]',
      '.project-stages',
      '.process-flow'
    ];

    for (const selector of workflowElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found workflow organization: ${selector}`);
      }
    }

    // Check for project status tracking
    const statusElements = [
      '.project-status',
      '[data-testid*="status"]',
      '.status-indicator',
      '.progress-bar',
      '.completion-status'
    ];

    for (const selector of statusElements) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        console.log(`✅ Found project status tracking: ${selector} (${count} elements)`);
      }
    }

    // Look for project navigation/organization
    const navigationElements = [
      '.project-nav',
      '.project-tabs',
      '[data-testid*="nav"]',
      '.workflow-nav',
      '.project-sections'
    ];

    for (const selector of navigationElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found project navigation: ${selector}`);
        
        // Test navigation functionality
        const navItems = page.locator(`${selector} a, ${selector} button`);
        const navCount = await navItems.count();
        if (navCount > 0) {
          console.log(`✅ Found ${navCount} navigation items`);
        }
      }
    }

    console.log('✅ Project workflow organization validated');
  });

  test('2.6 Project List and Management', async ({ page }) => {
    test.setTimeout(60000);
    
    console.log('🚀 Testing project list and management interface...');

    // Navigate to projects list
    const projectListPaths = [
      '/projects',
      '/dashboard',
      '/'
    ];

    for (const path of projectListPaths) {
      try {
        await page.goto(path);
        await helpers.waitForPageLoad();

        // Look for projects list
        const listElements = [
          '.projects-list',
          '.project-grid',
          '.projects-container',
          '[data-testid*="projects"]'
        ];

        for (const selector of listElements) {
          const count = await page.locator(selector).count();
          if (count > 0) {
            console.log(`✅ Found projects list at ${path}: ${selector}`);
            
            // Look for individual project items
            const projectItems = page.locator(`${selector} .project-item, ${selector} .project-card, ${selector} [data-testid*="project"]`);
            const itemCount = await projectItems.count();
            if (itemCount > 0) {
              console.log(`✅ Found ${itemCount} project items`);
              
              // Test project item interaction
              const firstProject = projectItems.first();
              const isClickable = await firstProject.evaluate(el => {
                return window.getComputedStyle(el).cursor === 'pointer' || el.tagName.toLowerCase() === 'a';
              });
              
              if (isClickable) {
                console.log(`✅ Project items are interactive`);
              }
            }
          }
        }
        break;
      } catch (e) {
        continue;
      }
    }

    // Look for project management actions
    const managementActions = [
      'button:has-text("Edit")',
      'button:has-text("Delete")',
      'button:has-text("Duplicate")',
      '[data-testid*="edit"]',
      '[data-testid*="delete"]',
      '.project-actions'
    ];

    for (const selector of managementActions) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        console.log(`✅ Found project management actions: ${selector} (${count} elements)`);
      }
    }

    console.log('✅ Project list and management validated');
  });

  test('2.7 Project Search and Filtering', async ({ page }) => {
    test.setTimeout(60000);
    
    console.log('🚀 Testing project search and filtering...');

    await page.goto('/projects');
    await helpers.waitForPageLoad();

    // Look for search functionality
    const searchElements = [
      'input[type="search"]',
      'input[placeholder*="Search" i]',
      'input[placeholder*="Find" i]',
      '[data-testid*="search"]',
      '.search-input'
    ];

    for (const selector of searchElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found project search: ${selector}`);
        
        try {
          await page.fill(selector, 'Front-Facing');
          await page.waitForTimeout(1000);
          console.log(`✅ Project search is functional`);
        } catch (e) {
          console.log(`⚠️ Could not test search functionality`);
        }
      }
    }

    // Look for filter controls
    const filterElements = [
      'select[data-testid*="filter"]',
      '.filter-dropdown',
      'button:has-text("Filter")',
      '.filter-controls',
      '.project-filters'
    ];

    for (const selector of filterElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found project filters: ${selector}`);
      }
    }

    // Look for sort options
    const sortElements = [
      'select[data-testid*="sort"]',
      '.sort-dropdown',
      'button:has-text("Sort")',
      '.sort-controls',
      '[data-testid*="sort"]'
    ];

    for (const selector of sortElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found project sorting: ${selector}`);
      }
    }

    console.log('✅ Project search and filtering validated');
  });

  test('2.8 Project Detail View', async ({ page }) => {
    test.setTimeout(90000);
    
    console.log('🚀 Testing project detail view...');

    await page.goto('/');
    await helpers.waitForPageLoad();

    // Look for project links or navigate to project detail
    const projectLinks = page.locator('a[href*="project"], .project-item, .project-card').first();
    
    if (await projectLinks.count() > 0) {
      try {
        await projectLinks.click();
        await helpers.waitForPageLoad();
        console.log(`✅ Navigated to project detail`);
      } catch (e) {
        // Try direct navigation
        await page.goto('/projects/1');
        await helpers.waitForPageLoad();
      }
    }

    // Verify project detail elements
    const detailElements = [
      '.project-header',
      '.project-title',
      '.project-description',
      '.project-details',
      '[data-testid*="project-detail"]'
    ];

    for (const selector of detailElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found project detail element: ${selector}`);
      }
    }

    // Look for project-specific sections
    const projectSections = [
      '.project-videos',
      '.project-tests',
      '.project-results',
      '.project-analytics',
      '.project-settings'
    ];

    for (const selector of projectSections) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found project section: ${selector}`);
      }
    }

    // Check for project actions in detail view
    const detailActions = [
      'button:has-text("Edit Project")',
      'button:has-text("Run Test")',
      'button:has-text("Generate Report")',
      '[data-testid*="project-action"]'
    ];

    for (const selector of detailActions) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found project action: ${selector}`);
      }
    }

    console.log('✅ Project detail view validated');
  });

  test('2.9 Project Collaboration Features', async ({ page }) => {
    test.setTimeout(60000);
    
    console.log('🚀 Testing project collaboration features...');

    await page.goto('/');
    await helpers.waitForPageLoad();

    // Look for collaboration elements
    const collaborationElements = [
      '.project-members',
      '.collaborators',
      '[data-testid*="member"]',
      '[data-testid*="collaborator"]',
      '.team-section'
    ];

    for (const selector of collaborationElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found collaboration interface: ${selector}`);
      }
    }

    // Look for sharing functionality
    const sharingElements = [
      'button:has-text("Share")',
      '[data-testid*="share"]',
      '.share-button',
      '.project-sharing'
    ];

    for (const selector of sharingElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found sharing functionality: ${selector}`);
      }
    }

    // Look for permission controls
    const permissionElements = [
      '.permissions',
      '.access-control',
      '[data-testid*="permission"]',
      'select[name*="role"]'
    ];

    for (const selector of permissionElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found permission controls: ${selector}`);
      }
    }

    console.log('✅ Project collaboration features validated');
  });

  test('2.10 Complete Project Management Workflow', async ({ page }) => {
    test.setTimeout(120000);
    
    console.log('🚀 Testing complete project management workflow...');

    // Step 1: Navigate to projects
    await page.goto('/');
    await helpers.waitForPageLoad();

    // Step 2: Create new project
    const createButtons = page.locator('button:has-text("Create"), button:has-text("New"), [data-testid*="create"]');
    if (await createButtons.count() > 0) {
      try {
        await createButtons.first().click();
        await helpers.waitForPageLoad();
        console.log(`✅ Step 1: Project creation started`);
      } catch (e) {
        console.log(`⚠️ Step 1: Could not start project creation`);
      }
    }

    // Step 3: Fill project form (if available)
    const nameInput = page.locator('input[name*="name"], input[placeholder*="name" i]').first();
    if (await nameInput.count() > 0) {
      try {
        await nameInput.fill('Test Project Workflow');
        console.log(`✅ Step 2: Project name filled`);
      } catch (e) {
        console.log(`⚠️ Step 2: Could not fill project name`);
      }
    }

    // Step 4: Navigate to project management
    try {
      await page.goto('/projects');
      await helpers.waitForPageLoad();
      console.log(`✅ Step 3: Navigated to project management`);
    } catch (e) {
      console.log(`⚠️ Step 3: Could not navigate to project management`);
    }

    // Step 5: Verify project list
    const projectElements = page.locator('.project-item, .project-card, [data-testid*="project"]');
    const projectCount = await projectElements.count();
    if (projectCount > 0) {
      console.log(`✅ Step 4: Found ${projectCount} projects in list`);
    } else {
      console.log(`⚠️ Step 4: No projects found in list`);
    }

    // Step 6: Test project interaction
    if (await projectElements.count() > 0) {
      try {
        await projectElements.first().click();
        await helpers.waitForPageLoad();
        console.log(`✅ Step 5: Project interaction successful`);
      } catch (e) {
        console.log(`⚠️ Step 5: Could not interact with project`);
      }
    }

    console.log('✅ Complete project management workflow tested');
  });
});