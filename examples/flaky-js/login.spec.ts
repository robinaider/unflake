// Deliberately flaky JS example.
// Run:  python3 -m unflake scan examples/flaky-js
// Expect: FLK009 (cy.wait), FLK010 (waitForTimeout).

describe("login", () => {
  it("shows the dashboard", () => {
    cy.visit("/login");
    cy.get("#user").type("ada");
    cy.wait(3000); // FLK009: fixed wait instead of intercept + should()
    cy.get("#go").click();
  });

  it("loads the avatar", async () => {
    await page.goto("/me");
    await page.waitForTimeout(500); // FLK010: use expect(locator) instead
    await expect(page.getByRole("img")).toBeVisible();
  });
});
