import { MeetingsScreen } from "@/features/service/MeetingsScreen";
import { getMeetingsData } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function MeetingsPage() {
  const data = await getMeetingsData();
  return <MeetingsScreen data={data} />;
}
