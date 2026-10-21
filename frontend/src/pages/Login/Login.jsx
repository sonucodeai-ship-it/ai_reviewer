import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./login.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const AFTER_LOGIN_ROUTE = "/menu";
const OTP_LENGTH = 6;
const RESEND_SECONDS = 60;

function getApiError(data, fallback) {
  if (!data) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (typeof data.message === "string") return data.message;
  if (Array.isArray(data.detail)) {
    return data.detail.map((item) => item?.msg).filter(Boolean).join(", ") || fallback;
  }
  return fallback;
}

function Icon({ name }) {
  const common = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };

  const paths = {
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>,
    business: <><path d="M4 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16" /><path d="M16 9h3a1 1 0 0 1 1 1v11" /><path d="M8 7h4M8 11h4M8 15h4M8 19h4M3 21h18" /></>,
    phone: <><rect x="6" y="2.5" width="12" height="19" rx="2.5" /><path d="M10 18.5h4" /></>,
    lock: <><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
    eye: <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z" /><circle cx="12" cy="12" r="3" /></>,
    eyeOff: <><path d="M3 3l18 18" /><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" /><path d="M9.9 4.2A10.8 10.8 0 0 1 12 4c7 0 11 8 11 8a20.7 20.7 0 0 1-4.1 5.5" /><path d="M6.2 6.2A20.8 20.8 0 0 0 1 12s4 8 11 8a10.9 10.9 0 0 0 5.8-1.7" /></>,
    shield: <><path d="M12 3 20 6v5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6l8-3z" /><path d="m9 12 2 2 4-4" /></>,
    otp: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h.01M11 14h.01M15 14h.01" /></>,
  };

  return <svg {...common}>{paths[name]}</svg>;
}

export default function Login() {
  const navigate = useNavigate();
  const otpRef = useRef(null);

  const [mode, setMode] = useState("login");
  const [signupStep, setSignupStep] = useState("details");

  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [otp, setOtp] = useState("");

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [messageType, setMessageType] = useState("");
  const [resendTimer, setResendTimer] = useState(0);

  useEffect(() => {
    if (!resendTimer) return undefined;
    const timer = window.setInterval(() => {
      setResendTimer((value) => Math.max(value - 1, 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendTimer]);

  useEffect(() => {
    if (signupStep === "otp") {
      window.setTimeout(() => otpRef.current?.focus(), 100);
    }
  }, [signupStep]);

  const clearMessage = () => {
    setMessage("");
    setMessageType("");
  };

  const showMessage = (text, type = "error") => {
    setMessage(text);
    setMessageType(type);
  };

  const resetTemporaryState = () => {
    setPassword("");
    setConfirmPassword("");
    setOtp("");
    setSignupStep("details");
    setResendTimer(0);
    setShowPassword(false);
    setShowConfirmPassword(false);
    clearMessage();
  };

  const switchMode = (nextMode) => {
    setMode(nextMode);
    resetTemporaryState();
  };

  const validateSignup = () => {
    const business = businessName.trim();
    const normalizedEmail = email.trim().toLowerCase();
    const digits = mobile.replace(/\D/g, "");

    if (business.length < 2) {
      showMessage("Please enter your business name.");
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail)) {
      showMessage("Please enter a valid email address.");
      return false;
    }
    if (digits.length < 10 || digits.length > 15) {
      showMessage("Please enter a valid mobile number.");
      return false;
    }
    if (password.length < 8) {
      showMessage("Password must contain at least 8 characters.");
      return false;
    }
    if (password !== confirmPassword) {
      showMessage("Passwords do not match.");
      return false;
    }
    return true;
  };

  const handleLogin = async (event) => {
    event.preventDefault();
    clearMessage();

    const normalizedEmail = email.trim().toLowerCase();
    if (!normalizedEmail || !password) {
      showMessage("Please enter your email and password.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: normalizedEmail, password }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        showMessage(getApiError(data, "Unable to sign in."));
        return;
      }

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("token_type", data.token_type || "bearer");

      if (data.user) {
        localStorage.setItem("auth_user", JSON.stringify(data.user));
      }

      navigate(AFTER_LOGIN_ROUTE, { replace: true });
    } catch (error) {
      console.error("Login error:", error);
      showMessage("Unable to connect to the server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleSendSignupOtp = async (event) => {
    event.preventDefault();
    clearMessage();

    if (!validateSignup()) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/signup/send-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_name: businessName.trim(),
          email: email.trim().toLowerCase(),
          mobile: mobile.replace(/\D/g, ""),
          password,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        showMessage(getApiError(data, "Unable to send the verification code."));
        return;
      }

      setSignupStep("otp");
      setOtp("");
      setResendTimer(RESEND_SECONDS);
      showMessage(
        `Verification code sent to ${email.trim().toLowerCase()}.`,
        "success"
      );
    } catch (error) {
      console.error("Signup OTP error:", error);
      showMessage("Unable to connect to the server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOtp = async (event) => {
    event.preventDefault();
    clearMessage();

    const cleanOtp = otp.replace(/\D/g, "");
    if (cleanOtp.length !== OTP_LENGTH) {
      showMessage("Please enter the 6-digit verification code.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/signup/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          otp: cleanOtp,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        showMessage(getApiError(data, "Invalid or expired verification code."));
        return;
      }

      setSignupStep("details");
      setMode("login");
      setPassword("");
      setConfirmPassword("");
      setOtp("");
      setResendTimer(0);

      showMessage(
        "Account created successfully. You can now sign in.",
        "success"
      );
    } catch (error) {
      console.error("OTP verification error:", error);
      showMessage("Unable to connect to the server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const resendOtp = async () => {
    if (resendTimer > 0 || loading) return;
    clearMessage();

    if (!validateSignup()) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/signup/send-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          business_name: businessName.trim(),
          email: email.trim().toLowerCase(),
          mobile: mobile.replace(/\D/g, ""),
          password,
        }),
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        showMessage(getApiError(data, "Unable to resend the code."));
        return;
      }

      setOtp("");
      setResendTimer(RESEND_SECONDS);
      showMessage("A new verification code has been sent.", "success");
    } catch (error) {
      console.error("Resend OTP error:", error);
      showMessage("Unable to connect to the server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const isOtpStep = mode === "signup" && signupStep === "otp";

  return (
    <main className="auth-page">
      <section className="auth-shell">
        <aside className="auth-visual">
          <div className="auth-visual-content">
            <div className="auth-brand">
              <span className="auth-brand-mark">A</span>
              <span>AI Reviewer</span>
            </div>

            <div className="auth-hero-copy">
              <span className="auth-eyebrow">BUSINESS REVIEW PLATFORM</span>
              <h1>
                Turn customer
                <br />
                experiences into
                <br />
                <span>better reviews.</span>
              </h1>
              <p>
                A professional workspace for businesses to simplify their
                customer review journey.
              </p>
            </div>

            <div className="auth-trust">
              <span><Icon name="shield" /> Secure authentication</span>
              <span><Icon name="otp" /> Email verification</span>
            </div>
          </div>
        </aside>

        <section className="auth-panel">
          <div className="auth-panel-inner">
            <div className="auth-mobile-brand">
              <div className="auth-brand">
                <span className="auth-brand-mark">A</span>
                <span>AI Reviewer</span>
              </div>
            </div>

            <header className="auth-heading">
              <span className="auth-kicker">
                {isOtpStep
                  ? "EMAIL VERIFICATION"
                  : mode === "login"
                  ? "WELCOME BACK"
                  : "GET STARTED"}
              </span>
              <h2>
                {isOtpStep
                  ? "Verify your email"
                  : mode === "login"
                  ? "Sign in to your account"
                  : "Create your business account"}
              </h2>
              <p>
                {isOtpStep
                  ? `Enter the 6-digit code sent to ${email.trim().toLowerCase()}.`
                  : mode === "login"
                  ? "Access your AI Reviewer workspace."
                  : "Create an account for your business and get started."}
              </p>
            </header>

            {!isOtpStep && (
              <div className="auth-tabs">
                <button
                  type="button"
                  className={mode === "login" ? "active" : ""}
                  onClick={() => switchMode("login")}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  className={mode === "signup" ? "active" : ""}
                  onClick={() => switchMode("signup")}
                >
                  Create Account
                </button>
              </div>
            )}

            {isOtpStep ? (
              <form className="auth-form" onSubmit={handleVerifyOtp}>
                <div className="otp-icon"><Icon name="otp" /></div>

                <label htmlFor="otp">Verification code</label>
                <input
                  ref={otpRef}
                  id="otp"
                  className="otp-input"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={OTP_LENGTH}
                  placeholder="000000"
                  value={otp}
                  onChange={(event) =>
                    setOtp(event.target.value.replace(/\D/g, "").slice(0, OTP_LENGTH))
                  }
                />

                {message && (
                  <div className={`auth-message ${messageType}`} role="alert">
                    {message}
                  </div>
                )}

                <button className="primary-button" type="submit" disabled={loading}>
                  {loading ? <><span className="spinner" /> Verifying...</> : "Verify & Create Account"}
                </button>

                <div className="otp-actions">
                  <button
                    type="button"
                    className="text-button"
                    onClick={resendOtp}
                    disabled={resendTimer > 0 || loading}
                  >
                    {resendTimer > 0
                      ? `Resend code in ${resendTimer}s`
                      : "Resend verification code"}
                  </button>

                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => {
                      setSignupStep("details");
                      clearMessage();
                    }}
                    disabled={loading}
                  >
                    Edit signup details
                  </button>
                </div>
              </form>
            ) : (
              <form
                className="auth-form"
                onSubmit={mode === "login" ? handleLogin : handleSendSignupOtp}
              >
                {mode === "signup" && (
                  <>
                    <div className="field">
                      <label htmlFor="businessName">Business name</label>
                      <div className="input-wrap">
                        <Icon name="business" />
                        <input
                          id="businessName"
                          type="text"
                          autoComplete="organization"
                          placeholder="Your business name"
                          value={businessName}
                          onChange={(event) => setBusinessName(event.target.value)}
                          maxLength={255}
                          disabled={loading}
                        />
                      </div>
                    </div>

                    <div className="field">
                      <label htmlFor="mobile">Mobile number</label>
                      <div className="input-wrap">
                        <Icon name="phone" />
                        <input
                          id="mobile"
                          type="tel"
                          inputMode="tel"
                          autoComplete="tel"
                          placeholder="Your mobile number"
                          value={mobile}
                          onChange={(event) => setMobile(event.target.value)}
                          maxLength={15}
                          disabled={loading}
                        />
                      </div>
                    </div>
                  </>
                )}

                <div className="field">
                  <label htmlFor="email">Email address</label>
                  <div className="input-wrap">
                    <Icon name="mail" />
                    <input
                      id="email"
                      type="email"
                      autoComplete="email"
                      placeholder="you@business.com"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      maxLength={255}
                      disabled={loading}
                    />
                  </div>
                </div>

                <div className="field">
                  <label htmlFor="password">
                    {mode === "signup" ? "Create password" : "Password"}
                  </label>
                  <div className="input-wrap">
                    <Icon name="lock" />
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      autoComplete={mode === "signup" ? "new-password" : "current-password"}
                      placeholder={mode === "signup" ? "Minimum 8 characters" : "Enter your password"}
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      disabled={loading}
                    />
                    <button
                      type="button"
                      className="eye-button"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      onClick={() => setShowPassword((value) => !value)}
                    >
                      <Icon name={showPassword ? "eyeOff" : "eye"} />
                    </button>
                  </div>
                </div>

                {mode === "signup" && (
                  <div className="field">
                    <label htmlFor="confirmPassword">Confirm password</label>
                    <div className="input-wrap">
                      <Icon name="lock" />
                      <input
                        id="confirmPassword"
                        type={showConfirmPassword ? "text" : "password"}
                        autoComplete="new-password"
                        placeholder="Re-enter your password"
                        value={confirmPassword}
                        onChange={(event) => setConfirmPassword(event.target.value)}
                        disabled={loading}
                      />
                      <button
                        type="button"
                        className="eye-button"
                        aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                        onClick={() => setShowConfirmPassword((value) => !value)}
                      >
                        <Icon name={showConfirmPassword ? "eyeOff" : "eye"} />
                      </button>
                    </div>
                  </div>
                )}

                {mode === "login" && (
                  <div className="forgot-row">
                    <button
                      type="button"
                      className="text-button"
                      onClick={() =>
                        showMessage("Password reset can be connected when the password-reset API is added.")
                      }
                    >
                      Forgot password?
                    </button>
                  </div>
                )}

                {message && (
                  <div className={`auth-message ${messageType}`} role="alert">
                    {message}
                  </div>
                )}

                <button className="primary-button" type="submit" disabled={loading}>
                  {loading ? (
                    <><span className="spinner" /> {mode === "login" ? "Signing in..." : "Sending verification code..."}</>
                  ) : mode === "login" ? (
                    "Sign In"
                  ) : (
                    "Continue to Verification"
                  )}
                </button>

                {mode === "signup" && (
                  <p className="terms">
                    By creating an account, you agree to use AI Reviewer for genuine business and customer interactions.
                  </p>
                )}
              </form>
            )}

            <footer className="auth-footer">
              <Icon name="shield" />
              <span>Secure authentication and email verification</span>
            </footer>
          </div>
        </section>
      </section>
    </main>
  );
}
