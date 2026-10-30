import { expect, test } from "@playwright/test";
import { pngFile, signUpAndProfile } from "./helpers";

test.describe("Advertiser App smoke", () => {
  test("sign-up, full new campaign, appears on Home", async ({ page }) => {
    const email = `cafe-${Date.now()}@example.com`;
    await signUpAndProfile(page, email, "cafe");

    await expect(page.getByTestId("demo-banner")).toBeVisible();
    await page.getByTestId("new-campaign").click();
    await page.waitForURL("**/campaigns/new");

    await page.getByTestId("goal-footfall").click();
    await page.getByTestId("campaign-name").fill("Smoke campaign");
    await page.getByTestId("wizard-next").click();

    await expect(page.getByTestId("step-where")).toBeVisible();
    await page.getByTestId("wizard-next").click();

    await expect(page.getByTestId("step-when")).toBeVisible();
    await page.getByTestId("wizard-next").click();

    await expect(page.getByTestId("step-budget")).toBeVisible();
    await page.getByTestId("budget-input").fill("200");
    await expect(page.getByTestId("estimate-range")).toContainText("Estimated plays");
    await expect(page.getByTestId("estimate-range")).toContainText("–");
    const estimateBefore = await page.getByTestId("estimate-range").innerText();
    await page.getByTestId("budget-input").fill("400");
    await expect.poll(async () => page.getByTestId("estimate-range").innerText()).not.toBe(estimateBefore);
    await expect(page.getByTestId("bidding-explainer")).toContainText("You set a budget");
    await page.getByTestId("wizard-next").click();

    await expect(page.getByTestId("step-creative")).toBeVisible();
    const goodPng = await pngFile(page, 1920, 1080, "good-1920x1080.png");
    await page.getByTestId("creative-file").setInputFiles(goodPng);
    await expect(page.getByTestId("creative-result")).toContainText(/Accepted/i);
    await page.getByTestId("wizard-next").click();

    await expect(page.getByTestId("step-review")).toBeVisible();
    await page.getByTestId("demo-compliance").selectOption("pass");
    await page.getByTestId("wizard-launch").click();
    await page.waitForURL("**/home");

    await expect(page.getByTestId("campaign-list")).toContainText("Smoke campaign");
  });

  test("creative check rejects bad image and long video; accepts 1920x1080", async ({ page }) => {
    const email = `creative-${Date.now()}@example.com`;
    await signUpAndProfile(page, email);
    await page.goto("/campaigns/new");
    await expect(page.getByTestId("step-goal")).toBeVisible();
    await page.getByTestId("campaign-name").fill("Creative check");
    await page.getByTestId("wizard-next").click();

    await expect(page.getByTestId("step-where")).toBeVisible();
    await expect(page.locator('[data-testid^="screen-"]').first()).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("wizard-next").click();
    await expect(page.getByTestId("step-when")).toBeVisible();
    await page.getByTestId("wizard-next").click();
    await expect(page.getByTestId("step-budget")).toBeVisible();
    await page.getByTestId("wizard-next").click();
    await expect(page.getByTestId("step-creative")).toBeVisible();

    const badPng = await pngFile(page, 1000, 1000, "bad-1000x1000.png");
    await page.getByTestId("creative-file").setInputFiles(badPng);
    await expect(page.getByTestId("creative-result")).toContainText("1000");
    await expect(page.getByTestId("creative-result")).toContainText("1920");

    const videoCheck = await page.evaluate(async () => {
      const api = (window as Window & { __advertiserApi?: { uploadCreative: Function } }).__advertiserApi;
      if (!api) throw new Error("mock api not exposed");
      return api.uploadCreative({
        filename: "long.mp4",
        mime: "video/mp4",
        width: 1920,
        height: 1080,
        duration_s: 20,
      });
    });
    expect(videoCheck.ok).toBe(false);
    expect(videoCheck.problems.join(" ")).toMatch(/20s|15 seconds/i);

    const unreadableVideo = await page.evaluate(async () => {
      const api = (window as Window & { __advertiserApi?: { uploadCreative: Function } }).__advertiserApi;
      if (!api) throw new Error("mock api not exposed");
      return api.uploadCreative({
        filename: "broken.mp4",
        mime: "video/mp4",
      });
    });
    expect(unreadableVideo.ok).toBe(false);
    expect(unreadableVideo.problems.join(" ")).toMatch(/Could not read video duration/i);
    expect(unreadableVideo.problems.join(" ")).toMatch(/Could not read video dimensions/i);

    const goodPng = await pngFile(page, 1920, 1080, "ok-1920x1080.png");
    await page.getByTestId("creative-file").setInputFiles(goodPng);
    await expect(page.getByTestId("creative-result")).toContainText(/Accepted/i);
  });

  for (const category of ["alcohol", "gambling", "political"] as const) {
    test(`${category} category shows refusal on profile`, async ({ page }) => {
      await page.goto("/signup");
      await page.evaluate(() => {
        try {
          window.localStorage.clear();
        } catch {
          /* ignore */
        }
      });
      await page.getByTestId("signup-email").fill(`${category}-${Date.now()}@example.com`);
      await page.getByTestId("signup-password").fill("secret12");
      await page.getByTestId("signup-submit").click();
      await page.waitForURL("**/profile");
      await page.getByTestId("profile-name").fill("Refused Demo");
      await page.getByTestId("profile-category").selectOption(category);
      await expect(page.getByTestId("category-refusal")).toBeVisible();
      await expect(page.getByTestId("profile-submit")).toBeDisabled();
    });
  }

  test("mock hook refused category blocks Home and createCampaign", async ({ page }) => {
    const email = `refuse-hook-${Date.now()}@example.com`;
    await signUpAndProfile(page, email, "cafe");
    await expect(page.getByTestId("new-campaign")).toBeVisible();

    await page.evaluate(async () => {
      const api = (
        window as Window & {
          __advertiserApi?: {
            updateProfile: (input: {
              name: string;
              category: string;
              lat: number;
              lng: number;
              address: string;
            }) => Promise<unknown>;
            createCampaign: (input: unknown) => Promise<unknown>;
          };
        }
      ).__advertiserApi;
      if (!api) throw new Error("mock api not exposed");
      await api.updateProfile({
        name: "Hook Refuse",
        category: "alcohol",
        lat: 53.3498,
        lng: -6.2603,
        address: "Dublin",
      });
    });

    await page.reload();
    await expect(page.getByTestId("home-category-block")).toBeVisible();
    await expect(page.getByTestId("new-campaign")).toHaveCount(0);

    const createError = await page.evaluate(async () => {
      const api = (
        window as Window & {
          __advertiserApi?: {
            createCampaign: (input: {
              name: string;
              goal: string;
              screen_ids: string[];
              start: string;
              end: string;
              dayparts: string[];
              budget: { micros: number; currency: "EUR" };
            }) => Promise<unknown>;
          };
        }
      ).__advertiserApi;
      if (!api) throw new Error("mock api not exposed");
      try {
        await api.createCampaign({
          name: "Should fail",
          goal: "footfall",
          screen_ids: ["scr-grafton"],
          start: "2026-11-01",
          end: "2026-11-07",
          dayparts: ["lunch"],
          budget: { micros: 100_000_000, currency: "EUR" },
        });
        return null;
      } catch (err) {
        return err instanceof Error ? err.message : String(err);
      }
    });
    expect(createError).toMatch(/alcohol|can't run|cannot|refuse/i);
  });

  test("wallet rejects non-positive top-up", async ({ page }) => {
    const email = `wallet-${Date.now()}@example.com`;
    await signUpAndProfile(page, email);
    await page.goto("/wallet");
    await expect(page.getByTestId("wallet-balance")).toBeVisible();

    await page.getByTestId("topup-amount").fill("0");
    await expect(page.getByTestId("topup-submit")).toBeDisabled();

    await page.getByTestId("topup-amount").fill("-10");
    await expect(page.getByTestId("topup-submit")).toBeDisabled();

    const thrown = await page.evaluate(async () => {
      const api = (window as Window & { __advertiserApi?: { topUp: Function } }).__advertiserApi;
      if (!api) throw new Error("mock api not exposed");
      try {
        await api.topUp({ micros: 0, currency: "EUR" });
        return null;
      } catch (err) {
        return err instanceof Error ? err.message : String(err);
      }
    });
    expect(thrown).toMatch(/greater than zero/i);
  });

  test("demo banner and AI label; layout at 375px", async ({ page }) => {
    const email = `layout-${Date.now()}@example.com`;
    await signUpAndProfile(page, email);
    await expect(page.getByTestId("demo-banner")).toBeVisible();

    await page.goto("/assistant");
    await expect(page.getByTestId("ai-label")).toHaveText(/AI/i);
    await expect(page.getByTestId("demo-banner")).toBeVisible();

    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/home");
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);

    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/wallet");
    await expect(page.getByTestId("demo-banner")).toBeVisible();
    await expect(page.getByTestId("wallet-balance")).toBeVisible();
  });
});
