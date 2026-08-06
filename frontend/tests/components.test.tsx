import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeToggle } from "@/components/theme-toggle";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/states";

test("cycles theme without storing authentication data", async () => {
  render(<ThemeToggle />);
  await userEvent.click(screen.getByRole("button", { name: /Theme: system/ }));
  expect(localStorage.getItem("theme")).toBe("light");
  expect(document.documentElement.dataset.theme).toBe("light");
});
test("renders accessible loading, error, and empty states", () => {
  const { rerender } = render(<LoadingState />);
  expect(screen.getByRole("status")).toBeVisible();
  rerender(<ErrorState message="Backend unavailable" />);
  expect(screen.getByRole("alert")).toHaveTextContent("Backend unavailable");
  rerender(<EmptyState title="Nothing here" message="No records exist." />);
  expect(screen.getByText("Nothing here")).toBeVisible();
});
