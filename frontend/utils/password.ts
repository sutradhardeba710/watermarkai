// Client-side mirror of backend strength rules (SRS AUTH-001).
export function isStrongPassword(pw: string): boolean {
  if (pw.length < 8) return false;
  if (!/[A-Z]/.test(pw)) return false;
  if (!/[a-z]/.test(pw)) return false;
  if (!/[0-9]/.test(pw)) return false;
  if (!/[^A-Za-z0-9]/.test(pw)) return false;
  return true;
}

export const STRENGTH_MSG =
  "At least 8 characters with uppercase, lowercase, a number, and a special character.";
