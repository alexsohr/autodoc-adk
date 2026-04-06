import { useState } from "react";
import type { Meta, StoryObj } from "@storybook/react";
import { Button } from "@salt-ds/core";
import { ConfirmDialog } from "./ConfirmDialog";

const meta = {
  title: "Shared/ConfirmDialog",
  component: ConfirmDialog,
  tags: ["autodocs"],
  argTypes: {
    open: { control: "boolean" },
    title: { control: "text" },
    message: { control: "text" },
    confirmLabel: { control: "text" },
  },
} satisfies Meta<typeof ConfirmDialog>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Open: Story = {
  args: {
    open: true,
    title: "Delete Repository",
    message:
      "Are you sure you want to remove autodoc-adk from AutoDoc? This will delete all generated documentation, wiki pages, and embedding chunks. This action cannot be undone.",
    confirmLabel: "Delete",
    onConfirm: () => console.log("Confirmed"),
    onCancel: () => console.log("Cancelled"),
  },
};

export const CustomConfirmLabel: Story = {
  args: {
    open: true,
    title: "Regenerate Documentation",
    message:
      "This will trigger a full documentation regeneration for frontend-app. The existing wiki pages will be replaced. Running pipelines for this repository will be cancelled.",
    confirmLabel: "Regenerate All",
    onConfirm: () => console.log("Confirmed"),
    onCancel: () => console.log("Cancelled"),
  },
};

export const DefaultLabel: Story = {
  args: {
    open: true,
    title: "Cancel Pipeline",
    message:
      "Are you sure you want to cancel the running pipeline for data-pipeline? Partially generated pages will be discarded.",
    onConfirm: () => console.log("Confirmed"),
    onCancel: () => console.log("Cancelled"),
  },
};

function InteractiveDialog() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <Button onClick={() => setOpen(true)}>Open Confirm Dialog</Button>
      <ConfirmDialog
        open={open}
        title="Remove Repository"
        message="Are you sure you want to remove shared-protos? All generated documentation and embeddings will be permanently deleted."
        confirmLabel="Remove"
        onConfirm={() => {
          console.log("Confirmed");
          setOpen(false);
        }}
        onCancel={() => setOpen(false)}
      />
    </div>
  );
}

export const Interactive: Story = {
  args: {
    open: false,
    title: "Remove Repository",
    message: "Are you sure?",
    onConfirm: () => {},
    onCancel: () => {},
  },
  render: () => <InteractiveDialog />,
};
