import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/layout/Layout";
import ProtectedRoute from "./components/layout/ProtectedRoute";
import Home from "./pages/Home";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import StockDashboard from "./pages/StockDashboard";
import Account from "./pages/Account";
import MyPage from "./pages/MyPage";
import { AssetTab } from "./components/account/AssetTab";
import { TransactionHistoryTab } from "./components/account/TransactionHistoryTab";
import { OrderHistoryTab } from "./components/account/OrderHistoryTab";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="stock/:code" element={<StockDashboard />} />

          {/* 로그인 권한이 필요한 라우트 */}
          <Route element={<ProtectedRoute />}>
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
  )
}

export default App
