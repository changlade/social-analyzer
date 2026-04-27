import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import Layout from "./components/Layout";
import Overview    from "./pages/Overview";
import Insights    from "./pages/Insights";
import ImpactDelta from "./pages/ImpactDelta";
import Sources     from "./pages/Sources";
import Reports     from "./pages/Reports";
import Chat        from "./pages/Chat";
import NewsEvents  from "./pages/NewsEvents";

export default function App() {
  return (
    <BrowserRouter>
      <Toaster theme="dark" position="top-right" />
      <Routes>
        <Route element={<Layout />}>
          <Route index                element={<Overview />}    />
          <Route path="insights"      element={<Insights />}    />
          <Route path="impact-delta"  element={<ImpactDelta />} />
          <Route path="news-events"   element={<NewsEvents />}  />
          <Route path="sources"       element={<Sources />}     />
          <Route path="reports"       element={<Reports />}     />
          <Route path="chat"          element={<Chat />}        />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
