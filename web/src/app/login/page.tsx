import { BrandLockup } from "@/components/brand";

export default async function Login({ searchParams }: { searchParams: Promise<{ wrong?: string }> }) {
  const { wrong } = await searchParams;
  return (
    <main className="flex min-h-screen items-center justify-center bg-hero px-4">
      <form action="/api/login" method="post" className="w-full max-w-sm bg-ink p-8">
        <BrandLockup />
        <h1 className="mt-6 font-medium">Enter passcode</h1>
        <input
          name="passcode" type="password" required autoFocus aria-label="Passcode"
          className="mt-3 w-full h-14 rounded-lg border border-zinc-400 bg-transparent px-3 outline-none focus:border-zinc-900"
        />
        {wrong && <p role="alert" className="mt-2 text-sm text-critical">That passcode is not right.</p>}
        <button className="mt-4 h-12 w-full rounded-full bg-zinc-900 px-4 font-medium text-ink">
          Open
        </button>
      </form>
    </main>
  );
}
