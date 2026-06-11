import Link from "next/link";

export default function Home() {
  return (
      <main className="flex min-h-screen flex-col items-center justify-center bg-gray-950 text-white">
        <h1 className="text-5xl font-bold mb-4">⚽ SportPredict</h1>
        <p className="text-gray-400 mb-8 text-lg">
          AI-powered match predictions & lottery suggestions
        </p>
        <div className="flex gap-4">
          <Link href="/sports"
                className="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-xl font-semibold">
            Sports Predictions
          </Link>
          <Link href="/lottery"
                className="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-xl font-semibold">
            Lottery Tool
          </Link>
        </div>
      </main>
  );
}