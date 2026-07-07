import { ProfileScreen } from "@/features/service/ProfileScreen";
import { getProfilePreviewData } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function ProfilePage() {
  const data = await getProfilePreviewData();
  return <ProfileScreen data={data} />;
}
