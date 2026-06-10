interface Props {
  params: { sport: string; country: string };
}

export default function SportCountryPage({ params }: Props) {
  return (
    <main className="p-6">
      <h1 className="text-xl font-bold capitalize">
        {params.sport} — {params.country}
      </h1>
    </main>
  );
}
