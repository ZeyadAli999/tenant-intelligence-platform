"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { loginSchema, type LoginInput } from "@/lib/contracts";

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      {children}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm text-[var(--danger)]">
          {error}
        </p>
      )}
    </div>
  );
}
export function LoginForm() {
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema),
    defaultValues: { tenant_code: "", email: "", password: "" },
  });
  async function submit(values: LoginInput) {
    setApiError(null);
    try {
      const response = await fetch("/api/session/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as {
          message?: string;
        } | null;
        setApiError(body?.message ?? "Sign in could not be completed.");
        return;
      }
      router.replace("/dashboard");
      router.refresh();
    } catch {
      setApiError("The sign-in service is temporarily unavailable.");
    }
  }
  return (
    <form onSubmit={handleSubmit(submit)} className="space-y-5" noValidate>
      {apiError && <Alert>{apiError}</Alert>}
      <Field
        id="tenant_code"
        label="Tenant code"
        error={errors.tenant_code?.message}
      >
        <Input
          id="tenant_code"
          autoComplete="organization"
          aria-invalid={!!errors.tenant_code}
          aria-describedby={
            errors.tenant_code ? "tenant_code-error" : undefined
          }
          {...register("tenant_code")}
        />
      </Field>
      <Field id="email" label="Email address" error={errors.email?.message}>
        <Input
          id="email"
          type="email"
          autoComplete="username"
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? "email-error" : undefined}
          {...register("email")}
        />
      </Field>
      <Field id="password" label="Password" error={errors.password?.message}>
        <div className="relative">
          <Input
            id="password"
            type={visible ? "text" : "password"}
            autoComplete="current-password"
            className="pr-12"
            aria-invalid={!!errors.password}
            aria-describedby={errors.password ? "password-error" : undefined}
            {...register("password")}
          />
          <button
            type="button"
            onClick={() => setVisible((value) => !value)}
            className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text)]"
            aria-label={visible ? "Hide password" : "Show password"}
          >
            {visible ? (
              <EyeOff aria-hidden className="h-4 w-4" />
            ) : (
              <Eye aria-hidden className="h-4 w-4" />
            )}
          </button>
        </div>
      </Field>
      <Button type="submit" disabled={isSubmitting} className="w-full">
        {isSubmitting && (
          <LoaderCircle
            aria-hidden
            className="h-4 w-4 animate-spin motion-reduce:animate-none"
          />
        )}
        {isSubmitting ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
