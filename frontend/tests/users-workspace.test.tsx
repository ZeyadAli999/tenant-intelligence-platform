import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { UsersWorkspace } from "@/components/users/users-workspace";
import { ADMINISTRATOR_DENIED_MESSAGE } from "@/lib/admin-api";

const role = {
  id: "00000000-0000-4000-8000-000000000003",
  name: "administrator",
  description: "Tenant Administrator",
  created_at: "2026-01-01T00:00:00Z",
};
const user = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "zeyad.said@tenant-intelligence.example",
  full_name: "Zeyad Said",
  status: "active",
  is_tenant_admin: true,
  roles: [role],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/roles"))
        return new Response(
          JSON.stringify({ items: [role], total: 1, page: 1, page_size: 100 }),
        );
      return new Response(
        JSON.stringify({ items: [user], total: 1, page: 1, page_size: 100 }),
      );
    }),
  );
});

test("renders user status and roles and validates account creation", async () => {
  render(<UsersWorkspace />);
  expect(await screen.findByText("zeyad.said@tenant-intelligence.example")).toBeVisible();
  expect(screen.getAllByText("Active").at(-1)).toBeVisible();
  expect(screen.getByText("Administrator")).toBeVisible();

  await userEvent.click(screen.getByRole("button", { name: "Create user" }));
  expect(screen.getByRole("dialog", { name: "Create tenant user" })).toBeVisible();
  await userEvent.click(
    screen.getAllByRole("button", { name: "Create user" }).at(-1)!,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("Full name is required");
});

test("contains focus and restores the exact trigger after keyboard close", async () => {
  const interaction = userEvent.setup();
  render(<UsersWorkspace />);
  await screen.findByText("zeyad.said@tenant-intelligence.example");
  const trigger = screen.getByRole("button", { name: "Create user" });
  await interaction.click(trigger);

  const dialog = screen.getByRole("dialog", { name: "Create tenant user" });
  const close = screen.getByRole("button", { name: "Close account dialog" });
  const submit = screen.getAllByRole("button", { name: "Create user" }).at(-1)!;
  expect(close).toHaveFocus();
  expect(document.body.style.overflow).toBe("hidden");

  await interaction.tab({ shift: true });
  expect(submit).toHaveFocus();
  await interaction.tab();
  expect(close).toHaveFocus();

  fireEvent.mouseDown(dialog);
  expect(dialog).toBeVisible();
  await interaction.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
  expect(document.body.style.overflow).toBe("");
});

test("closes on the backdrop but not an inside click", async () => {
  const interaction = userEvent.setup();
  render(<UsersWorkspace />);
  await screen.findByText("zeyad.said@tenant-intelligence.example");
  const trigger = screen.getByRole("button", { name: "Create user" });
  await interaction.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "Create tenant user" });

  fireEvent.mouseDown(dialog);
  expect(dialog).toBeVisible();
  fireEvent.mouseDown(dialog.parentElement!);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(trigger).toHaveFocus();
});

test("create and manage dialogs preserve submit behavior", async () => {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/roles")) {
        return new Response(
          JSON.stringify({ items: [role], total: 1, page: 1, page_size: 100 }),
        );
      }
      if (init?.method === "POST" || init?.method === "PUT") {
        return new Response(JSON.stringify(user));
      }
      return new Response(
        JSON.stringify({ items: [user], total: 1, page: 1, page_size: 100 }),
      );
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  const interaction = userEvent.setup();
  render(<UsersWorkspace />);
  await screen.findByText("zeyad.said@tenant-intelligence.example");

  await interaction.click(screen.getByRole("button", { name: "Create user" }));
  const createDialog = screen.getByRole("dialog", { name: "Create tenant user" });
  const createInputs = createDialog.querySelectorAll("input");
  await interaction.type(createInputs[0]!, "Second Administrator");
  await interaction.type(createInputs[1]!, "second@example-tenant.example");
  await interaction.type(createInputs[2]!, "Second-Administrator-99");
  await interaction.click(
    screen.getAllByRole("button", { name: "Create user" }).at(-1)!,
  );
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/backend/users",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

  await interaction.click(screen.getByRole("button", { name: "Manage account" }));
  await interaction.click(screen.getByRole("button", { name: "Save changes" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/backend/users/${user.id}`,
      expect.objectContaining({ method: "PUT" }),
    ),
  );
});

test("renders the honest empty state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) =>
      new Response(
        JSON.stringify(
          String(input).includes("/roles")
            ? { items: [role], total: 1, page: 1, page_size: 100 }
            : { items: [], total: 0, page: 1, page_size: 100 },
        ),
      ),
    ),
  );
  render(<UsersWorkspace />);
  expect(await screen.findByText("No users found")).toBeVisible();
});

test("shows the strict accessible warning only after a backend denial", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(
        JSON.stringify({
          error: "You do not have permission to perform this action.",
          code: "ADMINISTRATOR_REQUIRED",
        }),
        { status: 403 },
      ),
    ),
  );
  render(<UsersWorkspace />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    ADMINISTRATOR_DENIED_MESSAGE,
  );
});
