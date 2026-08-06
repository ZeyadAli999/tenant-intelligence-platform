import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { LoginForm } from "@/components/login-form";

const replace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh: vi.fn() }),
}));

test("validates required login fields", async () => {
  render(<LoginForm />);
  fireEvent.submit(
    screen.getByRole("button", { name: "Sign in" }).closest("form")!,
  );
  expect(await screen.findByText("Tenant code is required")).toBeVisible();
  expect(screen.getByText("Enter a valid email address")).toBeVisible();
  expect(screen.getByText("Password is required")).toBeVisible();
});
test("toggles password visibility", async () => {
  render(<LoginForm />);
  const password = screen.getByLabelText("Password");
  expect(password).toHaveAttribute("type", "password");
  await userEvent.click(screen.getByRole("button", { name: "Show password" }));
  expect(password).toHaveAttribute("type", "text");
});
test("renders loading and safe API errors", async () => {
  let finish!: (value: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          finish = resolve;
        }),
    ),
  );
  render(<LoginForm />);
  await userEvent.type(screen.getByLabelText("Tenant code"), "demo");
  await userEvent.type(
    screen.getByLabelText("Email address"),
    "user@example.com",
  );
  await userEvent.type(screen.getByLabelText("Password"), "safe-test-password");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(
    await screen.findByRole("button", { name: /Signing in/ }),
  ).toBeDisabled();
  finish(
    new Response(JSON.stringify({ message: "Invalid credentials" }), {
      status: 401,
    }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Invalid credentials",
  );
});
test("redirects after successful login", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ authenticated: true }), { status: 200 }),
    ),
  );
  render(<LoginForm />);
  await userEvent.type(screen.getByLabelText("Tenant code"), "demo");
  await userEvent.type(
    screen.getByLabelText("Email address"),
    "user@example.com",
  );
  await userEvent.type(screen.getByLabelText("Password"), "safe-test-password");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
});
