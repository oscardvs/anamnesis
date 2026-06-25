import { NextResponse } from "next/server";

import { getSettings, setSettings, type SettingsPatch } from "@/lib/settings";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/** GET /api/settings - current config view (masked key, env overrides). */
export async function GET() {
  try {
    return NextResponse.json(await getSettings());
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

/** POST /api/settings - apply a patch via the CLI, then return the fresh view. */
export async function POST(request: Request) {
  let patch: SettingsPatch;
  try {
    patch = (await request.json()) as SettingsPatch;
  } catch {
    return NextResponse.json({ error: "invalid JSON" }, { status: 400 });
  }
  try {
    await setSettings(patch);
    return NextResponse.json(await getSettings());
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
