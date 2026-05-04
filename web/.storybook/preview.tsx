// web/.storybook/preview.tsx
import type { Preview } from "@storybook/react";
import { SaltProvider } from "@salt-ds/core";
import React from "react";

import "@salt-ds/theme/index.css";
import "../src/theme/autodoc-theme.css";
import "../src/index.css";

const preview: Preview = {
  decorators: [
    (Story) => (
      <SaltProvider mode="light">
        <div style={{ padding: "1rem", background: "var(--autodoc-surface)" }}>
          <Story />
        </div>
      </SaltProvider>
    ),
  ],
};

export default preview;
