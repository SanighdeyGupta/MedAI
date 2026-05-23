import Link from "next/link";
import { findMedicineById, getPopularMedicineIds } from "@/lib/medicines";

export default async function PopularChips() {
  const ids = getPopularMedicineIds();
  const meds = (await Promise.all(ids.map((id) => findMedicineById(id)))).filter(
    (m): m is NonNullable<typeof m> => Boolean(m)
  );

  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {meds.map((m) => (
        <Link
          key={m.id}
          href={`/m/${m.id}`}
          className="glass rounded-full px-4 py-2 text-sm text-white/80 hover:text-white lift"
        >
          {m.name}
        </Link>
      ))}
    </div>
  );
}
