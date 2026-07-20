"use client";

import { TriangleAlert } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export function ConfirmResetDialog({
  open,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <div className="mb-1 grid h-11 w-11 place-items-center rounded-2xl bg-rose-400/15 text-rose-300">
            <TriangleAlert className="h-5 w-5" />
          </div>
          <DialogTitle>Reset the current mask?</DialogTitle>
          <DialogDescription>
            This will remove all unsaved mask selections and adjustments. You can still undo it until you leave the editor.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)}>
            Keep editing
          </Button>
          <Button
            variant="danger"
            className="border border-rose-400/30 bg-rose-500/10"
            onClick={() => {
              onConfirm();
              onOpenChange(false);
            }}
          >
            Reset mask
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
