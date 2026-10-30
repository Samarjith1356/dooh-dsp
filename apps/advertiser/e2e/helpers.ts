import fs from "fs";
import path from "path";
import type { Page } from "@playwright/test";

export async function pngFile(page: Page, width: number, height: number, filename: string) {
  const dataUrl = await page.evaluate(
    ({ w, h }) => {
      const canvas = document.createElement("canvas");
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("no canvas");
      ctx.fillStyle = "#2f6fed";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = "#ffffff";
      ctx.font = "48px sans-serif";
      ctx.fillText(`${w}x${h}`, 40, 80);
      return canvas.toDataURL("image/png");
    },
    { w: width, h: height },
  );
  const base64 = dataUrl.split(",")[1] ?? "";
  const dir = path.join(__dirname, ".tmp");
  fs.mkdirSync(dir, { recursive: true });
  const filePath = path.join(dir, filename);
  fs.writeFileSync(filePath, Buffer.from(base64, "base64"));
  return filePath;
}

export async function signUpAndProfile(page: Page, email: string, category = "cafe") {
  await page.goto("/signup");
  await page.evaluate(() => {
    try {
      window.localStorage.clear();
    } catch {
      /* ignore */
    }
  });
  await page.getByTestId("signup-email").fill(email);
  await page.getByTestId("signup-password").fill("secret12");
  await page.getByTestId("account-business").click();
  await page.getByTestId("signup-submit").click();
  await page.waitForURL("**/profile");
  await page.getByTestId("profile-name").fill("Demo Café");
  await page.getByTestId("profile-category").selectOption(category);
  await page.getByTestId("profile-submit").click();
  await page.waitForURL("**/home");
}
