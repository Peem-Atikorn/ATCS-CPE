import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import Register from "../app/register/page";
import { GoogleSignIn } from "../components/GoogleSignIn";

const state = vi.hoisted(() => ({
  user: null as { id: string; display_name: string } | null,
  checked: true,
  loggingOut: false,
  googleChallenge: vi.fn(async () => ({
    csrf_token: "challenge-123",
    nonce: "nonce-123",
  })),
  loginWithGoogle: vi.fn(async (_credential: string, _csrf: string) => {}),
  changeTeam: vi.fn(),
}));
vi.mock("../components/AppProvider", () => ({
  useApp: () => ({
    ...state,
    team: {
      key: "manchester-united",
      name: "Manchester United",
      mascot: "/mascot.png",
    },
  }),
}));
vi.mock("next/script", () => ({
  default: ({ onReady }: { onReady: () => void }) => (
    <button onClick={onReady}>Load Google SDK</button>
  ),
}));

afterEach(() => {
  state.user = null;
  state.googleChallenge.mockReset();
  state.googleChallenge.mockResolvedValue({
    csrf_token: "challenge-123",
    nonce: "nonce-123",
  });
  state.loginWithGoogle.mockReset();
  vi.unstubAllEnvs();
});

it("shows registration and an honest unavailable state without a Google client ID", () => {
  vi.stubEnv("NEXT_PUBLIC_GOOGLE_CLIENT_ID", "");
  render(<Register />);
  expect(
    screen.getByRole("heading", { name: "เข้าร่วม PANBALL" }),
  ).toBeInTheDocument();
  expect(screen.getByText(/ยังไม่เปิดใช้งานในระบบนี้/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "เข้าสู่ระบบ" })).toHaveAttribute(
    "href",
    "/login",
  );
  expect(state.googleChallenge).not.toHaveBeenCalled();
});

it("passes the Google credential and CSRF challenge to the app session flow", async () => {
  vi.stubEnv("NEXT_PUBLIC_GOOGLE_CLIENT_ID", "web-client-id");
  let onCredential!: (value: { credential: string }) => void;
  const initialize = vi.fn((options: { callback: typeof onCredential }) => {
    onCredential = options.callback;
  });
  const renderButton = vi.fn((node: HTMLElement) => {
    node.textContent = "Google button";
  });
  vi.stubGlobal("google", { accounts: { id: { initialize, renderButton } } });
  render(<GoogleSignIn />);
  await waitFor(() => expect(state.googleChallenge).toHaveBeenCalledOnce());
  fireEvent.click(screen.getByRole("button", { name: "Load Google SDK" }));
  await waitFor(() => expect(renderButton).toHaveBeenCalledOnce());
  expect(initialize).toHaveBeenCalledWith(
    expect.objectContaining({
      client_id: "web-client-id",
      nonce: "nonce-123",
      auto_select: false,
    }),
  );
  await act(async () => onCredential({ credential: "google-id-token" }));
  expect(state.loginWithGoogle).toHaveBeenCalledWith(
    "google-id-token",
    "challenge-123",
  );
});

it("keeps Google sign-in unavailable when the backend challenge endpoint is missing", async () => {
  vi.stubEnv("NEXT_PUBLIC_GOOGLE_CLIENT_ID", "web-client-id");
  state.googleChallenge.mockRejectedValueOnce(new Error("API unavailable"));
  render(<GoogleSignIn />);
  expect(await screen.findByRole("alert")).toHaveTextContent("API unavailable");
});
