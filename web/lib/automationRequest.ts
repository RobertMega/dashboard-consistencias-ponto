import { tokensMatch } from "./securityRules.ts";

export type AutomationRequestError = "UNAUTHORIZED" | "INVALID_DATE" | null;

export function automationRequestError(
  expectedToken: string | undefined,
  suppliedToken: string | undefined,
  reportDate: string,
): AutomationRequestError {
  if (!tokensMatch(expectedToken, suppliedToken)) return "UNAUTHORIZED";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(reportDate)) return "INVALID_DATE";
  return null;
}
