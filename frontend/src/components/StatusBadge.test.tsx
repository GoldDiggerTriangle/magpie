import { render, screen } from "@testing-library/react";

import { StatusBadge, statusStyles } from "./StatusBadge";

test("StatusBadge maps statuses to labels and styles", () => {
  render(<StatusBadge status="ready_to_list" />);
  const badge = screen.getByText("Ready");

  expect(badge).toBeInTheDocument();
  expect(statusStyles.ready_to_list).toContain("emerald");
});
