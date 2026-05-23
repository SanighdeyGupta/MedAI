import { NextRequest, NextResponse } from "next/server";
import { searchMedicines } from "@/lib/medicines";

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q") ?? "";
  const results = await searchMedicines(q, 8);
  return NextResponse.json({ results });
}
