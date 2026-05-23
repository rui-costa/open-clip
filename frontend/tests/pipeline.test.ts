import { test, expect } from '@playwright/test';

test.describe('Project Pipeline Integration', () => {
  test('should display the Run Pipeline button in project details', async ({ page }) => {
    // Navigate to a project detail page (using the /project/:id route)
    await page.goto('/project/00000000-0000-0000-0000-000000000000');
    
    // Verify the "Run Full Pipeline 🚀" button is present
    const runButton = page.getByRole('button', { name: /RUN FULL PIPELINE/i });
    await expect(runButton).toBeVisible();
  });
});
