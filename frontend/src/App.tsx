import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useSocketStore } from "./store/useSocketStore";
import { useNotificationStore } from "./store/useNotificationStore";
import { useAuthStore } from "./store/useAuthStore";
import { useConfigStore } from "./store/useConfigStore";
import Layout from "./components/layout/Layout";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import Home from "./pages/Home";
import HomeMockup from "./pages/HomeMockup";
import HomeMockup2 from "./pages/HomeMockup2";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import StockDashboard from "./pages/StockDashboard";
import CommunityPostDetailPage from "./pages/CommunityPostDetailPage";
import CommunityPostEditorPage from "./pages/CommunityPostEditorPage";
import Account from "./pages/Account";
import MyPage from "./pages/MyPage";
import Ranking from "./pages/Ranking";
import { AssetTab } from "./components/account/AssetTab";
import { TransactionHistoryTab } from "./components/account/TransactionHistoryTab";
import { OrderHistoryTab } from "./components/account/OrderHistoryTab";
import { Toaster } from "sonner";

function App() {
  const connect = useSocketStore((state) => state.connect);
  const connectSSE = useNotificationStore((state) => state.connectSSE);
  const disconnectSSE = useNotificationStore((state) => state.disconnectSSE);
  const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
  const fetchTradePolicy = useConfigStore((state) => state.fetchTradePolicy);

  useEffect(() => {
    connect();
    fetchTradePolicy();
  }, [connect, fetchTradePolicy]);

  useEffect(() => {
    if (isLoggedIn) {
      connectSSE();
    } else {
      disconnectSSE();
    }
    return () => {
      disconnectSSE();
    };
  }, [isLoggedIn, connectSSE, disconnectSSE]);

  return (
    <BrowserRouter>
      <Toaster richColors position="top-center" />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/mockup1" element={<HomeMockup />} />
        <Route path="/mockup2" element={<HomeMockup2 />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="stock/:code" element={<StockDashboard />} />
          <Route
            path="stock/:code/community/posts/:postId"
            element={<CommunityPostDetailPage />}
          />
          <Route path="ranking" element={<Ranking />} />

          <Route element={<ProtectedRoute />}>
            <Route
              path="stock/:code/community/posts/new"
              element={<CommunityPostEditorPage />}
            />
            <Route
              path="stock/:code/community/posts/:postId/edit"
              element={<CommunityPostEditorPage />}
            />
            <Route path="mypage" element={<MyPage />} />
            <Route path="account" element={<Account />}>
              <Route index element={<Navigate to="asset" replace />} />
              <Route path="asset" element={<AssetTab />} />
              <Route path="transactions" element={<TransactionHistoryTab />} />
              <Route path="orders" element={<OrderHistoryTab />} />
            </Route>
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
