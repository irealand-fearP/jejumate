import { PoliciesScreen } from "@/features/service/PoliciesScreen";
import { getPoliciesData } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function PoliciesPage() {
  const data = await getPoliciesData();
  return <PoliciesScreen data={data} />;
}
