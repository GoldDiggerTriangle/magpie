import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ComparableForm } from "./ComparableForm";

test("ComparableForm validates numeric price before submit", async () => {
  const user = userEvent.setup();
  const onSubmit = vi.fn();
  render(<ComparableForm itemId="item-1" onSubmit={onSubmit} />);

  await user.type(screen.getByLabelText("Price"), "abc");
  await user.click(screen.getByRole("button", { name: "Save comparable" }));

  expect(screen.getByText("Price must be a number.")).toBeInTheDocument();
  expect(onSubmit).not.toHaveBeenCalled();

  await user.clear(screen.getByLabelText("Price"));
  await user.type(screen.getByLabelText("Price"), "42.50");
  await user.click(screen.getByRole("button", { name: "Save comparable" }));

  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ price: "42.50", item: "item-1" }));
});

