import { NextRequest, NextResponse } from "next/server";
import { callPython } from "@/lib/python";

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const body   = await req.json();
  const data   = await callPython("holdings", {
    action:   "update",
    id,
    quantity: body.quantity,
    cost:     body.cost,
  });
  return NextResponse.json(data);
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const data   = await callPython("holdings", { action: "delete", id });
  return NextResponse.json(data);
}
