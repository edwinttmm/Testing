import { Page, expect } from '@playwright/test';

export class TestHelpers {
  constructor(private page: Page) {}

  async waitForPageLoad() {
    await this.page.waitForLoadState('networkidle');
    await this.page.waitForTimeout(1000); // Allow React to fully render
  }

  async waitForElement(selector: string, timeout = 10000) {
    return await this.page.waitForSelector(selector, { timeout });
  }

  async uploadFile(inputSelector: string, filePath: string) {
    const fileChooserPromise = this.page.waitForEvent('filechooser');
    await this.page.click(inputSelector);
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(filePath);
  }

  async verifyElementText(selector: string, expectedText: string) {
    const element = await this.waitForElement(selector);
    const text = await element.textContent();
    expect(text).toContain(expectedText);
  }

  async verifyElementExists(selector: string, shouldExist = true) {
    if (shouldExist) {
      await expect(this.page.locator(selector)).toBeVisible();
    } else {
      await expect(this.page.locator(selector)).not.toBeVisible();
    }
  }

  async clickAndWait(selector: string, waitForSelector?: string) {
    await this.page.click(selector);
    if (waitForSelector) {
      await this.waitForElement(waitForSelector);
    } else {
      await this.page.waitForTimeout(500);
    }
  }

  async fillForm(fields: Array<{ selector: string; value: string }>) {
    for (const field of fields) {
      await this.page.fill(field.selector, field.value);
    }
  }

  async takeScreenshot(name: string) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    await this.page.screenshot({ 
      path: `test-results/screenshots/${name}_${timestamp}.png`,
      fullPage: true 
    });
  }

  async verifyApiResponse(url: string, expectedStatus = 200) {
    const response = await this.page.request.get(url);
    expect(response.status()).toBe(expectedStatus);
    return response;
  }
}