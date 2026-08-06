import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, expect, test, vi, beforeEach, afterEach } from "vitest";
import { ToastProvider, toast, useToast, setFlashToast } from "@/components/ui/toast";
import { AppProviders } from "@/components/app-providers";

function TestComponent() {
  const { clearToasts } = useToast();
  return (
    <div>
      <button
        onClick={() => toast.success("Row filter saved successfully.")}
      >
        Trigger Success
      </button>
      <button
        onClick={() => toast.error("Database connection failed.")}
      >
        Trigger Error
      </button>
      <button
        onClick={() => toast.warning("Connection unsynchronized.")}
      >
        Trigger Warning
      </button>
      <button
        onClick={() => toast.info("Signed out successfully.")}
      >
        Trigger Info
      </button>
      <button onClick={clearToasts}>Clear All</button>
    </div>
  );
}

describe("Global Toast Notification System", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  test("renders success toast with role status and aria-live polite", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    const btn = screen.getByText("Trigger Success");
    fireEvent.click(btn);

    const toastElement = screen.getByRole("status");
    expect(toastElement).toBeInTheDocument();
    expect(toastElement).toHaveAttribute("aria-live", "polite");
    expect(screen.getByText("Row filter saved successfully.")).toBeInTheDocument();
  });

  test("renders error toast with role alert and aria-live assertive", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    const btn = screen.getByText("Trigger Error");
    fireEvent.click(btn);

    const toastElement = screen.getByRole("alert");
    expect(toastElement).toBeInTheDocument();
    expect(toastElement).toHaveAttribute("aria-live", "assertive");
    expect(screen.getByText("Database connection failed.")).toBeInTheDocument();
  });

  test("dismiss button removes the intended toast", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("Trigger Success"));
    expect(screen.getByText("Row filter saved successfully.")).toBeInTheDocument();

    const dismissBtn = screen.getByRole("button", { name: "Dismiss notification" });
    expect(dismissBtn).toHaveAttribute("title", "Dismiss notification");

    fireEvent.click(dismissBtn);
    expect(screen.queryByText("Row filter saved successfully.")).not.toBeInTheDocument();
  });

  test("auto-dismiss removes success toast after 4000ms duration", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("Trigger Success"));
    expect(screen.getByText("Row filter saved successfully.")).toBeInTheDocument();

    // Advance timers past 4000ms
    act(() => {
      vi.advanceTimersByTime(4100);
    });

    expect(screen.queryByText("Row filter saved successfully.")).not.toBeInTheDocument();
  });

  test("prevents rapid duplicate identical toasts within 2 seconds", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    const btn = screen.getByText("Trigger Success");
    fireEvent.click(btn);
    fireEvent.click(btn);
    fireEvent.click(btn);

    const toasts = screen.getAllByText("Row filter saved successfully.");
    expect(toasts).toHaveLength(1);
  });

  test("limits visible toasts to maximum 5 items", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    act(() => {
      toast.success("Message 1");
      toast.success("Message 2");
      toast.success("Message 3");
      toast.success("Message 4");
      toast.success("Message 5");
      toast.success("Message 6");
    });

    expect(screen.queryByText("Message 1")).not.toBeInTheDocument();
    expect(screen.getByText("Message 2")).toBeInTheDocument();
    expect(screen.getByText("Message 6")).toBeInTheDocument();
  });

  test("includes reduced-motion CSS class for accessible transitions", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("Trigger Info"));
    const statusToast = screen.getByRole("status");
    expect(statusToast.className).toContain("motion-reduce:transition-none");
  });

  test("AppProviders mounts exactly one global toast viewport at root level", () => {
    render(
      <AppProviders>
        <TestComponent />
      </AppProviders>,
    );

    act(() => {
      toast.info("Global notification mounted.");
    });

    const viewports = screen.getAllByRole("status");
    expect(viewports.length).toBe(1);
    expect(screen.getByText("Global notification mounted.")).toBeInTheDocument();
  });

  test("consumes allowlisted flash toast on provider mount and clears storage immediately", () => {
    sessionStorage.clear();
    setFlashToast("logout_success");
    expect(sessionStorage.getItem("app_flash_toast")).toBe("logout_success");

    let renderResult: ReturnType<typeof render>;
    act(() => {
      renderResult = render(
        <ToastProvider>
          <div>Login Page</div>
        </ToastProvider>,
      );
    });

    expect(screen.getByText("Signed out successfully.")).toBeInTheDocument();
    expect(sessionStorage.getItem("app_flash_toast")).toBeNull();

    // Remounting does not display the toast again
    act(() => {
      renderResult.unmount();
      render(
        <ToastProvider>
          <div>Login Page Remount</div>
        </ToastProvider>,
      );
    });
    expect(screen.queryByText("Signed out successfully.")).not.toBeInTheDocument();
  });

  test("rejects non-allowlisted flash toast keys and handles storage failure gracefully", () => {
    sessionStorage.clear();

    // Arbitrary key / malicious string rejected
    setFlashToast("<script>alert(1)</script>");
    expect(sessionStorage.getItem("app_flash_toast")).toBeNull();

    render(
      <ToastProvider>
        <div>Login Page</div>
      </ToastProvider>,
    );
    expect(screen.queryByText("<script>alert(1)</script>")).not.toBeInTheDocument();

    // Storage failure simulation
    const getItemSpy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("Storage blocked");
    });

    expect(() => {
      render(
        <ToastProvider>
          <div>Login Page Under Privacy Mode</div>
        </ToastProvider>,
      );
    }).not.toThrow();

    getItemSpy.mockRestore();
  });
});
