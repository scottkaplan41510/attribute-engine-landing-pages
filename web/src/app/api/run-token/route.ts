import { createHmac } from "node:crypto";
import { NextResponse } from "next/server";

const LIFETIME_SECONDS = 900;

/** Behind the passcode gate. Lets this browser call the run server for 15 minutes. */
export async function GET() {
  const secret = process.env.RUN_SECRET;
  if (!secret) return NextResponse.json({ error: "Not configured" }, { status: 503 });
  const expires = String(Math.floor(Date.now() / 1000) + LIFETIME_SECONDS);
  const signature = createHmac("sha256", secret).update(expires).digest("hex");
  return NextResponse.json({ token: `${expires}.${signature}` });
}
