import { BoardScreen } from "@/features/service/BoardScreen";
import { getBoardData } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function BoardPage() {
  const data = await getBoardData();
  return <BoardScreen data={data} />;
}
