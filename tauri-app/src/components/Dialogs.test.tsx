import { render, screen } from "@testing-library/react";
import { Dialogs } from "./Dialogs";
import { describe, it, expect } from "vitest";

it("renders when open", () => {
  render(<Dialogs showHowTo={true} onCloseHowTo={() => {}} showAbout={false} onCloseAbout={() => {}} />);
  expect(screen.getByText(/How to Use/i)).toBeTruthy();
});
