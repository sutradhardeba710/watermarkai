import { WorkspaceShell } from "@/components/WorkspaceShell";

type AppShellProps = {
  children: React.ReactNode;
  title: string;
  eyebrow?: string;
};

/**
 * Backwards-compatible shell for older workflow screens.
 *
 * Preview and result flows inherit the responsive navigation, safe-area
 * padding, account sheet, notifications, credits, and mobile bottom nav used
 * throughout the authenticated workspace.
 */
export function AppShell({ children, title, eyebrow = "Workspace" }: AppShellProps) {
  return (
    <WorkspaceShell title={title} eyebrow={eyebrow}>
      {children}
    </WorkspaceShell>
  );
}