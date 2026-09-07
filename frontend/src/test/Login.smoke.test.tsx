import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { Login } from "../pages/Login";
import { AuthProvider } from "../lib/auth";
import { ApiError } from "../lib/api";

// Mock the API layer so this test exercises the Login component's own
// logic (form state, calling auth.login, navigating, surfacing errors)
// without needing a real backend — that full round trip is covered by
// the backend's test_api_e2e_pipeline.py instead.
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    getToken: vi.fn(() => null),
    setToken: vi.fn(),
    login: vi.fn(),
    fetchMe: vi.fn(),
  };
});

import * as api from "../lib/api";

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/products" element={<div>Products page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("Login", () => {
  it("signs in and navigates to /products on success", async () => {
    vi.mocked(api.login).mockResolvedValueOnce("fake-token");
    vi.mocked(api.fetchMe).mockResolvedValueOnce({
      id: "u1",
      email: "inspector@metrology.gov.in",
      full_name: "Asha Verma",
      role: "inspector",
      is_active: true,
      created_at: new Date().toISOString(),
    });

    renderLogin();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "inspector@metrology.gov.in");
    await user.type(screen.getByLabelText(/password/i), "inspector123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => expect(screen.getByText("Products page")).toBeInTheDocument());
    expect(api.login).toHaveBeenCalledWith("inspector@metrology.gov.in", "inspector123");
  });

  it("shows an error message and stays on the page when login fails", async () => {
    vi.mocked(api.login).mockRejectedValueOnce(new ApiError(401, "Incorrect email or password"));

    renderLogin();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/email/i), "inspector@metrology.gov.in");
    await user.type(screen.getByLabelText(/password/i), "wrong-password");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Incorrect email or password")).toBeInTheDocument();
    // Still on the login page — no navigation happened.
    expect(screen.queryByText("Products page")).not.toBeInTheDocument();
  });
});
