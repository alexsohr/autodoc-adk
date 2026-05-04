import { type ReactNode, useState, useEffect, useRef } from "react";
import { Dialog, DialogHeader, DialogContent, DialogActions, Button } from "@salt-ds/core";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  onConfirm,
  onCancel,
}: ConfirmDialogProps): ReactNode {
  const [confirmDisabled, setConfirmDisabled] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (open) {
      setConfirmDisabled(true);
      timerRef.current = setTimeout(() => {
        setConfirmDisabled(false);
      }, 2000);
    }
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [open]);

  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen: boolean) => {
        if (!isOpen) onCancel();
      }}
      style={{
        background: "rgba(255, 255, 255, var(--autodoc-glass-opacity))",
        backdropFilter: "blur(var(--autodoc-glass-blur))",
        WebkitBackdropFilter: "blur(var(--autodoc-glass-blur))",
        border: "none",
        borderRadius: "16px",
        boxShadow: "var(--autodoc-shadow-float)",
      }}
    >
      <DialogHeader header={title} />
      <DialogContent>
        <p
          style={{
            color: "var(--autodoc-on-surface)",
            fontSize: "0.875rem",
            lineHeight: 1.6,
            margin: 0,
          }}
        >
          {message}
        </p>
      </DialogContent>
      <DialogActions>
        <Button appearance="transparent" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          appearance="solid"
          sentiment="negative"
          onClick={onConfirm}
          disabled={confirmDisabled}
          style={{
            transition: "opacity 200ms ease-out",
          }}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
