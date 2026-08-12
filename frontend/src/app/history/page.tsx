import { getRegimeHistory } from "@/lib/api";
import { HistoryView } from "./HistoryView";

export default async function HistoryPage() {
  const { history } = await getRegimeHistory();
  return <HistoryView history={history} />;
}
