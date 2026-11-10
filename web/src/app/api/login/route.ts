import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { accessToken, COOKIE } from "@/lib/auth";

export async function POST(request: Request) {
  const form = await request.formData();
  const attempt = String(form.get("passcode") ?? "");
  const passcode = process.env.VIEWER_PASSCODE ?? "";
  const a = Buffer.from(await accessToken(attempt));
  const b = Buffer.from(await accessToken(passcode));
  const url = new URL(request.url);
  if (!passcode || !timingSafeEqual(a, b)) {
    await new Promise((resolve) => setTimeout(resolve, 600));
    return NextResponse.redirect(new URL("/login?wrong=1", url), 303);
  }
  const response = NextResponse.redirect(new URL("/", url), 303);
  response.cookies.set(COOKIE, b.toString(), {
    httpOnly: true, secure: url.protocol === "https:", sameSite: "lax", path: "/", maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}
