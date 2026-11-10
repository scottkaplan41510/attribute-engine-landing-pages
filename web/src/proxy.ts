import { NextResponse, type NextRequest } from "next/server";
import { accessToken, COOKIE } from "@/lib/auth";

const OPEN = ["/login", "/api/login", "/robots.txt", "/icon.svg"];

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const passcode = process.env.VIEWER_PASSCODE;
  const open = OPEN.includes(pathname) || pathname.startsWith("/_next/");
  const allowed =
    open ||
    (passcode !== undefined &&
      passcode !== "" &&
      request.cookies.get(COOKIE)?.value === (await accessToken(passcode)));
  const response = allowed
    ? NextResponse.next()
    : NextResponse.redirect(new URL("/login", request.url));
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  return response;
}

export const config = { matcher: "/:path*" };
