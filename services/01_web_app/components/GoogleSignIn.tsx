"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";
import { ApiError } from "../lib/api";
import { useApp } from "./AppProvider";
import { ErrorBox } from "./Ui";

type GoogleCredential = { credential: string };
type GoogleAccounts = {
  id: {
    initialize(options: {
      client_id: string;
      callback: (response: GoogleCredential) => void;
      nonce?: string;
      auto_select: false;
    }): void;
    renderButton(
      element: HTMLElement,
      options: {
        theme: "outline";
        size: "large";
        shape: "rectangular";
        text: "continue_with";
        width: number;
      },
    ): void;
  };
};

declare global {
  interface Window {
    google?: { accounts: GoogleAccounts };
  }
}

export function GoogleSignIn() {
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID?.trim();
  const app = useApp();
  const button = useRef<HTMLDivElement>(null);
  const [scriptReady, setScriptReady] = useState(false);
  const [challenge, setChallenge] = useState<{
    csrf_token: string;
    nonce?: string;
  }>();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error>();

  useEffect(() => {
    if (!clientId || app.user || !app.checked || app.loggingOut) return;
    let active = true;
    app.googleChallenge().then(
      (value) => {
        if (active) setChallenge(value);
      },
      (cause) => {
        if (!active) return;
        setError(
          cause instanceof ApiError && cause.status === 404
            ? new Error(
                "การสมัครด้วย Google ยังไม่พร้อมใช้งาน กรุณาลองใหม่ภายหลัง",
              )
            : (cause as Error),
        );
      },
    );
    return () => {
      active = false;
    };
  }, [app.checked, app.loggingOut, app.user]);

  useEffect(() => {
    if (
      !clientId ||
      !scriptReady ||
      !challenge ||
      !button.current ||
      !window.google
    )
      return;
    const target = button.current;
    target.replaceChildren();
    window.google.accounts.id.initialize({
      client_id: clientId,
      nonce: challenge.nonce,
      auto_select: false,
      callback: async ({ credential }) => {
        setError(undefined);
        setPending(true);
        try {
          await app.loginWithGoogle(credential, challenge.csrf_token);
        } catch (cause) {
          setError(cause as Error);
        } finally {
          setPending(false);
        }
      },
    });
    window.google.accounts.id.renderButton(target, {
      theme: "outline",
      size: "large",
      shape: "rectangular",
      text: "continue_with",
      width: Math.min(target.clientWidth || 320, 400),
    });
  }, [challenge, scriptReady]);

  if (app.user || app.loggingOut) return null;
  if (!clientId) {
    return (
      <p className="google-unavailable" role="status">
        การสมัครด้วย Google ยังไม่เปิดใช้งานในระบบนี้
      </p>
    );
  }
  return (
    <div className="google-auth">
      <Script
        src="https://accounts.google.com/gsi/client"
        strategy="afterInteractive"
        onReady={() => setScriptReady(true)}
        onError={() =>
          setError(new Error("โหลด Google ไม่สำเร็จ กรุณาลองใหม่"))
        }
      />
      <div className="google-button-wrap" aria-busy={pending}>
        <div
          ref={button}
          className="google-button"
          aria-label="ดำเนินการต่อด้วย Google"
        />
        {(!challenge || !scriptReady || pending) && (
          <p role="status">
            {pending
              ? "กำลังเข้าสู่ระบบ…"
              : error
                ? ""
                : "กำลังเตรียมการเข้าสู่ระบบด้วย Google…"}
          </p>
        )}
      </div>
      <ErrorBox error={error} />
    </div>
  );
}
