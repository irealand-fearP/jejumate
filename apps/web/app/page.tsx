import { HomeScreen } from "@/features/home/HomeScreen";
import { getHomeData } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const data = await getHomeData();
  return <HomeScreen data={data} />;
}
